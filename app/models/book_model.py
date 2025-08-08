# # app/models/book_model.py
# """
# Book model definition.

# This module defines the Book SQLModel for storing book information
# and its relationships with users, tags, and reviews.
# """


from sqlmodel import SQLModel, Field, Column, DateTime, Relationship
from sqlalchemy import func
from typing import TYPE_CHECKING, Optional, List
from datetime import date, datetime
from sqlalchemy import Index, UniqueConstraint

from app.models.book_tag_model import BookTag

if TYPE_CHECKING:
    from app.models.user_model import User
    from app.models.review_model import Review
    from app.models.tag_model import Tag


class BookBase(SQLModel):

    title: str = Field(
        min_length=1,
        max_length=255,
        description="The title of the book",
        schema_extra={"example": "The Great Gatsby"},
    )
    author: str = Field(
        min_length=1,
        max_length=255,
        description="The author of the book",
        schema_extra={"example": "F. Scott Fitzgerald"},
    )
    publisher: str = Field(
        min_length=1,
        max_length=255,
        description="The publisher of the book",
        schema_extra={"example": "Charles Scribner's Sons"},
    )
    language: str = Field(
        min_length=2,
        max_length=50,
        description="The language of the book (ISO 639-1 code preferred)",
        schema_extra={"example": "en"},
    )
    page_count: int = Field(
        gt=0,
        le=10000,
        description="The number of pages in the book",
        schema_extra={"example": 180},
    )
    published_date: date = Field(
        description="The publication date of the book",
        schema_extra={"example": "1925-04-10T00:00:00"},
    )


class Book(BookBase, table=True):
    __tablename__ = "books"
    __table_args__ = (
        UniqueConstraint("title", "author", name="uq_book_title_author"),
        Index("idx_book_author", "author"),
        Index("idx_book_published_date", "published_date"),
        Index("idx_book_user_id", "user_id"),
    )

    id: Optional[int] = Field(
        default=None, primary_key=True, description="A unique constraint for Book"
    )

    user_id: Optional[int] = Field(
        default=None,
        foreign_key="users.id",
        description="Id of the User who added this Book.",
    )

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

    # Relationships
    user: Optional["User"] = Relationship(
        back_populates="books", sa_relationship_kwargs={"lazy": "joined"}
    )
    tags: List["Tag"] = Relationship(
        back_populates="books",
        link_model=BookTag,
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    reviews: List["Review"] = Relationship(
        back_populates="book",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"},
    )

    def __repr__(self) -> str:
        return f"<Book(id={self.id}, title='{self.title}', author='{self.author}')>"
