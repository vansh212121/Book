import logging
from typing import Optional

from app.models.review_vote_model import ReviewVote


from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.core.exception_utils import handle_exceptions
from app.core.exceptions import InternalServerError


logger = logging.getLogger(__name__)


class ReviewVoteRepository:

    def __init__(self):
        self.model = ReviewVote
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def get(
        self, db: AsyncSession, *, user_id: int, review_id: int
    ) -> Optional[ReviewVote]:
        """Gets a specific vote by user and review ID."""
        statement = select(self.model).where(
            self.model.user_id == user_id, self.model.review_id == review_id
        )
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def create(self, db: AsyncSession, *, vote: ReviewVote) -> ReviewVote:
        """Creates a new vote."""
        db.add(vote)
        await db.commit()
        await db.refresh(vote)
        return vote

    @handle_exceptions(
        default_exception=InternalServerError,
        message="An unexpected database error occurred.",
    )
    async def delete(self, db: AsyncSession, *, vote: ReviewVote) -> None:
        """Deletes an existing vote."""
        await db.delete(vote)
        await db.commit()
        return


# Singleton instance
review_vote_repository = ReviewVoteRepository()
