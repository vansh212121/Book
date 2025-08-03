# # app/services/user_service.py
# """
# User service module.

# This module provides the business logic layer for user operations,
# handling authorization, validation, and orchestrating repository calls.
# """

# import logging
# from typing import List, Optional, Dict, Any
# from datetime import datetime, timedelta

# from sqlmodel.ext.asyncio.session import AsyncSession

# from app.crud.user_crud import UserRepository
# from app.schemas.user_schema import (
#     UserCreate,
#     UserUpdate,
#     UserListResponse,
#     UserSearchParams
# )
# from app.models.user_model import User, UserRole
# from app.models.review_model import Review
# from app.core.exceptions import (
#     NotAuthorized,
#     UserNotFound,
#     ValidationError,
#     BusinessLogicError
# )
# from app.core.cache import cache_key_wrapper, invalidate_cache
# from app.core.config import settings

# logger = logging.getLogger(__name__)


# class UserService:
#     """
#     Enhanced user service with business logic and authorization.

#     This service extends the base CRUD operations with additional
#     business rules, authorization checks, and validation.
#     """

#     def __init__(self):
#         self.user_repository = UserRepository()
#         self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

#     def _check_authorization(
#         self,
#         current_user: User,
#         target_user: User,
#         action: str
#     ) -> None:
#         """
#         Check if current user is authorized to perform action on target user.

#         Args:
#             current_user: User performing the action
#             target_user: User being acted upon
#             action: Action being performed

#         Raises:
#             NotAuthorized: If user is not authorized
#         """
#         # Admins can do anything
#         if current_user.role == UserRole.ADMIN:
#             return

#         # Users can only modify their own account
#         if current_user.id != target_user.id:
#             raise NotAuthorized(
#                 detail=f"You are not authorized to {action} this user",
#                 resource="user",
#                 action=action
#             )

#     @cache_key_wrapper("user:{user_id}", expire=300)
#     async def get_user_by_id(
#         self,
#         db: AsyncSession,
#         user_id: int,
#         current_user: Optional[User] = None
#     ) -> User:
#         """
#         Get a user by ID with optional authorization check.

#         Args:
#             db: Database session
#             user_id: User ID
#             current_user: Optional current user for authorization

#         Returns:
#             User object

#         Raises:
#             UserNotFound: If user doesn't exist
#             NotAuthorized: If not authorized to view user
#         """
#         user = await self.user_repository.get_by_id(user_id, db)

#         # Check if current user can view this user
#         if current_user and current_user.role != UserRole.ADMIN:
#             # Non-admins can only view active users or themselves
#             if not user.is_active and current_user.id != user.id:
#                 raise NotAuthorized(
#                     detail="You cannot view inactive users",
#                     resource="user",
#                     action="view"
#                 )

#         return user

#     async def get_users(
#         self,
#         db: AsyncSession,
#         current_user: User,
#         search_params: Optional[UserSearchParams] = None,
#         page: int = 1,
#         size: int = 20
#     ) -> UserListResponse:
#         """
#         Get users with filtering and pagination.

#         Args:
#             db: Database session
#             current_user: Current user
#             search_params: Search parameters
#             page: Page number
#             size: Items per page

#         Returns:
#             Paginated user list
#         """
#         # Only admins can list all users
#         if current_user.role != UserRole.ADMIN:
#             raise NotAuthorized(
#                 detail="Only administrators can list users",
#                 resource="users",
#                 action="list"
#             )

#         # Build filters
#         filters = {}
#         if search_params:
#             if search_params.role:
#                 filters["role"] = search_params.role
#             if search_params.is_active is not None:
#                 filters["is_active"] = search_params.is_active
#             if search_params.is_verified is not None:
#                 filters["is_verified"] = search_params.is_verified
#             if search_params.search:
#                 filters["search"] = search_params.search

#         skip = (page - 1) * size

#         return await self.user_repository.get_many(
#             db=db,
#             skip=skip,
#             limit=size,
#             filters=filters
#         )

#     async def get_reviews_by_user(
#         self,
#         db: AsyncSession,
#         user_id: int,
#         current_user: Optional[User] = None
#     ) -> List[Review]:
#         """
#         Get all reviews written by a specific user.

