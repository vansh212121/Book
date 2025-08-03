# # app/services/book_service.py
# """
# Book service module.

# This module provides the business logic layer for book operations,
# handling authorization, validation, and orchestrating repository calls.
# """

# import logging
# from typing import List, Optional, Dict, Any

# from sqlmodel.ext.asyncio.session import AsyncSession

# from app.crud.book_crud import BookRepository, BookService as BaseBookService
# from app.crud.tag_crud import TagRepository
# from app.schemas.book_schema import (
#     BookCreate,
#     BookUpdate,
#     BookSearchParams,
#     BookListResponse,
#     BookResponseDetailed,
# )
# from app.models.book_model import Book
# from app.models.user_model import User, UserRole
# from app.models.tag_model import Tag
# from app.core.exceptions import (
#     BookNotFound,
#     NotAuthorized,
#     ValidationError,
#     BusinessLogicError,
# )
# from app.core.cache import cache_key_wrapper, invalidate_cache
# from app.core.config import settings

# logger = logging.getLogger(__name__)


# class BookService:
#     """
#     Enhanced book service with business logic and authorization.

#     This service extends the base CRUD service with additional
#     business rules, authorization checks, and tag management.
#     """

#     def __init__(self):
#         self.book_repository = BookRepository()
#         self.tag_repository = TagRepository()
#         self.base_service = BaseBookService(self.book_repository)
#         self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

#     async def _process_tags(self, db: AsyncSession, tag_names: List[str]) -> List[Tag]:
#         """
#         Process tag names into Tag objects (get or create).

#         Args:
#             db: Database session
#             tag_names: List of tag names

#         Returns:
#             List of Tag objects
#         """
#         tags = []
#         seen = set()

#         for tag_name in tag_names:
#             # Normalize tag name
#             normalized_name = tag_name.strip().lower()

#             # Skip empty or duplicate tags
#             if not normalized_name or normalized_name in seen:
#                 continue

#             seen.add(normalized_name)

#             # Get or create tag
#             tag = await self.tag_repository.get_or_create(db=db, name=normalized_name)
#             tags.append(tag)

#         return tags

#     def _check_authorization(self, user: User, book: Book, action: str) -> None:
#         """
#         Check if user is authorized to perform action on book.

#         Args:
#             user: User performing the action
#             book: Book being acted upon
#             action: Action being performed (update, delete, etc.)

#         Raises:
#             NotAuthorized: If user is not authorized
#         """
#         # Admins can do anything
#         if user.role == UserRole.ADMIN:
#             return

#         # Users can only modify their own books
#         if book.user_id != user.id:
#             raise NotAuthorized(
#                 detail=f"You are not authorized to {action} this book",
#                 resource="book",
#                 action=action,
#             )

#     # --- READ Operations ---

#     async def get_all_books(
#         self,
#         db: AsyncSession,
#         search_params: Optional[BookSearchParams] = None,
#         page: int = 1,
#         size: int = 20,
#         user: Optional[User] = None,
#     ) -> BookListResponse:
#         """
#         Get all books with optional filtering and pagination.

#         Args:
#             db: Database session
#             search_params: Search/filter parameters
#             page: Page number (1-based)
#             size: Items per page
#             user: Optional user for filtering own books

#         Returns:
#             Paginated book list
#         """
#         # Use default search params if none provided
#         if search_params is None:
#             search_params = BookSearchParams()

#         # Add user filter if specified
#         if user and not search_params.user_id:
#             search_params.user_id = user.id

#         return await self.base_service.search_books(
#             db=db, search_params=search_params, page=page, size=size
#         )

#     @cache_key_wrapper("book:detail:{book_id}", expire=1800)
#     async def get_book_by_id(
#         self, book_id: int, db: AsyncSession, include_reviews: bool = False
#     ) -> BookResponseDetailed:
#         """
#         Get detailed book information by ID.

#         Args:
#             book_id: Book ID
#             db: Database session
#             include_reviews: Whether to include reviews

#         Returns:
#             Detailed book information

#         Raises:
#             BookNotFound: If book doesn't exist
#         """
#         book = await self.book_repository.get_by_id(
#             book_id=book_id, db=db, load_relationships=True
#         )

#         # Calculate average rating if reviews are included
#         average_rating = None
#         review_count = 0

