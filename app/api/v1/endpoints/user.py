import logging

from typing import Dict, List
from fastapi import APIRouter, Depends, status, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.utils.deps import (
    get_current_verified_user,
    rate_limit_heavy,
    require_user,
    rate_limit_auth,
    rate_limit_api,
    PaginationParams,
    get_pagination_params,
)
from app.schemas.user_schema import (
    UserResponse,
    UserUpdate,
)
from app.schemas.book_schema import BookSearchParams, BookListResponse
from app.schemas.auth_schema import PasswordChange
from app.schemas.review_schema import ReviewListResponse

from app.models.user_model import User

from app.services.user_service import user_services
from app.services.book_service import book_service
from app.services.book_service import book_service
from app.services.auth_service import auth_service
from app.services.review_service import review_service

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Users"],
    prefix=f"{settings.API_V1_STR}/users",
)


# ------ Current User Operations ------
@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
    summary="Get current user profile",
    description="Get profile information for the authenticated user",
    dependencies=[Depends(rate_limit_heavy), Depends(require_user)],
)
async def get_my_profile(
    db: AsyncSession = Depends(get_session),
    *,
    current_user: User = Depends(get_current_verified_user),
):
    return current_user


@router.patch(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
    summary="Update current user profile",
    description="Update profile information for the authenticated user",
    dependencies=[Depends(rate_limit_heavy), Depends(require_user)],
)
async def update_my_profile(
    db: AsyncSession = Depends(get_session),
    *,
    current_user: User = Depends(get_current_verified_user),
    user_data: UserUpdate,
):
    updated_user = await user_services.update_user(
        db=db,
        user_id_to_update=current_user.id,
        user_data=user_data,
        current_user=current_user,
    )

    return updated_user


@router.delete(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
    summary="Deactivate current user profile",
    description="Deactivate profile for the authenticated user",
    dependencies=[Depends(rate_limit_heavy), Depends(require_user)],
)
async def deactivate_my_profile(
    db: AsyncSession = Depends(get_session),
    *,
    current_user: User = Depends(get_current_verified_user),
):
    """
    Deactivate a user account.

    - Users can deactivate their own account
    - Admins can deactivate any user account
    - The last admin account cannot be deactivated
    """
    user_to_deactivate = await user_services.deactivate_user(
        db=db, user_id_to_deactivate=current_user.id, current_user=current_user
    )

    return user_to_deactivate


@router.post(
    "/change-password",
    response_model=Dict[str, str],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Change Current User's Password",
    description="Change Current User's Password",
    dependencies=[Depends(rate_limit_auth)],
)
async def change_password(
    *,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
    password_data: PasswordChange,
):
    await auth_service.change_password(
        db=db, password_data=password_data, user=current_user
    )

    return {"message": "Password updated successfully"}


@router.get(
    "/me/books",
    # response_model=List[BookResponseDetailed],
    response_model=BookListResponse,
    summary="Get current user's books",
    description="Retrieve books owned by the authenticated user",
    dependencies=[Depends(rate_limit_api)],
)
async def get_my_books(
    *,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
    pagination: PaginationParams = Depends(get_pagination_params),
    search_params: BookSearchParams = Depends(BookSearchParams),
    order_by: str = Query("created_at", description="Field to order by"),
    order_desc: bool = Query(True, description="Order descending"),
):
    """
    Get books owned by the current authenticated user.
    """

    return await book_service.get_user_books(
        db=db,
        user_id=current_user.id,
        skip=pagination.skip,
        limit=pagination.limit,
        filters=search_params.model_dump(exclude_none=True),
        order_by=order_by,
        order_desc=order_desc,
    )


@router.get(
    "/me/reviews",
    response_model=ReviewListResponse,
    summary="Get current user's reviews",
    description="Retrieve review's owned by the authenticated user",
    dependencies=[Depends(rate_limit_api)],
)
async def get_my_reviews(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
    pagination: PaginationParams = Depends(get_pagination_params),
    search_params: BookSearchParams = Depends(BookSearchParams),
    order_by: str = Query("created_at", description="Field to order by"),
    order_desc: bool = Query(True, description="Order descending"),
):
    """Get reviews owned by the current authenticated user."""

    return await review_service.get_user_reviews(
        db=db,
        user_id=current_user.id,
        skip=pagination.skip,
        limit=pagination.limit,
        filters=search_params.model_dump(exclude_none=True),
        order_by=order_by,
        order_desc=order_desc,
    )
