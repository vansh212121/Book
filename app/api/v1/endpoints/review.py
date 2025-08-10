import logging

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.utils.deps import (
    get_current_verified_user,
    rate_limit_heavy,
    rate_limit_api,
    require_admin,
    require_moderator,
    PaginationParams,
)

from app.schemas.review_schema import (
    ReviewCreate,
    ReviewDetailedResponse,
    ReviewVoteResponse,
    ReviewListResponse,
    ReviewResponse,
    ReviewUpdate,
    ReviewSearchParams,
)
from app.utils.deps import get_pagination_params
from app.models.user_model import User
from app.services.review_service import review_service


logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Reviews"],
    prefix=f"{settings.API_V1_STR}/reviews",
)


@router.get(
    "/all",
    status_code=status.HTTP_200_OK,
    response_model=ReviewListResponse,
    summary="Get all Reviews",
    description="Retrieve a paginated list of reviews with optional filtering and search",
    dependencies=[Depends(require_admin), Depends(rate_limit_api)],
)
async def get_all_reviews(
    *,
    db: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination_params),
    search_params: ReviewSearchParams = Depends(ReviewSearchParams),
    order_by: str = Query("created_at", description="Field to order by"),
    order_desc: bool = Query(True, description="Order descending"),
):
    """Get all reveiws"""

    return await review_service.get_reviews(
        db=db,
        skip=pagination.skip,
        limit=pagination.limit,
        order_by=order_by,
        order_desc=order_desc,
        filters=search_params.model_dump(exclude_none=True),
    )


@router.get(
    "/users/{user_id}/reviews",
    status_code=status.HTTP_200_OK,
    response_model=ReviewListResponse,
    summary="Get all User Reviews",
    description="Retrieve a paginated list of reviews with optional filtering and search",
    dependencies=[Depends(require_admin), Depends(rate_limit_api)],
)
async def get_user_reviews(
    *,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
    user_id:int,
    pagination: PaginationParams = Depends(get_pagination_params),
    search_params: ReviewSearchParams = Depends(ReviewSearchParams),
    order_by: str = Query("created_at", description="Field to order by"),
    order_desc: bool = Query(True, description="Order descending"),
):
    """Get all reviews written by a specific user."""

    return await review_service.get_user_reviews(
        db=db,
        skip=pagination.skip,
        limit=pagination.limit,
        order_by=order_by,
        order_desc=order_desc,
        user_id=user_id,
        filters=search_params.model_dump(exclude_none=True),
    )


@router.get(
    "/books/{book_id}",
    status_code=status.HTTP_200_OK,
    response_model=ReviewListResponse,
    summary="Get all Book Reviews",
    description="Retrieve a paginated list of book reviews with optional filtering and search",
    dependencies=[Depends(rate_limit_api)],
)
async def get_book_reviews(
    *,
    book_id:int,
    db: AsyncSession = Depends(get_session),
    pagination: PaginationParams = Depends(get_pagination_params),
    search_params: ReviewSearchParams = Depends(ReviewSearchParams),
    order_by: str = Query("created_at", description="Field to order by"),
    order_desc: bool = Query(True, description="Order descending"),
):
    """Get all reviews written for a specific book."""

    return await review_service.get_book_reviews(
        db=db,
        skip=pagination.skip,
        limit=pagination.limit,
        order_by=order_by,
        order_desc=order_desc,
        filters=search_params.model_dump(exclude_none=True),
        book_id=book_id
    )


@router.get(
    "/{review_id}",
    status_code=status.HTTP_200_OK,
    response_model=ReviewResponse,
    summary="Get review by ID",
    description="Get detailed information about a specific review",
    dependencies=[Depends(rate_limit_api)],
)
async def get_review_by_id(
    *,
    review_id: int,
    db: AsyncSession = Depends(get_session),
):
    """Get a specific review by ID."""

    return await review_service.get_review_by_id(db=db, review_id=review_id)


# =====CREATE======
@router.post(
    "/books/{book_id}/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create review for book",
    description="Create a new review for a specific book",
    dependencies=[Depends(rate_limit_heavy)],
)
async def create_review_for_a_book(
    *,
    review_data: ReviewCreate,
    book_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
):
    """Create a review for a book.

    - Users can only have one review per book
    - Review content must be at least 10 characters
    - Rating must be between 1 and 5
    - Limited to 10 reviews per hour to prevent spam

    **Required fields:**
    - rating: Rating from 1 to 5
    - content: Review text (min 10 characters)"""
    # review_data.book_id = book_id

    return await review_service.create_review(
        db=db, review_data=review_data, current_user=current_user, book_id=book_id
    )


# =======UPDATE========
@router.patch(
    "/{review_id}",
    response_model=ReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Update review",
    description="Update an existing review",
    dependencies=[Depends(rate_limit_api)],
)
async def update_review(
    *,
    review_id: int,
    review_data: ReviewUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
):
    """
    Update an existing review.

    Users can only update their own reviews.
    Moderators and admins can update any review.

    **Updatable fields:**
    - rating: New rating (1-5)
    - title: Review title
    - content: Review content"""

    updated_review = await review_service.update_review(
        db=db,
        review_id_to_update=review_id,
        review_data=review_data,
        current_user=current_user,
    )

    logger.info(
        f"Review updated",
        extra={
            "review_id": review_id,
            "user_id": current_user.id,
            "updates": review_data.model_dump(exclude_unset=True),
        },
    )

    return updated_review


# =======DELETE========
@router.delete(
    "/{review_id}",
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Delete review",
    description="Delete a review",
)
async def delete_review(
    *,
    review_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
):
    """
    Delete a review.
    Users can only delete their own reviews.
    Moderators and admins can delete any review.
    """
    deleted_review = await review_service.delete(
        db=db, review_id_to_delete=review_id, current_user=current_user
    )

    logger.info(
        f"Review deleted",
        extra={
            "review_id": review_id,
            "user_id": current_user.id,
            "deleted_by": current_user.email,
        },
    )

    return {"message": f"Review with deleted successfully"}


@router.post(
    "/{review_id}/vote",
    response_model=ReviewVoteResponse,
    status_code=status.HTTP_200_OK,
    summary="Vote on review",
    description="Vote whether a review is helpful or not",
    dependencies=[Depends(rate_limit_heavy)],
)
async def vote_on_review(
    *,
    review_id: int,
    is_helpful: bool,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
):
    """Vote on whether a review is helpful."""

    review = await review_service.vote_on_review(
        review_id=review_id, db=db, current_user=current_user, is_helpful=is_helpful
    )

    return review
