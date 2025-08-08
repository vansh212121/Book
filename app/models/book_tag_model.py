# app/models/book_tag_model.py
"""
BookTag association model.

This module defines the many-to-many relationship between books and tags.
"""

from typing import Optional
from datetime import datetime

from sqlmodel import SQLModel, Field, Column, Integer, DateTime, ForeignKey
from sqlalchemy import UniqueConstraint, Index, func


class BookTag(SQLModel, table=True):
    __tablename__ = "book_tags"
    __table_args__ = (
        UniqueConstraint("book_id", "tag_id", name="uq_book_tag"),
        Index("idx_book_tag_book_id", "book_id"),
        Index("idx_book_tag_tag_id", "tag_id"),
        Index("idx_book_tag_created_at", "created_at"),
    )

    book_id: int = Field(
        foreign_key="books.id", primary_key=True, description="Book ID"
    )
    tag_id: int = Field(foreign_key="tags.id", primary_key=True, description="Tag ID")

    # Additional metadata
    created_at: datetime = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        ),
        description="When the tag was added",
    )
    created_by: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("users.id"), nullable=True),
        description="User who added the tag",
    )

    def __repr__(self) -> str:
        return f"<BookTag(book_id={self.book_id}, tag_id={self.tag_id})>"
