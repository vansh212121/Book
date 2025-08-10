from typing import TYPE_CHECKING, Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint

if TYPE_CHECKING:
    from .user_model import User
    from .review_model import Review


class ReviewVote(SQLModel, table=True):
    __tablename__ = "review_votes"
    __table_args__ = (
        UniqueConstraint("user_id", "review_id", name="uq_user_review_vote"),
    )

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    review_id: int = Field(foreign_key="reviews.id", primary_key=True)
    is_helpful: bool = Field(default=True)

    # --- ADD THESE RELATIONSHIPS ---
    user: Optional["User"] = Relationship(back_populates="review_votes")
    review: Optional["Review"] = Relationship(back_populates="votes")
