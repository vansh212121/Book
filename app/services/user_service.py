# app/services/user_service.py
"""
User service module.

This module provides the business logic layer for user operations,
handling authorization, validation, and orchestrating repository calls.
"""
import logging
from typing import Optional, Dict, Any

from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, timezone
from app.crud.user_crud import user_repository
from app.schemas.user_schema import UserUpdate, UserListResponse, UserCreate
from app.models.user_model import User, UserRole
from app.tasks.email_tasks import send_welcome_email_task
from app.services.auth_service import auth_service

from app.services.cache_service import cache_service
from app.core.exception_utils import raise_for_status
from app.core.exceptions import (
    ResourceNotFound,
    NotAuthorized,
    ValidationError,
    ResourceAlreadyExists,
)
from app.core.security import password_manager

logger = logging.getLogger(__name__)


class UserService:
    """Handles all user-related business logic."""

    def __init__(self):
        """
        Initializes the UserService.
        This version has no arguments, making it easy for FastAPI to use,
        while still allowing for dependency injection during tests.
        """
        self.user_repository = user_repository
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def _check_authorization(
        self, *, current_user: User, target_user: User, action: str
    ) -> None:
        """
        Central authorization check. An admin can do anything.
        A non-admin can only perform actions on their own account.

        Args:
            current_user: The user performing the action
            target_user: The user being acted upon
            action: Description of the action for error messages

        Raises:
            NotAuthorized: If user lacks permission for the action
        """
        # Admins have super powers
        if current_user.is_admin:
            return

        # Users can only modify their own account
        is_not_self = current_user.id != target_user.id
        raise_for_status(
            condition=is_not_self,
            exception=NotAuthorized,
            detail=f"You are not authorized to {action} this user.",
        )

    async def create_user(self, db: AsyncSession, *, user_in: UserCreate) -> User:
        """
        Handles the business logic of creating a new user.
        """
        # 1. Check for conflicts
        existing_user = await self.user_repository.get_by_email(db, email=user_in.email)
        raise_for_status(
            condition=existing_user is not None,
            exception=ResourceAlreadyExists,
            detail=f"User with email '{user_in.email}' already exists.",
            resource_type="User",
        )

        existing_username = await self.user_repository.get_by_username(
            db, username=user_in.username
        )
        raise_for_status(
            condition=existing_username is not None,
            exception=ResourceAlreadyExists,
            detail=f"User with username '{user_in.username}' already exists.",
            resource_type="User",
        )

        # 2. Prepare the user model
        user_dict = user_in.model_dump()
        password = user_dict.pop("password")
        user_dict["hashed_password"] = password_manager.hash_password(password)
        user_dict["created_at"] = datetime.now(timezone.utc)
        user_dict["updated_at"] = datetime.now(timezone.utc)

        user_to_create = User(**user_dict)

        # 3. Delegate creation to the repository
        new_user = await self.user_repository.create(db=db, db_obj=user_to_create)
        self._logger.info(f"New user created: {new_user.email}")
        await auth_service.send_verification_email(new_user)
        await self._send_welcome_email(user=new_user)
        return new_user

    async def get_user_for_auth(
        self, db: AsyncSession, *, user_id: int
    ) -> Optional[User]:
        """
        A simplified user retrieval method for authentication purposes.
        It only performs the cache and database lookup, without authorization.
        """
        # Try cache first
        cached_user = await cache_service.get(User, user_id)
        if cached_user:
            user = await db.merge(cached_user)
        else:
            # If cache miss, get from database
            user = await self.user_repository.get(db=db, obj_id=user_id)
            if user:
                # Cache the fresh user data for subsequent requests
                await cache_service.set(user)

        return user

    async def get_user_by_id(
        self, db: AsyncSession, *, user_id: int, current_user: User
    ) -> User:
        """
        Gets a user by ID, with caching and authorization.

        Args:
            db: Database session
            user_id: ID of user to retrieve
            current_user: User making the request

        Returns:
            User: The requested user

        Raises:
            ResourceNotFound: If user doesn't exist
            NotAuthorized: If current user lacks permission to view
        """
        # Input validation
        if user_id <= 0:
            raise ValidationError("User ID must be a positive integer")

        # Try cache first
        cached_user = await cache_service.get(User, user_id)
        if cached_user:
            user = await db.merge(cached_user)
        else:
            user = await self.user_repository.get(db=db, obj_id=user_id)
            raise_for_status(
                condition=(user is None),
                exception=ResourceNotFound,
                resource_type="User",
                detail=f"User with id {user_id} not found.",
            )
            # Cache the user for future requests
            await cache_service.set(user)

        # Fine-grained authorization check
        if current_user.is_admin:
            return user
        is_not_self = current_user.id != user.id
        can_view_others = current_user.role >= UserRole.MODERATOR

        raise_for_status(
            condition=(is_not_self and not can_view_others),
            exception=NotAuthorized,
            detail="You are not authorized to view this user's profile.",
        )

        self._logger.debug(f"User {user_id} retrieved by user {current_user.id}")
        return user

    async def get_users(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        skip: int = 0,
        limit: int = 50,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> UserListResponse:
        """
        Lists users with pagination and filtering.

        Args:
            db: Database session
            current_user: User making the request
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Optional filters to apply
            order_by: Field to order by
            order_desc: Whether to order in descending order

        Returns:
            UserListResponse: Paginated list of users

        Raises:
            NotAuthorized: If user lacks permission to list users
            ValidationError: If pagination parameters are invalid
        """
        # Authorization check: Only moderators and admins can list all users
        raise_for_status(
            condition=(current_user.role < UserRole.MODERATOR),
            exception=NotAuthorized,
            detail="Only moderators and administrators can list users.",
        )

        # Input validation
        if skip < 0:
            raise ValidationError("Skip parameter must be non-negative")
        if limit <= 0 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")

        # Delegate fetching to the repository
        users, total = await self.user_repository.get_all(
            db=db,
            skip=skip,
            limit=limit,
            filters=filters,
            order_by=order_by,
            order_desc=order_desc,
        )

        # Calculate pagination info
        page = (skip // limit) + 1
        total_pages = (total + limit - 1) // limit  # Ceiling division

        # Construct the response schema
        response = UserListResponse(
            items=users, total=total, page=page, pages=total_pages, size=limit
        )

        self._logger.info(
            f"User list retrieved by {current_user.id}: {len(users)} users returned"
        )
        return response

    async def update_user(
        self,
        db: AsyncSession,
        *,
        user_id_to_update: int,
        user_data: UserUpdate,
        current_user: User,
    ) -> User:
        """Updates a user after performing necessary authorization checks."""

        if user_id_to_update <= 0:
            raise ValidationError("User ID must be a positive integer")

        user_to_update = await self.get_user_by_id(
            db, user_id=user_id_to_update, current_user=current_user
        )

        self._check_authorization(
            current_user=current_user, target_user=user_to_update, action="update"
        )

        await self._validate_user_update(db, user_data, user_to_update)

        update_dict = user_data.model_dump(exclude_unset=True, exclude_none=True)

        # Remove timestamp fields that should not be manually updated
        for ts_field in {"created_at", "updated_at", "deleted_at"}:
            update_dict.pop(ts_field, None)

        updated_user = await self.user_repository.update(
            db=db,
            user=user_to_update,
            fields_to_update=update_dict,
        )

        await cache_service.invalidate(User, user_id_to_update)

        self._logger.info(
            f"User {user_id_to_update} updated by {current_user.id}",
            extra={
                "updated_user_id": user_id_to_update,
                "updater_id": current_user.id,
                "updated_fields": list(update_dict.keys()),
            },
        )
        return updated_user

    async def deactivate_user(
        self, db: AsyncSession, *, user_id_to_deactivate: int, current_user: User
    ) -> User:
        """
        Deactivates a user account.

        Args:
            db: Database session
            user_id_to_deactivate: ID of user to deactivate
            current_user: User making the request

        Returns:
            Dict with success message

        Raises:
            ResourceNotFound: If user doesn't exist
            NotAuthorized: If current user lacks permission
            ValidationError: If trying to deactivate already inactive user
        """
        # Input validation
        if user_id_to_deactivate <= 0:
            raise ValidationError("User ID must be a positive integer")

        # 1. Fetch the user to deactivate
        user_to_deactivate = await self.get_user_by_id(
            db, user_id=user_id_to_deactivate, current_user=current_user
        )

        # 2. Perform authorization check
        self._check_authorization(
            current_user=current_user,
            target_user=user_to_deactivate,
            action="deactivate",
        )

        # 3. Check if user is already deactivated
        if not user_to_deactivate.is_active:
            raise ValidationError("User is already deactivated")

        # 4. Prevent self-deactivation for admins (business rule)
        if current_user.id == user_id_to_deactivate and current_user.is_admin:
            raise ValidationError("Administrators cannot deactivate their own accounts")

        # 5. Update user status
        deactivated_user = await self.user_repository.update(
            db=db,
            user=user_to_deactivate,
            fields_to_update={"is_active": False, "is_verified": False},
        )

        # 6. Invalidate cache and potentially revoke tokens
        await cache_service.invalidate(User, user_id_to_deactivate)
        # TODO: Add token revocation logic here

        self._logger.info(
            f"User {user_id_to_deactivate} deactivated by {current_user.id}",
            extra={
                "deactivated_user_id": user_id_to_deactivate,
                "deactivator_id": current_user.id,
            },
        )
        return deactivated_user

    async def activate_user(
        self, db: AsyncSession, *, user_id_to_activate: int, current_user: User
    ) -> User:
        """Activates a user's account. (Admin only)"""
        # The endpoint dependency already confirms current_user is an admin.
        # We just need to fetch the target user.
        user_to_activate = await self.user_repository.get(
            db=db, obj_id=user_id_to_activate
        )
        raise_for_status(
            condition=(user_to_activate is None),
            exception=ResourceNotFound,
            detail=f"User with id {user_id_to_activate} not found.",
            resource_type="User",
        )

        raise_for_status(
            condition=(user_to_activate.is_active),
            exception=ValidationError,  # Or a more specific BadRequestException
            detail="User is already active.",
        )

        activated_user = await self.user_repository.update(
            db=db, user=user_to_activate, fields_to_update={"is_active": True}
        )

        await cache_service.invalidate(User, user_id_to_activate)
        self._logger.info(f"User {user_id_to_activate} activated by {current_user.id}")
        return activated_user

    async def change_role(
        self,
        db: AsyncSession,
        *,
        user_id_to_change: int,
        new_role: UserRole,
        current_user: User,
    ) -> User:
        """Changes a user's role. (Admin only)"""
        raise_for_status(
            condition=(user_id_to_change == current_user.id),
            exception=ValidationError,
            detail="Administrators cannot change their own role.",
        )

        user_to_change = await self.user_repository.get(db=db, obj_id=user_id_to_change)
        raise_for_status(
            condition=(user_to_change is None),
            exception=ResourceNotFound,
            detail=f"User with id {user_id_to_change} not found.",
                resource_type="User",
            
        )

        updated_user = await self.user_repository.update(
            db=db, user=user_to_change, fields_to_update={"role": new_role}
        )

        await cache_service.invalidate(User, user_id_to_change)
        self._logger.info(
            f"User {user_id_to_change} role changed to {new_role.value} by {current_user.id}"
        )
        return updated_user

    async def delete_user(
        self, db: AsyncSession, *, user_id_to_delete: int, current_user: User
    ) -> Dict[str, str]:
        """
        Permanently deletes a user account.

        Args:
            db: Database session
            user_id_to_delete: ID of user to delete
            current_user: User making the request

        Returns:
            Dict with success message

        Raises:
            ResourceNotFound: If user doesn't exist
            NotAuthorized: If current user lacks permission
            ValidationError: If trying to delete own account or last admin
        """
        # Input validation
        if user_id_to_delete <= 0:
            raise ValidationError("User ID must be a positive integer")

        # 1. Fetch the user to delete
        user_to_delete = await self.get_user_by_id(
            db, user_id=user_id_to_delete, current_user=current_user
        )

        # 2. Perform authorization check
        self._check_authorization(
            current_user=current_user,
            target_user=user_to_delete,
            action="delete",
        )

        # 3. Business rules validation
        await self._validate_user_deletion(db, user_to_delete, current_user)

        # 4. Perform the deletion
        await self.user_repository.delete(db=db, obj_id=user_id_to_delete)

        # 5. Clean up cache and tokens
        await cache_service.invalidate(User, user_id_to_delete)
        # TODO: Add token revocation logic here

        self._logger.warning(
            f"User {user_id_to_delete} permanently deleted by {current_user.id}",
            extra={
                "deleted_user_id": user_id_to_delete,
                "deleter_id": current_user.id,
                "deleted_user_email": user_to_delete.email,
            },
        )

        return {"message": "User deleted successfully"}

    async def _validate_user_update(
        self, db: AsyncSession, user_data: UserUpdate, existing_user: User
    ) -> None:
        """Validates user update data for potential conflicts."""

        if user_data.email and user_data.email != existing_user.email:
            if await self.user_repository.get_by_email(db=db, email=user_data.email):
                raise ResourceAlreadyExists("Email address is already in use")

        if user_data.username and user_data.username != existing_user.username:
            if await self.user_repository.get_by_username(
                db=db, username=user_data.username
            ):
                raise ResourceAlreadyExists("Username is already in use")

    async def _validate_user_deletion(
        self, db: AsyncSession, user_to_delete: User, current_user: User
    ) -> None:
        """
        Validates user deletion for business rules.

        Args:
            db: Database session
            user_to_delete: User to be deleted
            current_user: User performing the deletion

        Raises:
            ValidationError: If deletion violates business rules
        """
        # Prevent self-deletion
        if current_user.id == user_to_delete.id:
            raise ValidationError("Users cannot delete their own accounts")

        # Prevent deletion of the last admin
        if user_to_delete.is_admin:
            admin_count = await self.user_repository.count(
                db=db, filters={"role": UserRole.ADMIN, "is_active": True}
            )
            if admin_count <= 1:
                raise ValidationError(
                    "Cannot delete the last active administrator account"
                )

    # --- Private Helper Methods for Email Sending (Simulated) ---
    async def _send_welcome_email(self, user: User):
        """
        Dispatches a Celery task to send a password reset email.
        """
        send_welcome_email_task.delay(email_to=user.email, first_name=user.first_name)

        # We can still log that the task was dispatched.
        logger.info(f"Dispatched a welcome email task for {user.email}")


# Singleton instance for the rest of the application to use
user_services = UserService()



# async def get_reviews_by_user(
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