#         Args:
#             db: Database session
#             user_id: User ID
#             current_user: Optional current user for authorization

#         Returns:
#             List of reviews
#         """
#         user = await self.user_repository.get_with_reviews(user_id, db)

#         # Check if reviews are public or user has access
#         if current_user:
#             if current_user.id != user.id and current_user.role != UserRole.ADMIN:
#                 # Filter out private reviews if any
#                 return [r for r in user.reviews if getattr(r, 'is_public', True)]
#         else:
#             # Anonymous users only see public reviews
#             return [r for r in user.reviews if getattr(r, 'is_public', True)]

#         return user.reviews

#     async def update_user(
#         self,
#         db: AsyncSession,
#         user_id: int,
#         user_data: UserUpdate,
#         current_user: User
#     ) -> User:
#         """
#         Update a user with authorization check.

#         Args:
#             db: Database session
#             user_id: ID of user to update
#             user_data: Update data
#             current_user: User performing the update

#         Returns:
#             Updated user

#         Raises:
#             UserNotFound: If user doesn't exist
#             NotAuthorized: If not authorized
#         """
#         # Get target user
#         user_to_update = await self.user_repository.get_by_id(user_id, db)

#         # Check authorization
#         self._check_authorization(current_user, user_to_update, "update")

#         # Additional validation for role changes
#         if user_data.role and user_data.role != user_to_update.role:
#             if current_user.role != UserRole.ADMIN:
#                 raise NotAuthorized(
#                     detail="Only administrators can change user roles",
#                     resource="user",
#                     action="update_role"
#                 )

#         # Update user
#         updated_user = await self.user_repository.update(user_id, user_data, db)

#         # Invalidate caches
#         await invalidate_cache(f"user:{user_id}")

#         self._logger.info(
#             f"User {user_id} updated by {current_user.id}",
#             extra={
#                 "user_id": user_id,
#                 "updater_id": current_user.id,
#                 "updates": user_data.model_dump(exclude_unset=True)
#             }
#         )

#         return updated_user

#     async def deactivate_user(
#         self,
#         db: AsyncSession,
#         user_id: int,
#         current_user: User
#     ) -> Dict[str, str]:
#         """
#         Deactivate a user account.

#         Args:
#             db: Database session
#             user_id: ID of user to deactivate
#             current_user: User performing the action

#         Returns:
#             Success message

#         Raises:
#             UserNotFound: If user doesn't exist
#             NotAuthorized: If not authorized
#         """
#         # Get target user
#         user_to_deactivate = await self.user_repository.get_by_id(user_id, db)

#         # Check authorization
#         self._check_authorization(current_user, user_to_deactivate, "deactivate")

#         # Prevent admin from deactivating themselves
#         if current_user.id == user_id and current_user.role == UserRole.ADMIN:
#             # Check if there are other admins
#             admin_count = await db.scalar(
#                 select(func.count(User.id))
#                 .where(
#                     and_(
#                         User.role == UserRole.ADMIN,
#                         User.is_active == True,
#                         User.id != user_id
#                     )
#                 )
#             )

#             if admin_count == 0:
#                 raise BusinessLogicError(
#                     detail="Cannot deactivate the last admin account",
#                     rule="last_admin_protection"
#                 )

#         # Deactivate user
#         await self.user_repository.deactivate(user_id, db)

#         # Revoke all user tokens
#         from app.core.security import token_manager
#         await token_manager.revoke_all_user_tokens(
#             str(user_id),
#             "account_deactivated"
#         )

#         self._logger.info(
#             f"User {user_id} deactivated by {current_user.id}",
#             extra={
#                 "user_id": user_id,
#                 "deactivator_id": current_user.id
#             }
#         )

#         return {"message": "User deactivated successfully"}

#     async def delete_user(
#         self,
#         db: AsyncSession,
#         user_id: int,
#         current_user: User
#     ) -> Dict[str, str]:
#         """
#         Delete a user account (soft delete).

#         Args:
#             db: Database session
#             user_id: ID of user to delete
#             current_user: User performing the action

#         Returns:
#             Success message
#         """
#         # Only admins can delete users
#         if current_user.role != UserRole.ADMIN:
#             raise NotAuthorized(
#                 detail="Only administrators can delete users",
#                 resource="user",
#                 action="delete"
#             )

