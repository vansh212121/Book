import logging
from typing import Optional, Dict, Any, List

from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, timezone
from app.crud.book_crud import book_repository
from app.crud.tag_crud import tag_repository
from app.schemas.book_schema import (
    BookCreate,
    BookUpdate,
    BookResponseDetailed,
    BookListResponse,
)
from app.models.user_model import User
from app.models.book_model import Book
from app.models.book_tag_model import BookTag

from app.services.tag_service import tag_service
from sqlalchemy import delete

from app.services.cache_service import cache_service
from app.core.exception_utils import raise_for_status
from app.core.exceptions import (
    ResourceNotFound,
    NotAuthorized,
    ValidationError,
    ResourceAlreadyExists,
)

logger = logging.getLogger(__name__)


class BookService:
    """
    Enhanced book service with business logic and authorization.

    This service extends the base CRUD service with additional
    business rules, authorization checks, and tag management.
    """

    def __init__(self):
        """
        Initializes the UserService.
        This version has no arguments, making it easy for FastAPI to use,
        while still allowing for dependency injection during tests.
        """
        self.book_repository = book_repository
        self.tag_repository = tag_repository
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def _process_and_link_tags(
        self, db: AsyncSession, *, book: Book, tag_names: List[str], current_user: User
    ) -> Book:
        # Remove all existing links first

        statement = delete(BookTag).where(BookTag.book_id == book.id)
        await db.execute(statement)

        if tag_names:
            for tag_name in tag_names:
                tag = await tag_service.get_or_create_tag(
                    db=db, tag_name=tag_name, current_user=current_user
                )
                link = BookTag(
                    book_id=book.id, tag_id=tag.id, created_by=current_user.id
                )
                db.add(link)

        await db.commit()
        await db.refresh(book, attribute_names=["tags"])
        return book

    def _check_authorization(self, current_user: User, book: Book, action: str) -> None:
        """
        Check if user is authorized to perform action on book.
        """
        # Admins can do anything
        if current_user.is_admin:
            return

        # Users can only modify their own Books
        is_not_self = book.user_id != current_user.id
        raise_for_status(
            condition=is_not_self,
            exception=NotAuthorized,
            detail=f"You are not authorized to {action} this user.",
        )

    # ======= READ OPERATIONS =======
    async def get_book_by_id(self, db: AsyncSession, *, book_id: int) -> Optional[Book]:
        """Get Book By it ID"""
        if book_id <= 0:
            raise ValidationError("Book ID must be a positive integer")

        cached_book = await cache_service.get(Book, book_id)
        if cached_book:
            book = await db.merge(cached_book)
        else:
            book = await book_repository.get(db=db, obj_id=book_id)
            raise_for_status(
                condition=book is None,
                exception=ResourceNotFound,
                resource_type="Book",
                detail=f"Book with id {book_id} not found.",
            )

            await cache_service.set(book)

        return book

    async def get_by_ids(self, db: AsyncSession, *, book_ids: List[int]) -> List[Book]:
        """
        Fetches the full details for a list of book IDs.
        """
        if not book_ids:
            return []
        return await book_repository.get_by_ids(db=db, obj_ids=book_ids)

    async def get_user_books(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at",
        order_desc: bool = True,
    ):
        """
        Get books owned by the current authenticated user.
        """
        books, total = await book_repository.get_users(
            db=db,
            obj_id=user_id,
            skip=skip,
            limit=limit,
            filters=filters,
            order_by=order_by,
            order_desc=order_desc,
        )

        raise_for_status(
            condition=books is None,
            exception=ResourceNotFound,
            resource_type="Book",
            detail=f"Books for user with user_id:{user_id} not Found.",
        )

        # Calculate pagination info
        page = (skip // limit) + 1
        total_pages = (total + limit - 1) // limit  # Ceiling division

        # Construct the response schema
        response = BookListResponse(
            items=books, total=total, page=page, pages=total_pages, size=limit
        )

        self._logger.info(f"Book list retrieved : {len(books)} books returned")
        return response

    async def get_books(
        self,
        *,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> BookListResponse:
        """Get all books with optional filtering and pagination."""

        # Input validation
        if skip < 0:
            raise ValidationError("Skip parameter must be non-negative")
        if limit <= 0 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")

        books, total = await book_repository.get_many(
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
        response = BookListResponse(
            items=books, total=total, page=page, pages=total_pages, size=limit
        )

        self._logger.info(f"Book list retrieved : {len(books)} books returned")
        return response

    async def get_book_details(
        self, db: AsyncSession, *, book_id: int
    ) -> BookResponseDetailed:
        """
        Gets a book by its ID, calculates statistics, and returns the detailed response.
        """
        if book_id <= 0:
            raise ValidationError("Book ID must be a positive integer")

        # Caching a detailed object with all relationships can be complex.
        # For simplicity and to always show the latest reviews, we will bypass the cache
        # for this specific detailed view and fetch directly from the DB.

        # 1. Use our new high-performance repository method
        book = await self.book_repository.get_details(db=db, obj_id=book_id)

        raise_for_status(
            condition=(book is None),
            exception=ResourceNotFound,
            resource_type="Book",
            detail=f"Book with id{book_id} not found.",
        )

        # 2. Perform business logic: calculate statistics
        review_count = len(book.reviews)
        average_rating = 0.0
        if review_count > 0:
            total_rating = sum(review.rating for review in book.reviews)
            average_rating = round(total_rating / review_count, 2)

        # 3. Construct the final, detailed response schema
        #    This perfectly matches what the API endpoint's response_model expects.
        return BookResponseDetailed(
            id=book.id,
            user_id=book.user_id,
            created_at=book.created_at,
            updated_at=book.updated_at,
            title=book.title,
            author=book.author,
            publisher=book.publisher,
            language=book.language,
            page_count=book.page_count,
            published_date=book.published_date,
            tags=book.tags,
            reviews=book.reviews,
            user=book.user,  # Pass the user object directly
            average_rating=average_rating,
            review_count=review_count,
        )

    async def get_books_by_tag(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> BookListResponse:
        """"""

        # Input validation
        if skip < 0:
            raise ValidationError("Skip parameter must be non-negative")
        if limit <= 0 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")

        books, total = await book_repository.get_all_by_tag(
            db=db,
            skip=skip,
            limit=limit,
        )

        # Calculate pagination info
        page = (skip // limit) + 1
        total_pages = (total + limit - 1) // limit  # Ceiling division

        # Construct the response schema
        response = BookListResponse(
            items=books, total=total, page=page, pages=total_pages, size=limit
        )

        self._logger.info(f"Book list retrieved : {len(books)} books returned")
        return response

    async def create_book(
        self, db: AsyncSession, *, book_data: BookCreate, current_user: User
    ) -> Book:
        """Create a book"""

        # Check for conflicts
        existing_book = await book_repository.get_by_title(db=db, title=book_data.title)
        raise_for_status(
            condition=existing_book is not None,
            exception=ResourceAlreadyExists,
            detail=f"Book with title '{book_data.title}' already exists.",
            resource_type="Book",
        )

        # Prepare the book model
        book_dict = book_data.model_dump(exclude={"tags"})
        book_dict["created_at"] = datetime.now(timezone.utc)
        book_dict["updated_at"] = datetime.now(timezone.utc)
        book_dict["user_id"] = current_user.id

        book_to_create = Book(**book_dict)
        #  3. Delegate creation to the repository
        new_book = await self.book_repository.create(db=db, obj_in=book_to_create)
        await db.refresh(new_book)

        # 4. If tags were provided, process and link them
        if book_data.tags:
            new_book = await self._process_and_link_tags(
                db=db,
                book=new_book,
                tag_names=book_data.tags,
                current_user=current_user,
            )

        self._logger.info(f"New book created: {new_book.title}")

        return new_book

    async def update_book(
        self,
        db: AsyncSession,
        *,
        book_id_to_update: int,
        book_data: BookUpdate,
        current_user: User,
    ) -> Book:
        """Book update using book_id"""

        if book_id_to_update <= 0:
            raise ValidationError("Book ID must be a positive integer")

        book_to_update = await self.get_book_by_id(db=db, book_id=book_id_to_update)

        self._check_authorization(
            current_user=current_user, book=book_to_update, action="update"
        )

        await self._validate_book_update(db, book_data, book_to_update)

        update_dict = book_data.model_dump(
            exclude={"tags"}, exclude_unset=True, exclude_none=True
        )

        # Remove timestamp fields that should not be manually updated
        for ts_field in {"created_at", "updated_at"}:
            update_dict.pop(ts_field, None)

        updated_book = await self.book_repository.update(
            db=db,
            book=book_to_update,
            fields_to_update=update_dict,
        )

        if book_data.tags is not None:
            book_to_update = await self._process_and_link_tags(
                db=db,
                book=book_to_update,
                tag_names=book_data.tags,
                current_user=current_user,
            )

        await cache_service.invalidate(Book, book_id_to_update)

        self._logger.info(
            f"Book {book_id_to_update} updated by {current_user.id}",
            extra={
                "updated_book_id": book_id_to_update,
                "updated_fields": list(update_dict.keys()),
            },
        )
        return updated_book

    async def delete_book(
        self, db: AsyncSession, *, book_id_to_delete: int, current_user: User
    ) -> Dict[str, str]:
        """Hard deleting a book by its ID"""

        # Input validation
        if book_id_to_delete <= 0:
            raise ValidationError("Book ID must be a positive integer")

        # 1. Fetch the user to delete
        book_to_delete = await self.get_book_by_id(db, book_id=book_id_to_delete)

        # 2. Perform authorization check
        self._check_authorization(
            current_user=current_user,
            book=book_to_delete,
            action="delete",
        )

        # 3. Business rules validation
        await self._validate_book_deletion(book_to_delete, current_user)

        # 4. Perform the deletion
        await self.book_repository.delete(db=db, obj_id=book_id_to_delete)

        # 5. Clean up cache and tokens
        await cache_service.invalidate(Book, book_id_to_delete)
        # TODO: Add token revocation logic here

        self._logger.warning(
            f"User {book_id_to_delete} permanently deleted by {current_user.id}",
            extra={
                "deleted_book_id": book_id_to_delete,
                "deleter_id": current_user.id,
                "deleted_book_title": book_to_delete.title,
            },
        )

        return {"message": "Book deleted successfully"}

    async def transfer_ownership(
        self, db: AsyncSession, *, book_id: int, new_owner_id: int, admin_user: User
    ) -> Book:
        """Transfers book ownership to another user (admin only)."""
        if not admin_user.is_admin:
            raise NotAuthorized("Only admins can transfer book ownership")

        book = await self.get_book_by_id(db=db, book_id=book_id)

        # --- THE FIX IS HERE: Use the new repository method with a simple dictionary ---
        updated_book = await self.book_repository.update(
            db=db, book=book, fields_to_update={"user_id": new_owner_id}
        )

        await cache_service.invalidate(Book, book_id)

        self._logger.info(
            f"Admin {admin_user.id} transferred book {book_id} to user {new_owner_id}"
        )
        return updated_book

    # Helper Functions
    async def _validate_book_update(
        self, db: AsyncSession, book_data: BookUpdate, existing_book: Book
    ) -> None:
        """Validates user update data for potential conflicts."""

        if book_data.title and book_data.title != existing_book.title:
            if await self.book_repository.get_by_title(db=db, title=book_data.title):
                raise ResourceAlreadyExists("Title is already in use")

    async def _validate_book_deletion(
        self, book_to_delete: Book, current_user: User
    ) -> None:

        # Prevent self-deletion
        if current_user.id != book_to_delete.user_id:
            raise ValidationError("Users cannot delete other's Book.")


book_service = BookService()
