# # app/schemas/book_schema.py
# """
# Book schemas for request/response models.

# This module defines Pydantic schemas for book-related operations,
# including creation, updates, and various response formats.
# """

# from datetime import date, datetime
# from typing import Optional, List, Dict, Any
# from enum import Enum

# from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
# from pydantic.types import conint

# from app.schemas.tag_schema import TagResponse
# from app.schemas.user_schema import UserBasicResponse
# from app.schemas.review_schema import ReviewResponse


# class BookLanguage(str, Enum):
#     """Supported book languages."""

#     ENGLISH = "en"
#     SPANISH = "es"
#     FRENCH = "fr"
#     GERMAN = "de"
#     ITALIAN = "it"
#     PORTUGUESE = "pt"
#     RUSSIAN = "ru"
#     JAPANESE = "ja"
#     CHINESE = "zh"
#     KOREAN = "ko"
#     OTHER = "other"


# class BookBase(BaseModel):
#     """Base schema for book data."""

#     title: str = Field(
#         ...,
#         min_length=1,
#         max_length=255,
#         description="The title of the book",
#         examples=["The Great Gatsby"],
#     )
#     author: str = Field(
#         ...,
#         min_length=1,
#         max_length=255,
#         description="The author of the book",
#         examples=["F. Scott Fitzgerald"],
#     )
#     publisher: str = Field(
#         ...,
#         min_length=1,
#         max_length=255,
#         description="The publisher of the book",
#         examples=["Charles Scribner's Sons"],
#     )
#     language: str = Field(
#         ...,
#         min_length=2,
#         max_length=50,
#         description="The language of the book",
#         examples=["en"],
#     )
#     page_count: conint(gt=0, le=10000) = Field(
#         ..., description="The number of pages in the book", examples=[180]
#     )
#     published_date: date = Field(
#         ..., description="The publication date of the book", examples=["1925-04-10"]
#     )

#     @field_validator("title", "author", "publisher")
#     @classmethod
#     def strip_whitespace(cls, v: str) -> str:
#         """Strip leading and trailing whitespace."""
#         return v.strip()

#     @field_validator("language")
#     @classmethod
#     def validate_language(cls, v: str) -> str:
#         """Validate and normalize language code."""
#         return v.lower().strip()

#     @field_validator("published_date")
#     @classmethod
#     def validate_published_date(cls, v: date) -> date:
#         """Ensure published date is not in the future."""
#         if v > date.today():
#             raise ValueError("Published date cannot be in the future")
#         return v


# class BookCreate(BookBase):
#     """Schema for creating a new book."""

#     tags: Optional[List[str]] = Field(
#         default=None,
#         min_items=0,
#         max_items=10,
#         description="List of tag names to associate with the book",
#         examples=[["fiction", "classic", "american-literature"]],
#     )

#     @field_validator("tags")
#     @classmethod
#     def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
#         """Validate and normalize tags."""
#         if v is None:
#             return v

#         # Remove duplicates and normalize
#         normalized_tags = []
#         seen = set()

#         for tag in v:
#             normalized = tag.strip().lower()
#             if normalized and normalized not in seen:
#                 seen.add(normalized)
#                 normalized_tags.append(normalized)

#         return normalized_tags if normalized_tags else None


# class BookUpdate(BaseModel):
#     """Schema for updating a book."""

#     model_config = ConfigDict(validate_assignment=True)

#     title: Optional[str] = Field(
#         None, min_length=1, max_length=255, description="The title of the book"
#     )
#     author: Optional[str] = Field(
#         None, min_length=1, max_length=255, description="The author of the book"
#     )
#     publisher: Optional[str] = Field(
#         None, min_length=1, max_length=255, description="The publisher of the book"
#     )
#     language: Optional[str] = Field(
#         None, min_length=2, max_length=50, description="The language of the book"
#     )
#     page_count: Optional[conint(gt=0, le=10000)] = Field(
#         None, description="The number of pages in the book"
#     )
#     published_date: Optional[date] = Field(
#         None, description="The publication date of the book"
#     )
#     tags: Optional[List[str]] = Field(
#         None,
#         min_items=0,
#         max_items=10,
#         description="List of tag names to associate with the book",
#     )

