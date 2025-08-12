import logging
from typing import Optional, List, Dict, Any, TypeVar, Generic, Tuple
from abc import ABC, abstractmethod
from sqlalchemy import text

from app.models.tag_model import Tag


from datetime import datetime, timezone

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


class TagRepository(BaseRepository[Tag]):
    """Repository for all database operations related to the Book model."""

    def __init__(self):
        super().__init__(Tag)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get(self, db: AsyncSession, *, obj_id: int) -> Optional[Tag]:
        """Get tags by id"""

        statement = select(self.model).where(self.model.id == obj_id)
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get_by_name(self, db: AsyncSession, *, name: str) -> Optional[Tag]:
        """Fetch Tags by their Name"""

        statement = select(self.model).where(self.model.name == name)
        result = await db.execute(statement)
        return result.scalar_one_or_none()

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
    ) -> Tuple[List[Tag], int]:
        """Retrieve tags with filtering, search, and pagination."""

        query = select(self.model)

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
        tags = result.scalars().all()

        return tags, total

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def create(self, db: AsyncSession, *, obj_in: Tag) -> Tag:
        """create a tag"""

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
        self, db: AsyncSession, *, tag: Tag, fields_to_update: Dict[str, Any]
    ) -> Tag:
        """Update a Tag"""

        for field, value in fields_to_update.items():
            if field in {"created_at", "updated_at"} and isinstance(value, str):
                try:
                    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    value = datetime.now(timezone.utc)

            setattr(tag, field, value)

        db.add(tag)
        await db.commit()
        await db.refresh(tag)

        self._logger.info(
            f"Tag fields updated for {tag.id}: {list(fields_to_update.keys())}"
        )
        return tag

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def delete(self, db: AsyncSession, *, obj_id: int) -> None:
        """Permanently delete a tag by ID."""
        statement = delete(self.model).where(self.model.id == obj_id)
        await db.execute(statement)
        await db.commit()
        self._logger.info(f"Tag hard deleted: {obj_id}")
        return

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get_related_by_co_occurrence(
        self, db: AsyncSession, *, tag_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Executes an optimized query to find related tags based on co-occurrence.
        """
        # --- THE FIX IS HERE: The SQL query now casts the enum to text ---
        sql_query = text(
            """
            SELECT 
                t.id, 
                t.name, 
                t.display_name, 
                -- FIX: Cast the enum to TEXT before applying LOWER()
                LOWER(t.category::TEXT) as category, 
                t.is_official,
                t.created_at,
                t.updated_at,
                COUNT(bt2.book_id) as co_occurrence
            FROM tags t
            JOIN book_tags bt2 ON t.id = bt2.tag_id
            WHERE bt2.book_id IN (
                SELECT book_id FROM book_tags WHERE tag_id = :tag_id
            )
            AND t.id != :tag_id
            GROUP BY t.id, t.name, t.display_name, t.category, t.is_official, t.created_at, t.updated_at
            ORDER BY co_occurrence DESC
            LIMIT :limit
            """
        )

        result = await db.execute(
            sql_query,
            {"tag_id": tag_id, "limit": limit},
        )

        # Convert the raw result rows into a list of dictionaries
        return [row._asdict() for row in result]

    # ========== Helpers ==========
    def _apply_filters(self, query, *, filters: Dict[str, Any]):
        """Apply filters to a review query."""
        if not filters:
            return query

        conditions = []

        if "category" in filters and filters["category"] is not None:
            conditions.append(self.model.category == filters["category"])

        if "name" in filters and filters["name"] is not None:
            conditions.append(self.model.name == filters["name"])

        if "display_name" in filters and filters["display_name"] is not None:
            conditions.append(self.model.display_name == filters["display_name"])

        if "is_official" in filters and filters["is_official"] is not None:
            # Correctly compare the 'is_official' column with the boolean value
            conditions.append(self.model.is_official == filters["is_official"])

        if "created_by" in filters and filters["created_by"] is not None:
            # Correctly compare the 'is_official' column with the boolean value
            conditions.append(self.model.created_by == filters["created_by"])

        if "category" in filters and filters["category"] is not None:
            conditions.append(self.model.category == filters["category"])

        # --- Search Filter (Corrected for Review model) ---
        if "search" in filters and filters["search"]:
            search_term = f"%{filters['search']}%"
            conditions.append(
                or_(
                    self.model.name.ilike(search_term),
                    self.model.display_name.ilike(search_term),
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


tag_repository = TagRepository()
