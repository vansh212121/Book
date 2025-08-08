from pydantic import BaseModel

# app/schemas/review_schema.py
"""
Review schemas for request/response models.

This module defines Pydantic schemas for review-related operations,
including creation, updates, and various response formats.
"""

from typing import Optional, List, Dict, Any, Annotated, TYPE_CHECKING
from datetime import datetime, date
from enum import Enum
# from app.schemas.user_schema import UserPublicResponse
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
# if TYPE_CHECKING:
#     from app.schemas.book_schema import BookResponse



class ReviewBase(BaseModel):
    """Base schema for review data."""

    rating: Annotated[
        int, Field(ge=1, le=5, description="Rating from 1 to 5 stars", examples=[5])
    ]
    title: Optional[
        Annotated[
            str,
            Field(
                min_length=1,
                max_length=200,
                description="Title for a review",
                examples=["An excellent read!"],
            ),
        ]
    ]
    review_text: Annotated[
        str,
        Field(
            min_length=10,
            max_length=5000,
            description="Detailed review text",
            examples=["This book exceeded my expectations in every way..."],
        ),
    ]
    is_spoiler: bool = Field(
        default=False, description="Whether the review contains spoilers"
    )

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: Optional[str]) -> Optional[str]:
        """Clean and validate title."""
        if v:
            return " ".join(v.strip().split())
        return v

    @field_validator("review_text")
    @classmethod
    def clean_review_text(cls, v: str) -> str:
        """Clean and validate review text."""
        # Remove excessive whitespace
        cleaned = " ".join(v.strip().split())

        # Check minimum word count (not just characters)
        word_count = len(cleaned.split())
        if word_count < 5:
            raise ValueError("Review must contain at least 5 words")

        return cleaned


# ------CRUD SCHEMAS------
class ReviewCreate(ReviewBase):
    """Schema for creating a review."""

    book_id: int = Field(..., gt=0, description="ID of the book being reviewed")

    @model_validator(mode="after")
    def validate_review(self) -> "ReviewCreate":
        """Additional validation for review creation."""
        # Ensure title is provided for 5-star or 1-star reviews
        if self.rating in [1, 5] and not self.title:
            raise ValueError(
                f"Please provide a title for your {self.rating}-star review"
            )
        return self


class ReviewUpdate(BaseModel):
    """Schema for updating a review."""

    model_config = ConfigDict(validate_assignment=True)
    rating: Optional[
        Annotated[int, Field(ge=1, le=5, description="Updated rating", examples=[4])]
    ]
    title: Optional[
        Annotated[
            str,
            Field(
                min_length=1,
                max_length=250,
                description="Title for the review",
                examples=["A must Read"],
            ),
        ]
    ]
    review_text: Optional[
        Annotated[
            str, Field(min_length=10, max_length=500, description="Updated review text")
        ]
    ]
    is_spoiler: Optional[bool] = Field(None, description="Updated spoiler flag")

    @model_validator(mode="before")
    @classmethod
    def validate_at_least_one_field(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure at least one field is provided for update."""
        if not any(v is not None for v in values.values()):
            raise ValueError("At least one field must be provided for update")
        return values


# ----- Response Schemas ------
class ReviewResponse(ReviewBase):
    """Basic review response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Review ID")
    user_id: int = Field(..., description="Reviewer's user ID")
    book_id: int = Field(..., description="Reviewed book ID")
    helpful_count: int = Field(..., description="Number of helpful votes")
    unhelpful_count: int = Field(..., description="Number of unhelpful votes")
    is_verified_purchase: bool = Field(..., description="Verified purchase flag")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# class ReviewDetailedResponse(ReviewResponse):
#     """Detailed review response with all information."""

#     user: UserPublicResponse = Field(..., description="Reviewer information")
#     book: BookResponse = Field(..., description="Book information")

#     @property
#     def display_name(self) -> str:
#         """Get display name for reviewer."""
#         return self.user.username or self.user.full_name


# ----VOTING SCHEMA-------
class ReviewVote(BaseModel):
    """Schema for voting on review helpfulness."""

    vote_type: str = Field(
        ..., pattern="^(helpful|unhelpful)$", description="Type of vote"
    )

    @field_validator("vote_type")
    @classmethod
    def validate_vote_type(cls, v: str) -> str:
        """Normalize vote type."""
        return v.lower()


class ReviewVoteResponse(BaseModel):
    """Response after voting on a review."""

    review_id: int = Field(..., description="Review ID")
    helpful_count: int = Field(..., description="Updated helpful count")
    unhelpful_count: int = Field(..., description="Updated unhelpful count")
    user_vote: Optional[str] = Field(None, description="User's vote on this review")


# -----LIST AND SEARCH PARAMS------


# class ReviewListResponse(BaseModel):
#     """Response for paginated review list."""

#     items: List[ReviewDetailedResponse] = Field(..., description="List of reviews")
#     total: int = Field(..., ge=0, description="Total number of reviews")
#     page: int = Field(..., ge=1, description="Current page number")
#     pages: int = Field(..., ge=0, description="Total number of pages")
#     size: int = Field(..., ge=1, le=100, description="Number of items per page")

#     # Aggregate data
#     average_rating: Optional[float] = Field(
#         None, ge=1.0, le=5.0, description="Average rating across all reviews"
#     )
#     rating_distribution: Dict[int, int] = Field(
#         default_factory=dict, description="Count of reviews per rating"
#     )


class ReviewSearchParams(BaseModel):
    """Parameters for searching reviews."""

    book_id: Optional[int] = Field(None, gt=0, description="Filter by book ID")
    user_id: Optional[int] = Field(None, gt=0, description="Filter by user ID")
    rating: Optional[
        Annotated[int, Field(ge=1, le=5, description="Filter by exact rating")]
    ] = None
    min_rating: Optional[
        Annotated[int, Field(ge=1, le=5, description="Minimum rating filter")]
    ] = None
    max_rating: Optional[
        Annotated[int, Field(ge=1, le=5, description="Maximum rating filter")]
    ] = None

    is_verified_purchase: Optional[bool] = Field(
        None, description="Filter by verified purchase"
    )
    has_spoilers: Optional[bool] = Field(None, description="Filter by spoiler content")
    search: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Search in review text and title",
    )
    created_after: Optional[date] = Field(
        None, description="Reviews created after this date"
    )
    created_before: Optional[date] = Field(
        None, description="Reviews created before this date"
    )
    sort_by: Optional[str] = Field(
        "created_at",
        pattern="^(created_at|rating|helpful_count|updated_at)$",
        description="Sort field",
    )
    sort_order: Optional[str] = Field(
        "desc", pattern="^(asc|desc)$", description="Sort order"
    )

    @model_validator(mode="after")
    def validate_rating_range(self) -> "ReviewSearchParams":
        """Ensure rating range is valid."""
        if self.min_rating and self.max_rating:
            if self.min_rating > self.max_rating:
                raise ValueError("min_rating must be less than or equal to max_rating")
        return self

    @model_validator(mode="after")
    def validate_date_range(self) -> "ReviewSearchParams":
        """Ensure date range is valid."""
        if self.created_after and self.created_before:
            if self.created_after > self.created_before:
                raise ValueError("created_after must be before created_before")
        return self


__all__ = [
    # Base schemas
    "ReviewBase",
    "ReviewCreate",
    "ReviewUpdate",
    # Response schemas
    "ReviewResponse",
    # "ReviewDetailedResponse",
    # Voting
    "ReviewVote",
    "ReviewVoteResponse",
    # List and search
    "ReviewListResponse",
    "ReviewSearchParams",
]
