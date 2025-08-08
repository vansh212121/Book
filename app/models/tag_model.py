# app/models/tag_model.py
"""
Tag model definition.

This module defines the Tag model for categorizing books with
comprehensive features for tag management.
"""

from typing import List, TYPE_CHECKING, Optional
from datetime import datetime
from enum import Enum

from sqlmodel import (
    SQLModel,
    Field,
    Relationship,
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
)
from sqlalchemy import Index, UniqueConstraint, func, CheckConstraint

from app.models.book_tag_model import BookTag

if TYPE_CHECKING:
    from app.models.book_model import Book
    from app.models.user_model import User


class TagCategory(str, Enum):
    """Tag category enumeration."""

    GENRE = "genre"
    TOPIC = "topic"
    AUDIENCE = "audience"
    FORMAT = "format"
    LANGUAGE = "language"
    OTHER = "other"


class TagBase(SQLModel):
    """Base tag model with common attributes."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Tag name",
        schema_extra={"example": "science-fiction"},
    )
    display_name: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Display name (if different from name)",
        schema_extra={"example": "Science Fiction"},
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Tag description",
        schema_extra={
            "example": "Books featuring futuristic or speculative science themes"
        },
    )
    category: TagCategory = Field(default=TagCategory.OTHER, description="Tag category")
    is_official: bool = Field(
        default=False, description="Whether this is an official/curated tag"
    )


class Tag(TagBase, table=True):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("name", name="uq_tag_name"),
        Index("idx_tag_name", "name"),
        Index("idx_tag_category", "category"),
    )

    id: Optional[int] = Field(
        default=None, primary_key=True, description="Unique constraint for tags."
    )
    # Override name to ensure lowercase and unique
    name: str = Field(
        sa_column=Column(String(50), unique=True, nullable=False, index=True)
    )

    # Time stamps
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        ),
        description="Book creation timestamp",
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            server_onupdate=func.now(),  # Correctly updates on every change
            nullable=False,
        ),
        description="Book last updated timestamp",
    )

    # Creator tracking
    created_by: Optional[int] = Field(
        default=None, foreign_key="users.id", description="User who created the tag"
    )

    # Relationships
    books: List["Book"] = Relationship(
        back_populates="tags",
        link_model=BookTag,
        sa_relationship_kwargs={"lazy": "dynamic"},
    )

    created_by_user: Optional["User"] = Relationship(
        sa_relationship_kwargs={"lazy": "joined", "foreign_keys": "[Tag.created_by]"}
    )

    # Computed properties
    @property
    def display_text(self) -> str:
        """Get display text for tag."""
        return self.display_name or self.name.replace("-", " ").title()

    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, name='{self.name}', usage={self.usage_count})>"
