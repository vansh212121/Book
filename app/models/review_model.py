from typing import TYPE_CHECKING, Optional
from datetime import datetime

from sqlmodel import (
    SQLModel,
    Field,
    Relationship,
    Column,
    String,
    Integer,
    DateTime,
    Text,
)
from sqlalchemy import Index, UniqueConstraint, CheckConstraint, func

if TYPE_CHECKING:
    from app.models.user_model import User
    from app.models.book_model import Book


class ReviewBase(SQLModel):
    rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Rating from 1 to 5 stars",
        schema_extra={"example": 5},
    )
    title: Optional[str] = Field(
        min_length=1,
        max_length=50,
        description="Review title/summary",
        schema_extra={"example": "An excellent read!"},
    )
    review_text: str = Field(
        ...,
        min_length=10,
        max_length=250,
        description="Detailed review text",
        schema_extra={"example": "This book exceeded my expectations..."},
    )
    is_spoiler: bool = Field(
        default=False, description="Whether review contains spoilers"
    )
    is_verified_purchase: bool = Field(
        default=False, description="Whether reviewer purchased the book"
    )


class Review(ReviewBase, table=True):

    __tablename__ = "reviews"
    __table_args__ = (
        # Ensure one review per user per book
        UniqueConstraint("user_id", "book_id", name="uq_user_book_review"),
        # Indexes for common queries
        Index("idx_review_book_id", "book_id"),
        Index("idx_review_user_id", "user_id"),
        Index("idx_review_rating", "rating"),
        Index("idx_review_created_at", "created_at"),
        Index("idx_review_helpful", "helpful_count"),
        # Check constraints
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating"),
        CheckConstraint("helpful_count >= 0", name="ck_review_helpful_positive"),
        CheckConstraint("unhelpful_count >= 0", name="ck_review_unhelpful_positive"),
    )

    id: Optional[int] = Field(
        primary_key=True, default=None, description="Unique constraint for Review"
    )

    # Override title to use Text for longer content
    title: Optional[str] = Field(
        default=None, sa_column=Column(String(200), nullable=True)
    )

    # Override review_text to use Text type
    review_text: str = Field(sa_column=Column(Text, nullable=False))

    # Foreign keys
    user_id: int = Field(
        foreign_key="users.id", nullable=False, description="ID of the reviewer"
    )
    book_id: int = Field(
        foreign_key="books.id", nullable=False, description="ID of the reviewed book"
    )

    # Engagement metrics
    helpful_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
        description="Number of helpful votes",
    )
    unhelpful_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
        description="Number of unhelpful votes",
    )

    # Timestamps
    created_at: datetime = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        ),
        description="Review creation timestamp",
    )
    updated_at: datetime = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
        description="Last update timestamp",
    )

    # Relationships
    user: Optional["User"] = Relationship(
        back_populates="reviews",
        sa_relationship_kwargs={"lazy": "joined", "foreign_keys": "[Review.user_id]"},
    )
    book: Optional["Book"] = Relationship(
        back_populates="reviews", sa_relationship_kwargs={"lazy": "joined"}
    )

    def __repr__(self) -> str:
        return f"<Review(id={self.id}, user_id={self.user_id}, book_id={self.book_id}, rating={self.rating})>"
