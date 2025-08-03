# # app/schemas/tag_schema.py
# """
# Tag schemas for request/response models.

# This module defines Pydantic schemas for tag-related operations,
# including creation, updates, and various response formats.
# """

# from typing import List, Optional
# from datetime import datetime

# from pydantic import BaseModel, Field, ConfigDict, field_validator

# from app.schemas.book_schema import BookBasicResponse


# class TagBase(BaseModel):
#     """Base schema for tag data."""
    
#     name: str = Field(
#         ...,
#         min_length=1,
#         max_length=50,
#         description="The name of the tag",
#         examples=["fiction", "science", "history"]
#     )
    
#     @field_validator('name')
#     @classmethod
#     def validate_name(cls, v: str) -> str:
#         """Validate and normalize tag name."""
#         # Strip whitespace
#         v = v.strip()
        
#         # Check if empty after stripping
#         if not v:
#             raise ValueError("Tag name cannot be empty")
        
#         # Normalize to lowercase
#         v = v.lower()
        
#         # Validate characters (alphanumeric, hyphens, and spaces)
#         if not all(c.isalnum() or c in ['-', ' '] for c in v):
#             raise ValueError("Tag name can only contain letters, numbers, hyphens, and spaces")
        
#         # Prevent multiple consecutive spaces or hyphens
#         if '  ' in v or '--' in v:
#             raise ValueError("Tag name cannot contain consecutive spaces or hyphens")
        
#         return v


# class TagCreate(TagBase):
#     """Schema for creating a new tag."""
#     pass


# class TagUpdate(BaseModel):
#     """Schema for updating a tag."""
    
#     model_config = ConfigDict(validate_assignment=True)
    
#     name: Optional[str] = Field(
#         None,
#         min_length=1,
#         max_length=50,
#         description="The new name for the tag"
#     )
    
#     @field_validator('name')
#     @classmethod
#     def validate_name(cls, v: Optional[str]) -> Optional[str]:
#         """Validate and normalize tag name if provided."""
#         if v is None:
#             return v
#         return TagBase.validate_name(v)


# class TagResponse(TagBase):
#     """Basic tag response schema."""
    
#     model_config = ConfigDict(from_attributes=True)
    
#     id: int = Field(..., description="Unique identifier for the tag")
#     created_at: datetime = Field(..., description="When the tag was created")
#     updated_at: datetime = Field(..., description="When the tag was last updated")


# class TagBasicResponse(BaseModel):
#     """Minimal tag response for inclusion in other schemas."""
    
#     model_config = ConfigDict(from_attributes=True)
    
#     id: int = Field(..., description="Unique identifier for the tag")
#     name: str = Field(..., description="The name of the tag")


# class TagWithBooksResponse(TagResponse):
#     """Tag response with associated books."""
    
#     books: List[BookBasicResponse] = Field(
#         default_factory=list,
#         description="Books associated with this tag"
#     )
#     book_count: int = Field(
#         default=0,
#         description="Number of books with this tag"
#     )


# class TagListResponse(BaseModel):
#     """Response schema for paginated tag list."""
    
#     items: List[TagResponse] = Field(
#         ...,
#         description="List of tags"
#     )
#     total: int = Field(
#         ...,
#         ge=0,
#         description="Total number of tags"
#     )
#     page: int = Field(
#         ...,
#         ge=1,
#         description="Current page number"
#     )
#     pages: int = Field(
#         ...,
#         ge=0,
#         description="Total number of pages"
#     )
#     size: int = Field(
#         ...,
#         ge=1,
#         le=100,
#         description="Number of items per page"
#     )


# class TagPopularResponse(BaseModel):
#     """Response for popular tags with usage statistics."""
    
#     id: int = Field(..., description="Unique identifier for the tag")
#     name: str = Field(..., description="The name of the tag")
#     book_count: int = Field(..., description="Number of books using this tag")
#     rank: int = Field(..., description="Popularity rank")


# class TagSearchParams(BaseModel):
#     """Parameters for searching tags."""
    
#     query: Optional[str] = Field(
#         None,
#         min_length=1,
#         max_length=50,
#         description="Search query for tag names"
#     )
#     min_usage: Optional[int] = Field(
#         None,
#         ge=0,
#         description="Minimum number of books using the tag"
#     )
#     max_usage: Optional[int] = Field(
#         None,
#         ge=0,
#         description="Maximum number of books using the tag"
#     )
#     order_by: Optional[str] = Field(
#         default="name",
#         pattern="^(name|created_at|book_count)$",
#         description="Field to order by"
#     )
#     order_desc: bool = Field(
#         default=False,
#         description="Whether to order in descending order"
#     )


# class TagBulkCreateRequest(BaseModel):
#     """Request schema for creating multiple tags."""
    
#     tags: List[str] = Field(
#         ...,
#         min_items=1,
#         max_items=50,
#         description="List of tag names to create",
#         examples=[["fiction", "non-fiction", "science", "history"]]
#     )
    
#     @field_validator('tags')
#     @classmethod
#     def validate_tags(cls, v: List[str]) -> List[str]:
#         """Validate and normalize tag list."""
#         # Remove duplicates while preserving order
#         seen = set()
#         unique_tags = []
        
#         for tag in v:
#             normalized = TagBase.validate_name(tag)
#             if normalized not in seen:
#                 seen.add(normalized)
#                 unique_tags.append(normalized)
        
#         if not unique_tags:
#             raise ValueError("At least one valid tag must be provided")
        
#         return unique_tags


# class TagBulkCreateResponse(BaseModel):
#     """Response schema for bulk tag creation."""
    
#     created: List[TagResponse] = Field(
#         default_factory=list,
#         description="Successfully created tags"
#     )
#     existing: List[TagResponse] = Field(
#         default_factory=list,
#         description="Tags that already existed"
#     )
#     failed: List[dict] = Field(
#         default_factory=list,
#         description="Tags that failed to create with error details"
#     )
#     total_processed: int = Field(
#         ...,
#         description="Total number of tags processed"
#     )


# class TagMergeRequest(BaseModel):
#     """Request schema for merging tags."""
    
#     source_tag_ids: List[int] = Field(
#         ...,
#         min_items=1,
#         max_items=10,
#         description="IDs of tags to merge from"
#     )
#     target_tag_id: int = Field(
#         ...,
#         description="ID of tag to merge into"
#     )
#     delete_source_tags: bool = Field(
#         default=True,
#         description="Whether to delete source tags after merge"
#     )


# class TagStatistics(BaseModel):
#     """Tag usage statistics."""
    
#     total_tags: int = Field(..., description="Total number of tags")
#     tags_with_books: int = Field(..., description="Number of tags assigned to at least one book")
#     unused_tags: int = Field(..., description="Number of tags not assigned to any book")
#     average_books_per_tag: float = Field(..., description="Average number of books per tag")
#     most_used_tags: List[TagPopularResponse] = Field(
#         default_factory=list,
#         description="Most frequently used tags"
#     )
#     recently_created_tags: List[TagResponse] = Field(
#         default_factory=list,
#         description="Recently created tags"
#     )


# # Export all schemas
# __all__ = [
#     # Base schemas
#     "TagBase",
#     "TagCreate",
#     "TagUpdate",
    
#     # Response schemas
#     "TagResponse",
#     "TagBasicResponse",
#     "TagWithBooksResponse",
#     "TagListResponse",
#     "TagPopularResponse",
    
#     # Request schemas
#     "TagSearchParams",
#     "TagBulkCreateRequest",
#     "TagBulkCreateResponse",
#     "TagMergeRequest",
    
#     # Statistics
#     "TagStatistics",
# ]