#         if include_reviews and book.reviews:
#             review_count = len(book.reviews)
#             if review_count > 0:
#                 total_rating = sum(review.rating for review in book.reviews)
#                 average_rating = round(total_rating / review_count, 2)

#         # Convert to detailed response
#         return BookResponseDetailed(
#             **book.model_dump(),
#             average_rating=average_rating,
#             review_count=review_count,
#         )

#     async def get_user_books(
#         self, user: User, db: AsyncSession, page: int = 1, size: int = 20
#     ) -> BookListResponse:
#         """
#         Get all books created by a specific user.

#         Args:
#             user: User whose books to retrieve
#             db: Database session
#             page: Page number
#             size: Items per page

#         Returns:
#             Paginated book list
#         """
#         search_params = BookSearchParams(user_id=user.id)

#         return await self.get_all_books(
#             db=db, search_params=search_params, page=page, size=size
#         )

#     # --- CREATE Operations ---

#     async def create_book(
#         self, db: AsyncSession, book_data: BookCreate, user: User
#     ) -> Book:
#         """
#         Create a new book with tag handling.

#         Args:
#             db: Database session
#             book_data: Book creation data
#             user: User creating the book

#         Returns:
#             Created book

#         Raises:
#             BookAlreadyExists: If book already exists
#             ValidationError: If validation fails
#         """
#         # Validate user can create books
#         if user.role == UserRole.VIEWER:
#             raise NotAuthorized(
#                 detail="Viewers cannot create books", resource="book", action="create"
#             )

#         # Check daily creation limit for non-admin users
#         if user.role != UserRole.ADMIN:
#             today_count = await self._get_user_books_created_today(user.id, db)
#             if today_count >= settings.MAX_BOOKS_PER_DAY:
#                 raise BusinessLogicError(
#                     detail=f"Daily book creation limit ({settings.MAX_BOOKS_PER_DAY}) reached",
#                     rule="daily_limit",
#                 )

#         # Process tags if provided
#         processed_book_data = book_data.model_dump(exclude={"tags"})

#         # Create book
#         book = await self.book_repository.create(
#             book_data=BookCreate(**processed_book_data), user_id=user.id, db=db
#         )

#         # Add tags if provided
#         if book_data.tags:
#             book.tags = await self._process_tags(db, book_data.tags)
#             await db.commit()
#             await db.refresh(book)

#         # Invalidate user's book cache
#         await invalidate_cache(f"books:user:{user.id}")

#         self._logger.info(
#             f"Book created by user {user.id}: {book.id} - {book.title}",
#             extra={
#                 "book_id": book.id,
#                 "user_id": user.id,
#                 "tags": [tag.name for tag in book.tags],
#             },
#         )

#         return book

#     # --- UPDATE Operations ---

#     async def update_book(
#         self, db: AsyncSession, book_id: int, book_data: BookUpdate, user: User
#     ) -> Book:
#         """
#         Update a book with authorization and tag handling.

#         Args:
#             db: Database session
#             book_id: ID of book to update
#             book_data: Update data
#             user: User performing the update

#         Returns:
#             Updated book

#         Raises:
#             BookNotFound: If book doesn't exist
#             NotAuthorized: If user is not authorized
#         """
#         # Get existing book
#         book = await self.book_repository.get_by_id(
#             book_id=book_id, db=db, load_relationships=False
#         )

#         # Check authorization
#         self._check_authorization(user, book, "update")

#         # Handle tag updates separately
#         update_dict = book_data.model_dump(exclude={"tags"}, exclude_unset=True)

#         # Update book fields
#         if update_dict:
#             book = await self.book_repository.update(
#                 book_id=book_id, book_data=BookUpdate(**update_dict), db=db
#             )

#         # Update tags if provided
#         if book_data.tags is not None:
#             book.tags = await self._process_tags(db, book_data.tags)
#             await db.commit()
#             await db.refresh(book)

#         # Invalidate caches
#         await invalidate_cache(f"book:{book_id}")
#         await invalidate_cache(f"book:detail:{book_id}")

#         self._logger.info(
#             f"Book {book_id} updated by user {user.id}",
#             extra={"book_id": book_id, "user_id": user.id, "updates": update_dict},
#         )

#         return book

#     # --- DELETE Operations ---

#     async def delete_book(self, db: AsyncSession, book_id: int, user: User) -> None:
#         """
#         Delete a book with authorization check.

