import logging

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.utils.deps import (
    get_current_verified_user,
    rate_limit_heavy,
    require_user,
)
from app.schemas.user_schema import (
    UserResponse,
    UserUpdate,
)
from app.models.user_model import User
from app.services.user_service import user_services

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
