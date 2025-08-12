# In app/crud/book_tag_crud.py

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_

from app.models.book_tag_model import BookTag
from app.core.exceptions import InternalServerError
from app.core.exception_utils import handle_exceptions

logger = logging.getLogger(__name__)
DB_ERROR = InternalServerError


class BookTagRepository:
    """A specialized repository for BookTag link table operations."""

    def __init__(self):
        self.model = BookTag
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get(
        self, db: AsyncSession, *, book_id: int, tag_id: int
    ) -> Optional[BookTag]:
        """Gets a specific book-tag link by its composite primary key."""
        statement = select(self.model).where(
            and_(self.model.book_id == book_id, self.model.tag_id == tag_id)
        )
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def create(self, db: AsyncSession, *, obj_in: BookTag) -> BookTag:
        """Creates a new book-tag link."""
        db.add(obj_in)
        await db.commit()
        await db.refresh(obj_in)
        return obj_in

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def delete(self, db: AsyncSession, *, db_obj: BookTag) -> None:
        """Deletes an existing book-tag link."""
        await db.delete(db_obj)
        await db.commit()
        return


# Singleton instance
book_tag_repository = BookTagRepository()
