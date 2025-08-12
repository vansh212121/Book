import logging
from typing import Dict

from fastapi import APIRouter, Depends, status, Query, Path
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.utils.deps import (
    get_current_verified_user,
    get_pagination_params,
    rate_limit_api,
    require_admin,
    require_moderator,
    PaginationParams,
)
from app.schemas.user_schema import (
    UserResponse,
    UserUpdate,
    UserListResponse,
    UserSearchParams,
)
from app.models.user_model import User, UserRole
from app.services.user_service import user_services

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Admin"],
    prefix=f"{settings.API_V1_STR}/admin",
)


# ------ Current Admin CRUD Operations ------


@router.get(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
    summary="Get user by id",
    description="Get all information for the user by id (moderators and admin only)",
    dependencies=[Depends(rate_limit_api), Depends(require_moderator)],
)
async def get_user_by_id(
    db: AsyncSession = Depends(get_session),
    *,
    user_id: int,
    current_user: User = Depends(get_current_verified_user),
):
    return await user_services.get_user_by_id(
        db=db, user_id=user_id, current_user=current_user
    )


@router.post(
    "/{user_id}/activate",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, str],
    summary="Activate a users account",
    description="Activate a user's account using his id(Admins only).",
    dependencies=[Depends(require_admin), Depends(rate_limit_api)],
)
async def activate_user(
    db: AsyncSession = Depends(get_session),
    *,
    current_user: User = Depends(get_current_verified_user),
    user_id: int,
):
    """
    Deactivate a user account.

    - Users can deactivate their own account
    - Admins can deactivate any user account
    - The last admin account cannot be deactivated
    """
    user_to_activate = await user_services.activate_user(
        db=db, user_id_to_activate=user_id, current_user=current_user
    )
    logger.info(
        f"User activated", extra={"user_id": user_id, "activated_by": current_user.id}
    )

    return {"message": f"{user_to_activate.first_name}'s Account has been Activated."}


@router.post(
    "/{user_id}/change-role",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Change user role",
    description="Change a user's role (admin only)",
    dependencies=[Depends(require_admin), Depends(rate_limit_api)],
)
async def change_user_role(
    db: AsyncSession = Depends(get_session),
    *,
    current_user: User = Depends(get_current_verified_user),
    new_role: UserRole = Query(..., description="New role for the user"),
    user_id: int,
):
    """
    Change a user's role.

    **Admin access required.**

    Available roles:
    - USER: Standard user
    - MODERATOR: Content moderator
    - ADMIN: System administrator
    """

    updated_user = await user_services.change_role(
        db=db, user_id_to_change=user_id, current_user=current_user, new_role=new_role
    )

    logger.info(
        f"User role changed",
        extra={
            "user_id": user_id,
            "new_role": new_role.value,
            "changed_by": current_user.id,
        },
    )

    return updated_user


@router.get(
    "/users/all",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all users",
    description="Get a paginated and filterable list of all users (Admins only).",
    dependencies=[Depends(require_admin)],  # Simplified the auth check
)
async def get_all_users(
    db: AsyncSession = Depends(get_session),
    *,
    current_user: User = Depends(get_current_verified_user),
    pagination: PaginationParams = Depends(get_pagination_params),
    search_params: UserSearchParams = Depends(UserSearchParams),
    order_by: str = Query("created_at", description="Field to order by"),
    order_desc: bool = Query(True, description="Order descending"),
):
    # The endpoint is now just one line of logic!
    return await user_services.get_users(
        db=db,
        current_user=current_user,
        skip=pagination.skip,
        limit=pagination.limit,
        filters=search_params.model_dump(exclude_none=True),
        order_by=order_by,
        order_desc=order_desc,
    )


@router.patch(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
    summary="Update user by id",
    description="Update user profile by id",
    dependencies=[Depends(rate_limit_api), Depends(require_admin)],
)
async def update_user(
    db: AsyncSession = Depends(get_session),
    *,
    current_user: User = Depends(get_current_verified_user),
    user_id: int,
    user_data: UserUpdate,
):
    """
    Update user information.

    - Users can update their own profile
    - Admins can update any user
    - Role changes require admin privileges
    """
    updated_user = await user_services.update_user(
        db=db, user_id_to_update=user_id, user_data=user_data, current_user=current_user
    )

    logger.info(
        f"User updated",
        extra={
            "user_id": user_id,
            "updated_by": current_user.id,
            "changes": user_data.model_dump(exclude_unset=True),
        },
    )

    return updated_user


@router.post(
    "/{user_id}/deactivate",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, str],
    summary="Deactivate user by id",
    description="Deactivate user profile by id",
    dependencies=[Depends(rate_limit_api), Depends(require_admin)],
)
async def deactivate_user(
    db: AsyncSession = Depends(get_session),
    *,
    user_id: int,
    current_user: User = Depends(get_current_verified_user),
):
    """
    Deactivate a user account.

    - Users can deactivate their own account
    - Admins can deactivate any user account
    - The last admin account cannot be deactivated
    """
    user_to_deactivate = await user_services.deactivate_user(
        db=db, user_id_to_deactivate=user_id, current_user=current_user
    )

    return {
        "message": f"{user_to_deactivate.first_name}'s Account has been Deactivated."
    }


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, str],
    summary="Delete user by id",
    description="Delete user profile by id",
    dependencies=[Depends(rate_limit_api), Depends(require_admin)],
)
async def delete_user(
    db: AsyncSession = Depends(get_session),
    *,
    user_id: int,
    current_user: User = Depends(get_current_verified_user),
):
    user_to_delete = await user_services.delete_user(
        db=db, user_id_to_delete=user_id, current_user=current_user
    )

    return {"message" : "User delete succesfully."}