#         Args:
#             db: Database session
#             book_id: ID of book to delete
#             user: User performing the deletion

#         Raises:
#             BookNotFound: If book doesn't exist
#             NotAuthorized: If user is not authorized
#         """
#         # Get book to check authorization
#         book = await self.book_repository.get_by_id(
#             book_id=book_id, db=db, load_relationships=False
#         )

#         # Check authorization
#         self._check_authorization(user, book, "delete")

#         # Delete the book
#         await self.book_repository.delete(book_id, db)

#         # Invalidate caches
#         await invalidate_cache(f"book:{book_id}")
#         await invalidate_cache(f"book:detail:{book_id}")
#         await invalidate_cache(f"books:user:{book.user_id}")

#         self._logger.info(
#             f"Book {book_id} deleted by user {user.id}",
#             extra={"book_id": book_id, "user_id": user.id, "book_title": book.title},
#         )

#     async def bulk_delete_books(
#         self, db: AsyncSession, book_ids: List[int], user: User
#     ) -> Dict[str, Any]:
#         """
#         Delete multiple books with authorization.

#         Args:
#             db: Database session
#             book_ids: List of book IDs to delete
#             user: User performing the deletion

#         Returns:
#             Deletion results
#         """
#         results = {"deleted": [], "not_found": [], "unauthorized": [], "errors": []}

#         for book_id in book_ids:
#             try:
#                 await self.delete_book(db, book_id, user)
#                 results["deleted"].append(book_id)
#             except BookNotFound:
#                 results["not_found"].append(book_id)
#             except NotAuthorized:
#                 results["unauthorized"].append(book_id)
#             except Exception as e:
#                 results["errors"].append({"book_id": book_id, "error": str(e)})
#                 self._logger.error(f"Error deleting book {book_id}: {e}", exc_info=True)

#         return results

#     # --- Statistics ---

#     async def get_statistics(
#         self, db: AsyncSession, user: Optional[User] = None
#     ) -> Dict[str, Any]:
#         """
#         Get book statistics, optionally filtered by user.

#         Args:
#             db: Database session
#             user: Optional user for user-specific stats

#         Returns:
#             Statistics dictionary
#         """
#         # Get general statistics
#         stats = await self.book_repository.get_statistics(db)

#         # Add user-specific stats if user provided
#         if user:
#             user_books = await self.book_repository.get_by_user(
#                 user_id=user.id, db=db, skip=0, limit=1000  # Get all user's books
#             )

#             stats["user_stats"] = {
#                 "total_books": len(user_books),
#                 "languages": list(set(book.language for book in user_books)),
#                 "total_pages": sum(book.page_count for book in user_books),
#             }

#         return stats

#     # --- Helper Methods ---

#     async def _get_user_books_created_today(
#         self, user_id: int, db: AsyncSession
#     ) -> int:
#         """Get count of books created by user today."""
#         from datetime import datetime, date

#         today_start = datetime.combine(date.today(), datetime.min.time())

#         result = await db.execute(
#             select(func.count(Book.id)).where(
#                 and_(Book.user_id == user_id, Book.created_at >= today_start)
#             )
#         )

#         return result.scalar() or 0


# # Create singleton instance
# book_service = BookService()


# # Export convenience functions for backward compatibility
# async def get_all_books(db: AsyncSession) -> List[Book]:
#     """Legacy function - get all books."""
#     result = await book_service.get_all_books(db)
#     return result.items


# async def get_book_by_id(book_id: int, db: AsyncSession) -> Book:
#     """Legacy function - get book by ID."""
#     return await book_service.get_book_by_id(book_id, db)


# async def create_book(db: AsyncSession, book_data: BookCreate, user: User) -> Book:
#     """Legacy function - create book."""
#     return await book_service.create_book(db, book_data, user)


# async def update_book(
#     db: AsyncSession, book_id: int, book_data: BookUpdate, user: User
# ) -> Book:
#     """Legacy function - update book."""
#     return await book_service.update_book(db, book_id, book_data, user)


# async def delete_book(db: AsyncSession, book_id: int, user: User) -> None:
#     """Legacy function - delete book."""
#     await book_service.delete_book(db, book_id, user)


# __all__ = [
#     # Main service class
#     "BookService",
#     "book_service",
#     # Legacy functions
#     "get_all_books",
#     "get_book_by_id",
#     "create_book",
#     "update_book",
#     "delete_book",
# ]
