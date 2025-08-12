import logging

from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.utils.deps import (
    get_current_verified_user,
    rate_limit_api,
    require_user,
    PaginationParams,
)

from app.schemas.book_schema import BookListResponse
from app.schemas.tag_schema import (
    TagCreate,
    TagResponse,
    TagSuggestion,
    TagListResponse,
    TagSearchParams,
    TagUpdate,
    RelatedTagResponse,
)
from app.utils.deps import get_pagination_params
from app.models.user_model import User
from app.services.tag_service import tag_service


logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Tags"],
    prefix=f"{settings.API_V1_STR}/tags",
)


@router.get(
    "/all",
    status_code=status.HTTP_200_OK,
    summary="Get all tags",
    response_model=TagListResponse,
    description="Retrieve a paginated list of reviews with optional filtering and search",
    dependencies=[Depends(rate_limit_api)],
)
async def get_all_tags(
    *,
    db: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination_params),
    search_params: TagSearchParams = Depends(TagSearchParams),
    order_by: str = Query("created_at", description="Field to order by"),
    order_desc: bool = Query(True, description="Order descending"),
):
    """Get all tags"""

    return await tag_service.get_all_tags(
        db=db,
        skip=pagination.skip,
        limit=pagination.limit,
        order_desc=order_desc,
        order_by=order_by,
        filters=search_params.model_dump(exclude_none=True),
    )


@router.get(
    "/{tag_id}",
    status_code=status.HTTP_200_OK,
    summary="Get tags by id",
    description="Get detailed information about a specific review",
    response_model=TagResponse,
    dependencies=[Depends(rate_limit_api)],
)
async def get_tag_by_id(*, tag_id: int, db: AsyncSession = Depends(get_session)):
    """Get Tag by it's ID"""

    return await tag_service.get_by_id(db=db, tag_id=tag_id)


@router.get(
    "/{tag_id}/related",
    status_code=status.HTTP_200_OK,
    summary="Get related tags",
    description="Get tags that frequently appear together",
    response_model=List[RelatedTagResponse],
    dependencies=[Depends(rate_limit_api)],
)
async def get_related_tags(
    *,
    tag_id: int,
    limit: int,
    db: AsyncSession = Depends(get_session),
):
    """Get tags related to a specific tag."""

    return await tag_service.get_related_tags(db=db, tag_id=tag_id, limit=limit)


# ======CREATE========
@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=TagResponse,
    summary="Create a tag",
    description="create a tag for your book",
    dependencies=[Depends(rate_limit_api)],
)
async def create_tag(
    *,
    tag_data: TagCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
):
    """Create a Tag"""

    return await tag_service.create_tag(
        db=db, tag_data=tag_data, current_user=current_user
    )


# ======Update========
@router.patch(
    "/{tag_id}",
    status_code=status.HTTP_200_OK,
    response_model=TagResponse,
    summary="Update a tag",
    description="update a tag for your book by it's id",
    dependencies=[Depends(rate_limit_api), Depends(require_user)],
)
async def update_tag(
    *,
    tag_id: int,
    tag_data: TagUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
):
    """Update atag by it's ID"""

    return await tag_service.update_tag(
        db=db, tag_data=tag_data, tag_id_to_update=tag_id, current_user=current_user
    )


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, str],
    summary="Delete a tag",
    description="delete a tag for your book by it's id",
    dependencies=[Depends(rate_limit_api), Depends(require_user)],
)
async def delete_tag(
    *,
    tag_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
):
    """Delete a tag by it's ID"""

    await tag_service.delete_tag(
        db=db, tag_id_to_delete=tag_id, current_user=current_user
    )

    return {"message": "Tag deleted successfully"}


@router.post(
    "/suggestions",
    response_model=List[TagSuggestion],
    status_code=status.HTTP_200_OK,
    summary="Get tag suggestions",
    description="Get tag suggestions for a book",
    dependencies=[Depends(rate_limit_api)],
)
async def get_tag_suggestions(
    *,
    existing_tags: Optional[List[str]],
    limit: int,
    book_id: Optional[int],
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
):
    """Get tag suggestions for a book."""
    return await tag_service.get_tag_suggestions(
        db=db,
        book_id=book_id,
        existing_tags=existing_tags,
        limit=limit,
    )


@router.get(
    "/all/books",
    response_model=BookListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all books by tags",
    description="Retrieve a paginated list of books with tags",
    dependencies=[Depends(rate_limit_api)],
)
async def get_all_books_by_tags(
    *,
    db: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination_params),
    tag_name: str,
):
    """
    Get all books with advanced filtering and pagination.
    """
    return await tag_service.get_books_by_tag_name(
        db=db, skip=pagination.skip, limit=pagination.limit, tag_name=tag_name
    )
