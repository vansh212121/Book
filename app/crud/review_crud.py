import logging
from typing import Optional, List, Dict, Any, TypeVar, Generic, Tuple
from abc import ABC, abstractmethod

from app.models.review_model import Review

from datetime import datetime, timezone
from sqlalchemy.orm import selectinload

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, and_, or_, delete

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


class ReviewRepository(BaseRepository[Review]):
    """Abstract base repository providing consistent interface for database operations."""

    def __init__(self):
        super().__init__(Review)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get(self, db: AsyncSession, *, obj_id: int) -> Optional[Review]:
        """Get a review by its id"""

        statement = select(self.model).where(self.model.id == obj_id)
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get_by_user_and_books(
        self, db: AsyncSession, *, user_id: int, book_id: int
    ) -> Optional[Review]:
        """Get review by user and book (unique constraint)."""

        statement = (
            select(self.model)
            .where(and_(self.model.user_id == user_id, self.model.book_id == book_id))
            .options(selectinload(self.model.user), selectinload(self.model.book))
        )

        result = await db.execute(statement)

        return result.scalar_one_or_none()

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get_book_reviews(
        self, db: AsyncSession, *, book_id: int
    ) -> Optional[List[Review]]:
        """Get reviews for a book"""
        statement = select(Review).where(self.model.book_id == book_id)
        result = await db.execute(statement)
        return result.scalars().all()

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get_user_reviews(
        self, db: AsyncSession, *, user_id: int
    ) -> Optional[List[Review]]:
        """Get logged in users reviews"""

        statement = select(self.model).where(self.model.user_id == user_id)
        result = await db.execute(statement)
        return result.scalars().all()

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
    ) -> Tuple[List[Review], int]:
        """Retrieve reviews with filtering, search, and pagination."""
        query = select(self.model)

        if filters:
            query = self._apply_filters(query, filters=filters)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        # Apply ordering
        query = self._apply_ordering(query, order_by, order_desc)

        # Apply pagination
        paginated_query = (
            query.offset(skip)
            .limit(limit)
            .options(
                selectinload(self.model.user), 
                selectinload(self.model.book)
            )
        )
        result = await db.execute(paginated_query)
        reviews = result.scalars().all()

        return reviews, total

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get_by_title(self, db: AsyncSession, *, title: str) -> Optional[Review]:
        """Retrieves a review by Title"""
        statement = select(self.model).where(
            func.lower(self.model.title) == title.lower()
        )
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    # CRUD
    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def create(self, db: AsyncSession, *, obj_in: Review) -> Review:
        """Create a reveiw"""

        db.add(obj_in)
        await db.commit()
        await db.refresh(obj_in)
        self._logger.info(f"Review created: {obj_in.id}")
        return obj_in

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def update(
        self, db: AsyncSession, *, review: Review, fields_to_update: Dict[str, Any]
    ):
        """Update a review"""
        for field, value in fields_to_update.items():
            if field in {"created_at", "updated_at"} and isinstance(value, str):
                try:
                    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    value = datetime.now(timezone.utc)

            setattr(review, field, value)

        db.add(review)
        await db.commit()
        await db.refresh(review)

        self._logger.info(
            f"Review fields updated for {review.id}: {list(fields_to_update.keys())}"
        )
        return review

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def delete(self, db: AsyncSession, *, obj_id: int) -> None:
        """Delete a review"""
        statement = delete(self.model).where(self.model.id == obj_id)
        await db.execute(statement)
        await db.commit()
        self._logger.info(f"Review hard deleted: {obj_id}")
        return

    def _apply_filters(self, query, *, filters: Dict[str, Any]):
        """Apply filters to a review query."""
        if not filters:
            return query

        conditions = []
        
        if "book_id" in filters and filters["book_id"]:
            conditions.append(self.model.book_id == filters["book_id"])

        if "user_id" in filters and filters["user_id"]:
            conditions.append(self.model.user_id == filters["user_id"])

        # --- Boolean Filters ---
        if "is_spoiler" in filters and filters["is_spoiler"] is not None:
            conditions.append(self.model.is_spoiler == filters["is_spoiler"])

        if (
            "is_verified_purchase" in filters
            and filters["is_verified_purchase"] is not None
        ):
            conditions.append(
                self.model.is_verified_purchase == filters["is_verified_purchase"]
            )

        # --- Count Filters (filtering for a minimum count) ---
        if "min_helpful_count" in filters and filters["min_helpful_count"] is not None:
            conditions.append(self.model.helpful_count >= filters["min_helpful_count"])

        if (
            "min_unhelpful_count" in filters
            and filters["min_unhelpful_count"] is not None
        ):
            conditions.append(
                self.model.unhelpful_count >= filters["min_unhelpful_count"]
            )

        # --- Search Filter (Corrected for Review model) ---
        if "search" in filters and filters["search"]:
            search_term = f"%{filters['search']}%"
            conditions.append(
                or_(
                    self.model.title.ilike(search_term),
                    self.model.review_text.ilike(search_term),
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


review_repository = ReviewRepository()