#     @model_validator(mode="before")
#     @classmethod
#     def validate_at_least_one_field(cls, values: Dict[str, Any]) -> Dict[str, Any]:
#         """Ensure at least one field is provided for update."""
#         if not any(v is not None for v in values.values()):
#             raise ValueError("At least one field must be provided for update")
#         return values

#     # Apply same validators as BookBase
#     _strip_whitespace = field_validator("title", "author", "publisher")(
#         BookBase.strip_whitespace
#     )
#     _validate_language = field_validator("language")(BookBase.validate_language)
#     _validate_published_date = field_validator("published_date")(
#         BookBase.validate_published_date
#     )
#     _validate_tags = field_validator("tags")(BookCreate.validate_tags)


# class BookResponse(BookBase):
#     """Basic book response schema."""

#     model_config = ConfigDict(from_attributes=True)

#     id: int = Field(..., description="Unique identifier for the book")
#     user_id: int = Field(..., description="ID of the user who added the book")
#     created_at: datetime = Field(..., description="When the book was created")
#     updated_at: datetime = Field(..., description="When the book was last updated")

# class BookBasicResponse(BaseModel):
#     """Minimal book response for inclusion in other schemas."""
    
#     model_config = ConfigDict(from_attributes=True)
    
#     id: int = Field(..., description="Unique identifier for the book")
#     title: str = Field(..., description="The title of the book")
#     author: str = Field(..., description="The author of the book")
#     published_date: date = Field(..., description="The publication date")
    
# class BookResponseWithTags(BookResponse):
#     """Book response with associated tags."""

#     tags: List[TagResponse] = Field(
#         default_factory=list, description="Tags associated with this book"
#     )


# class BookResponseWithUser(BookResponseWithTags):
#     """Book response with user information."""

#     user: UserBasicResponse = Field(..., description="User who added this book")


# class BookResponseDetailed(BookResponseWithUser):
#     """Detailed book response with reviews."""

#     reviews: List[ReviewResponse] = Field(
#         default_factory=list, description="Reviews for this book"
#     )
#     average_rating: Optional[float] = Field(
#         None, ge=1.0, le=5.0, description="Average rating from all reviews"
#     )
#     review_count: int = Field(default=0, ge=0, description="Total number of reviews")


# class BookListResponse(BaseModel):
#     """Response schema for paginated book list."""

#     items: List[BookResponseWithTags] = Field(..., description="List of books")
#     total: int = Field(..., ge=0, description="Total number of books")
#     page: int = Field(..., ge=1, description="Current page number")
#     pages: int = Field(..., ge=0, description="Total number of pages")
#     size: int = Field(..., ge=1, le=100, description="Number of items per page")


# class BookSearchParams(BaseModel):
#     """Parameters for searching books."""

#     query: Optional[str] = Field(
#         None,
#         min_length=1,
#         max_length=100,
#         description="Search query for title or author",
#     )
#     author: Optional[str] = Field(
#         None, min_length=1, max_length=255, description="Filter by author"
#     )
#     language: Optional[str] = Field(
#         None, min_length=2, max_length=50, description="Filter by language"
#     )
#     tags: Optional[List[str]] = Field(
#         None, min_items=1, max_items=10, description="Filter by tags"
#     )
#     published_after: Optional[date] = Field(
#         None, description="Filter books published after this date"
#     )
#     published_before: Optional[date] = Field(
#         None, description="Filter books published before this date"
#     )
#     min_pages: Optional[conint(gt=0)] = Field(
#         None, description="Minimum number of pages"
#     )
#     max_pages: Optional[conint(gt=0)] = Field(
#         None, description="Maximum number of pages"
#     )

#     @model_validator(mode="after")
#     def validate_date_range(self) -> "BookSearchParams":
#         """Ensure date range is valid."""
#         if self.published_after and self.published_before:
#             if self.published_after > self.published_before:
#                 raise ValueError("published_after must be before published_before")
#         return self
