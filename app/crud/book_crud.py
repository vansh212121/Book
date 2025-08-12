import logging
from typing import Optional, List, Dict, Any, TypeVar, Generic, Tuple
from abc import ABC, abstractmethod

from app.models.book_model import Book
from app.models.tag_model import Tag
from app.models.book_tag_model import BookTag

from datetime import datetime, timezone

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, and_, or_, delete
from sqlalchemy.orm import selectinload

from app.core.exception_utils import handle_exceptions
from app.core.exceptions import InternalServerError


logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository providing consistent interface for database operations."""

    def __init__(self, model: type[T]):
        self.model = model

    @abstractmethod
    async def get(self, db: AsyncSession, *, obj_id: int) -> Optional[T]:
        """Get entity by its primary key."""
        pass

    @abstractmethod
    async def create(self, db: AsyncSession, *, obj_in: Any) -> T:
        """Create a new entity."""
        pass

    @abstractmethod
    async def update(self, db: AsyncSession, *, db_obj: T, obj_in: Any) -> T:
        """Update an existing entity."""
        pass

    @abstractmethod
    async def delete(self, db: AsyncSession, *, obj_id: Any) -> None:
        """Delete an entity by its primary key."""
        pass


class BookRepository(BaseRepository[Book]):
    """Repository for all database operations related to the Book model."""

    def __init__(self):
        super().__init__(Book)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get(self, db: AsyncSession, *, obj_id: int) -> Optional[Book]:
        """Retrieves a user by their ID."""
        statement = select(self.model).where(self.model.id == obj_id)
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get_by_langs(self, db: AsyncSession, *, language: str) -> Optional[Book]:
        """Retrieves a book by Language"""
        statement = select(self.model).where(
            func.lower(self.model.language) == language.lower()
        )
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get_by_title(self, db: AsyncSession, *, title: str) -> Optional[Book]:
        """Retrieves a book by Language"""
        statement = select(self.model).where(
            func.lower(self.model.title) == title.lower()
        )
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get_by_ids(
        self, db: AsyncSession, *, obj_ids: List[int]
    ) -> Optional[Book]:
        """Retrieves multiple books by their IDs."""
        statement = select(self.model).where(self.model.id.in_(obj_ids))
        result = await db.execute(statement)
        books = result.scalars().all()

        logger.info(f"Retrieved {len(books)} books out of {len(obj_ids)} requested")
        return books

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get_users(
        self,
        db: AsyncSession,
        *,
        obj_id: int,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> Tuple[List[Book], int]:
        """Get all books created by a specific user, with filtering and pagination."""

        # 1. Start with the base query to get books for the specific user
        query = select(self.model).where(self.model.user_id == obj_id)

        # 2. Apply any additional filters
        if filters:
            query = self._apply_filters(query, filters=filters)

        # 3. Get the total count of matching books *before* pagination
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        # 4. Apply ordering
        query = self._apply_ordering(query, order_by=order_by, order_desc=order_desc)

        # 5. Apply pagination
        paginated_query = query.offset(skip).limit(limit)
        result = await db.execute(paginated_query)
        books = result.scalars().all()

        return books, total

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get_many(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> Tuple[List[Book], int]:
        """Retrieve books with filtering, search, and pagination."""

        query = select(self.model)

        # Apply filters
        if filters:
            query = self._apply_filters(query, filters=filters)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        # Apply ordering
        query = self._apply_ordering(query, order_by, order_desc)

        # Apply pagination
        paginated_query = query.offset(skip).limit(limit)
        result = await db.execute(paginated_query)
        books = result.scalars().all()

        return books, total

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get_details(self, db: AsyncSession, *, obj_id: int) -> Optional[Book]:
        """
        Retrieves a book and eagerly loads all its key relationships
        (user, tags, reviews) for a detailed view.
        """
        statement = (
            select(self.model)
            .where(self.model.id == obj_id)
            .options(
                selectinload(self.model.user),
                selectinload(self.model.tags),
                selectinload(self.model.reviews),
            )
        )
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get_all_by_tag(
        self,
        db: AsyncSession,
        *,
        tag_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[Book], int]:
        """
        Gets a paginated list of all books associated with a specific tag.
        """
        # 1. First, create a query to count the total number of books for the tag.
        #    This is a JOIN from Book -> BookTag where the tag_id matches.
        count_query = (
            select(func.count(self.model.id))
            .join(BookTag)
            .where(BookTag.tag_id == tag_id)
        )
        total = (await db.execute(count_query)).scalar_one()

        # 2. Now, create the main query to fetch the paginated book data.
        #    We also eager-load the user and tags for an efficient response.
        statement = (
            select(self.model)
            .join(BookTag)
            .where(BookTag.tag_id == tag_id)
            .order_by(self.model.title)  # A sensible default order
            .offset(skip)
            .limit(limit)
            .options(selectinload(self.model.user), selectinload(self.model.tags))
        )

        result = await db.execute(statement)
        books = result.scalars().all()

        return books, total

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get_with_tags(self, db: AsyncSession, *, obj_id: int) -> Optional[Book]:
        """
        Retrieves a book and eagerly loads its 'tags' relationship
        to prepare for a cascade delete operation.
        """
        statement = (
            select(self.model)
            .where(self.model.id == obj_id)
            .options(selectinload(self.model.tags))
        )
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def create(self, db: AsyncSession, *, obj_in: Book) -> Book:
        """Create a new user. Expects a pre-constructed User model object."""
        db.add(obj_in)
        await db.commit()
        await db.refresh(obj_in)
        self._logger.info(f"Book created: {obj_in.id}")
        return obj_in

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def update(
        self, db: AsyncSession, *, book: Book, fields_to_update: Dict[str, Any]
    ) -> Book:
        """Updates specific fields of a user object."""
        for field, value in fields_to_update.items():
            if field in {"created_at", "updated_at"} and isinstance(value, str):
                try:
                    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    value = datetime.now(timezone.utc)

            setattr(book, field, value)

        db.add(book)
        await db.commit()
        await db.refresh(book)

        self._logger.info(
            f"Book fields updated for {book.id}: {list(fields_to_update.keys())}"
        )
        return book

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def delete(self, db: AsyncSession, *, obj_id: int) -> None:
        """Permanently delete a book by ID."""
        statement = delete(self.model).where(self.model.id == obj_id)
        await db.execute(statement)
        await db.commit()
        self._logger.info(f"Book hard deleted: {obj_id}")
        return

    # Private Helper Methods
    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def exists(self, db: AsyncSession, *, obj_id: int) -> bool:
        """Check if a book exists by id"""
        statement = (
            select(func.count()).select_from(self.model).where(self.model.id == obj_id)
        )
        result = await db.execute(statement)
        return result.scalar_one() > 0

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def count(
        self, db: AsyncSession, *, filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """Count books with optional filters."""
        query = select(func.count(self.model.id))

        if filters:
            query = self._apply_filters(query, filters)

        result = await db.execute(query)
        return result.scalar_one()

    def _apply_filters(self, query, *, filters: Dict[str, Any]):
        """Apply filters to a book query."""
        if not filters:
            return query

        conditions = []

        # --- FIX: Changed all filters to use the Book model ---
        if "language" in filters and filters["language"]:
            conditions.append(self.model.language == filters["language"])

        if "author" in filters and filters["author"]:
            conditions.append(self.model.author == filters["author"])

        if "min_pages" in filters and filters["min_pages"]:
            conditions.append(self.model.page_count >= filters["min_pages"])

        if "max_pages" in filters and filters["max_pages"]:
            conditions.append(self.model.page_count <= filters["max_pages"])

        if "search" in filters and filters["search"]:
            search_term = f"%{filters['search']}%"
            conditions.append(
                or_(
                    self.model.title.ilike(search_term),
                    self.model.author.ilike(search_term),
                )
            )

        if conditions:
            query = query.where(and_(*conditions))

        return query

    def _apply_ordering(self, query, order_by: str, order_desc: bool):
        """Apply ordering to query."""
        order_column = getattr(self.model, order_by, self.model.created_at)
        if order_desc:
            return query.order_by(order_column.desc())
        else:
            return query.order_by(order_column.asc())


book_repository = BookRepository()
