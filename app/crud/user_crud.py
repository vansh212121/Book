# -----CLAUDE CODE------
import logging
from typing import Optional, List, Dict, Any, TypeVar, Generic, Tuple
from abc import ABC, abstractmethod

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, and_, or_, delete

from app.core.exception_utils import handle_exceptions
from app.core.exceptions import InternalServerError

from app.models.user_model import User
from app.schemas.user_schema import UserCreate, UserUpdate

logger = logging.getLogger(__name__)

T = TypeVar("T")
DB_ERROR = InternalServerError(detail="An unexpected database error occurred.")


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository providing consistent interface for database operations."""
    
    def __init__(self, model: type[T]):
        self.model = model

    @abstractmethod
    async def get(self, db: AsyncSession, *, obj_id: Any) -> Optional[T]:
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


class UserRepository(BaseRepository[User]):
    """Repository for all database operations related to the User model."""
    
    def __init__(self):
        super().__init__(User)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @handle_exceptions(default_exception=DB_ERROR)
    async def get(self, db: AsyncSession, *, obj_id: int) -> Optional[User]:
        """Retrieves a user by their ID."""
        statement = select(self.model).where(self.model.id == obj_id)
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @handle_exceptions(default_exception=DB_ERROR)
    async def get_by_email(self, db: AsyncSession, *, email: str) -> Optional[User]:
        """Retrieves a user by their email address (case-insensitive)."""
        statement = select(self.model).where(func.lower(self.model.email) == email.lower())
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @handle_exceptions(default_exception=DB_ERROR)
    async def get_by_username(self, db: AsyncSession, *, username: str) -> Optional[User]:
        """Retrieves a user by their username (case-insensitive)."""
        statement = select(self.model).where(func.lower(self.model.username) == username.lower())
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @handle_exceptions(default_exception=DB_ERROR)
    async def get_all(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> Tuple[List[User], int]:
        """Get multiple users with filtering and pagination."""
        query = select(self.model)

        # Apply filters
        if filters:
            query = self._apply_filters(query, filters)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar_one()

        # Apply ordering
        query = self._apply_ordering(query, order_by, order_desc)

        # Apply pagination
        paginated_query = query.offset(skip).limit(limit)
        result = await db.execute(paginated_query)
        users = result.scalars().all()
        
        return users, total

    @handle_exceptions(default_exception=DB_ERROR)
    async def count(self, db: AsyncSession, *, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count users with optional filters."""
        query = select(func.count(self.model.id))
        
        if filters:
            query = self._apply_filters(query, filters)
            
        result = await db.execute(query)
        return result.scalar_one()

    @handle_exceptions(default_exception=DB_ERROR)
    async def create(self, db: AsyncSession, *, obj_in: UserCreate) -> User:
        """Create a new user."""
        db_obj = self.model.model_validate(obj_in)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        
        self._logger.info(f"User created: {db_obj.id}")
        return db_obj

    @handle_exceptions(default_exception=DB_ERROR)
    async def update(self, db: AsyncSession, *, db_obj: User, obj_in: UserUpdate) -> User:
        """Update an existing user."""
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        
        self._logger.info(f"User updated: {db_obj.id}")
        return db_obj

    # @handle_exceptions(default_exception=DB_ERROR)
    # async def update_fields(self, db: AsyncSession, *, obj_id: int, fields: Dict[str, Any]) -> Optional[User]:
    #     """Update specific fields of a user by ID."""
    #     db_obj = await self.get(db, obj_id=obj_id)
    #     if not db_obj:
    #         return None
            
    #     for field, value in fields.items():
    #         if hasattr(db_obj, field):
    #             setattr(db_obj, field, value)
        
    #     db.add(db_obj)
    #     await db.commit()
    #     await db.refresh(db_obj)
        
    #     self._logger.info(f"User fields updated: {db_obj.id}, fields: {list(fields.keys())}")
    #     return db_obj

    @handle_exceptions(default_exception=DB_ERROR)
    async def delete(self, db: AsyncSession, *, obj_id: int) -> None:
        """Permanently delete a user by ID."""
        statement = delete(self.model).where(self.model.id == obj_id)
        await db.execute(statement)
        await db.commit()
        self._logger.info(f"User hard deleted: {obj_id}")
        return


    # --- Helper & Efficiency Methods ---
    
    @handle_exceptions(default_exception=DB_ERROR)
    async def exists(self, db: AsyncSession, *, obj_id: int) -> bool:
        """Check if a user exists by ID."""
        statement = select(func.count(self.model.id)).where(self.model.id == obj_id)
        result = await db.execute(statement)
        return result.scalar_one() > 0

    @handle_exceptions(default_exception=DB_ERROR)
    async def exists_by_email(self, db: AsyncSession, *, email: str) -> bool:
        """Check if a user exists by email."""
        statement = select(func.count(self.model.id)).where(
            func.lower(self.model.email) == email.lower()
        )
        result = await db.execute(statement)
        return result.scalar_one() > 0

    @handle_exceptions(default_exception=DB_ERROR)
    async def exists_by_username(self, db: AsyncSession, *, username: str) -> bool:
        """Check if a user exists by username."""
        statement = select(func.count(self.model.id)).where(
            func.lower(self.model.username) == username.lower()
        )
        result = await db.execute(statement)
        return result.scalar_one() > 0

    def _apply_filters(self, query, filters: Dict[str, Any]):
        """Apply filters to query."""
        conditions = []

        if "role" in filters and filters["role"]:
            conditions.append(User.role == filters["role"])

        if "is_active" in filters and filters["is_active"] is not None:
            conditions.append(User.is_active == filters["is_active"])

        if "is_verified" in filters and filters["is_verified"] is not None:
            conditions.append(User.is_verified == filters["is_verified"])

        if "search" in filters and filters["search"]:
            search_term = f"%{filters['search']}%"
            conditions.append(
                or_(
                    User.email.ilike(search_term),
                    User.username.ilike(search_term),
                    User.full_name.ilike(search_term),
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

user_repository = UserRepository()