#         # Prevent deleting self
#         if current_user.id == user_id:
#             # app/services/user_service.py (continued)
#             raise BusinessLogicError(
#                 detail="You cannot delete your own account",
#                 rule="self_deletion_protection"
#             )

#         # Delete user
#         await self.user_repository.delete(user_id, db)

#         # Revoke all user tokens
#         from app.core.security import token_manager
#         await token_manager.revoke_all_user_tokens(
#             str(user_id),
#             "account_deleted"
#         )

#         self._logger.info(
#             f"User {user_id} deleted by {current_user.id}",
#             extra={
#                 "user_id": user_id,
#                 "deleter_id": current_user.id
#             }
#         )

#         return {"message": "User deleted successfully"}

#     async def get_user_statistics(
#         self,
#         db: AsyncSession,
#         current_user: User
#     ) -> Dict[str, Any]:
#         """
#         Get user statistics.

#         Args:
#             db: Database session
#             current_user: Current user

#         Returns:
#             User statistics
#         """
#         # Only admins can view statistics
#         if current_user.role != UserRole.ADMIN:
#             raise NotAuthorized(
#                 detail="Only administrators can view user statistics",
#                 resource="statistics",
#                 action="view"
#             )

#         return await self.user_repository.get_statistics(db)


# # Create singleton instance
# user_service = UserService()


# # Legacy functions for backward compatibility
# async def get_user_by_id(db: AsyncSession, user_id: int) -> User:
#     """Service to get a user by ID, handling not found errors."""
#     return await user_service.get_user_by_id(db, user_id)


# async def get_reviews_by_user(db: AsyncSession, user_id: int) -> List[Review]:
#     """Service to get all reviews written by a specific user."""
#     return await user_service.get_reviews_by_user(db, user_id)


# async def update_user(
#     db: AsyncSession,
#     user_id: int,
#     user_data: UserUpdate,
#     current_user: User
# ) -> User:
#     """Service to update a user, ensuring the requesting user is authorized."""
#     return await user_service.update_user(db, user_id, user_data, current_user)


# async def deactivate_user(
#     db: AsyncSession,
#     user_id: int,
#     current_user: User
# ) -> Dict[str, str]:
#     """Service to deactivate a user, ensuring the requesting user is authorized."""
#     return await user_service.deactivate_user(db, user_id, current_user)


# # app/services/user_service.py
"""
User service module.

This module provides the business logic layer for user operations,
handling authorization, validation, and orchestrating repository calls.
"""

# app/services/user_service.py
"""
User business logic service.
"""
# import logging
# from typing import Optional
# from sqlmodel.ext.asyncio.session import AsyncSession

# from app.crud.user_crud import user_repository
# from app.services.cache_service import cache_service
# from app.models.user_model import User

# logger = logging.getLogger(__name__)

# class UserService:
#     """Handles user business logic with caching."""
    
#     def __init__(self):
#         self.user_repo = user_repository
#         self.cache_service = cache_service

#     async def get_user_by_id(self, db: AsyncSession, user_id: int) -> Optional[User]:
#         """Get user by ID with caching."""
#         # Try cache first
#         user = await self.cache_service.get_user(user_id)
#         if user:
#             return user
        
#         # Get from database
#         user = await self.user_repo.get(db, obj_id=user_id)
#         if user:
#             # Cache for future requests
#             await self.cache_service.cache_user(user)
        
#         return user

#     async def invalidate_user_cache(self, user_id: int):
#         """Invalidate user cache when user data changes."""
#         await self.cache_service.invalidate_user(user_id)



# user_service = UserService()


import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user_crud import user_repository
from app.services.cache_service import cache_service
from app.models.user_model import User

logger = logging.getLogger(__name__)

class UserService:
    """Handles user business logic with caching."""
    
    async def get_user_by_id(self, db: AsyncSession, user_id: int) -> Optional[User]:
        """
        Get user by ID, using a read-through caching pattern.
        """
        user = await cache_service.get_user(user_id)
        if user:
            return user
        
        user = await user_repository.get(db, obj_id=user_id)
        if user:
            await cache_service.cache_user(user)
        
        return user

# Singleton instance
user_service = UserService()
