# app/schemas/tag_schema.py
"""
Tag schemas for request/response models.

This module defines Pydantic schemas for tag-related operations,
including creation, updates, and various response formats.
"""

from typing import Optional, List, Dict, Any, Annotated
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

from app.models.tag_model import TagCategory


# ------ Base Schemas ------
class TagBase(BaseModel):
    """Base schema for tag data."""

    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=50,
            pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
            description="Tag name (lowercase, hyphenated)",
            examples=["science-fiction", "young-adult", "historical-fiction"],
        ),
    ]
    display_name: Optional[
        Annotated[
            str,
            Field(
                max_length=50,
                description="Display name for UI",
                examples=["Science Fiction", "Young Adult", "Historical Fiction"],
            ),
        ]
    ] = None
    description: Optional[
        Annotated[
            str,
            Field(
                max_length=500,
                description="Tag description",
                examples=["Books featuring futuristic or speculative science themes"],
            ),
        ]
    ] = None
    category: TagCategory = Field(default=TagCategory.OTHER, description="Tag category")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and normalize tag name."""
        # Convert to lowercase
        v = v.lower().strip()

        # Replace spaces with hyphens
        v = v.replace(" ", "-")

        # Remove multiple consecutive hyphens
        while "--" in v:
            v = v.replace("--", "-")

        # Remove leading/trailing hyphens
        v = v.strip("-")

        return v


# ------ CRUD Schemas -------
class TagCreate(TagBase):
    """Schema for creating a new tag."""

    is_official: bool = Field(
        default=False, description="Mark as official tag (admin only)"
    )


class TagUpdate(BaseModel):
    """Schema for updating a tag."""

    model_config = ConfigDict(validate_assignment=True)

    name: Optional[Annotated[str, Field(max_length=50, description="Updated name")]] = (
        None
    )

    display_name: Optional[
        Annotated[str, Field(max_length=50, description="Updated display name")]
    ] = None

    description: Optional[
        Annotated[str, Field(max_length=500, description="Updated description")]
    ] = None
    category: Optional[TagCategory] = Field(None, description="Updated category")
    is_official: Optional[bool] = Field(
        None, description="Update official status (admin only)"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_at_least_one_field(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure at least one field is provided for update."""
        if not any(v is not None for v in values.values()):
            raise ValueError("At least one field must be provided for update")
        return values


# ------- Response Schemas -------
class TagResponse(TagBase):
    """Basic tag response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Tag ID")
    is_official: bool = Field(..., description="Official tag flag")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[int] = Field(None, description="ID of user who created tag")


class TagDetailedResponse(TagResponse):
    """Detailed tag response with additional information."""

    created_by: Optional[int] = Field(None, description="ID of user who created tag")
    book_count: int = Field(0, description="Number of books with this tag")

    # Recent usage trend
    usage_trend: str = Field(
        "stable",
        pattern="^(increasing|decreasing|stable)$",
        description="Recent usage trend",
    )

    # Related tags
    related_tags: List[TagResponse] = Field(
        default_factory=list, description="Related tags based on co-occurrence"
    )


# ===== List and Search Params Schemas ======
class TagListResponse(BaseModel):
    """Response for paginated tag list."""

    items: List[TagResponse] = Field(..., description="List of tags")
    total: int = Field(..., ge=0, description="Total number of tags")
    page: int = Field(..., ge=1, description="Current page number")
    pages: int = Field(..., ge=0, description="Total number of pages")
    size: int = Field(..., ge=1, le=100, description="Number of items per page")


class TagSearchParams(BaseModel):
    """Parameters for searching tags."""

    search: Optional[str] = Field(
        None, min_length=1, max_length=50, description="Search query for tag names"
    )
    category: Optional[TagCategory] = Field(None, description="Filter by category")
    is_official: Optional[bool] = Field(None, description="Filter by official status")
    created_by: Optional[int] = Field(None, description="Filter by creator user ID")


# ------ Suggestions ------
class TagSuggestion(BaseModel):
    """Tag suggestion for a book."""

    tag: TagResponse = Field(..., description="Suggested tag")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    reason: str = Field(
        ...,
        description="Reason for suggestion",
        examples=["Similar books use this tag", "Based on book description"],
    )


class TagSuggestionRequest(BaseModel):
    """Request for tag suggestions."""

    book_id: Optional[int] = Field(None, description="Book ID for suggestions")
    title: Optional[str] = Field(None, description="Book title for suggestions")
    description: Optional[str] = Field(
        None, description="Book description for suggestions"
    )
    existing_tags: Optional[List[str]] = Field(
        None, description="Already assigned tags"
    )
    max_suggestions: int = Field(
        5, ge=1, le=20, description="Maximum number of suggestions"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_input_provided(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure at least one input is provided."""
        if not any(
            [values.get("book_id"), values.get("title"), values.get("description")]
        ):
            raise ValueError(
                "At least one of book_id, title, or description must be provided"
            )
        return values


class RelatedTagResponse(TagResponse):
    """A tag response that includes the co-occurrence count."""

    co_occurrence: int = Field(
        ..., description="How many books this tag shares with the source tag."
    )


# Export all schemas
__all__ = [
    # Base schemas
    "TagBase",
    "TagCreate",
    "TagUpdate",
    # Response schemas
    "TagResponse",
    "TagDetailedResponse",
    # List and search
    "TagListResponse",
    "TagSearchParams",
    # Suggestions
    "TagSuggestion",
    "TagSuggestionRequest",
    "RelatedTagResponse",
]
