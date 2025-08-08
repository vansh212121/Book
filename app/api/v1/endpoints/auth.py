import logging

from typing import Dict

from fastapi import APIRouter, Depends, status, Request, Body, Query
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.db.session import get_session
from app.utils.deps import (
    get_current_verified_user,
    # rate_limit_heavy,
    rate_limit_api,
    rate_limit_auth,
    require_user,
    require_moderator,
)
from app.models.user_model import UserRole, User
from app.schemas.user_schema import (
    UserResponse,
    UserCreate,
)
from app.schemas.token_schema import TokenResponse
from app.schemas.auth_schema import (
    TokenRefresh,
    PasswordChange,
    PasswordResetConfirm,
    PasswordResetRequest,
    EmailChangeRequest,
    EmailVerificationRequest,
)

from app.core.exceptions import NotAuthorized
from app.services.user_service import user_services
from app.services.auth_service import auth_service
from app.utils.deps import reusable_oauth2

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Auth"],
    prefix=f"{settings.API_V1_STR}/auth",
)


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    summary="Create a user account",
    description="Create a user profile",
    dependencies=[Depends(rate_limit_api)],
)
async def signup(db: AsyncSession = Depends(get_session), *, user_data: UserCreate):

    user = await user_services.create_user(db=db, user_in=user_data)

    logger.info(
        f"New user registered",
        extra={
            "user_id": user.id,
            "email": user.email,
        },
    )

    return user


# ----- Login -----
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login for Access Token",
    description="Authenticate with email and password to receive JWT tokens.",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_auth)],  # Rate limit login attempts by IP
)
async def login_for_access_token(
    *,
    request: Request,
    db: AsyncSession = Depends(get_session),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    Standard user login. The 'username' field of the form should contain the user's email.
    """
    client_ip = request.client.host if request.client else "unknown"

    return await auth_service.login(
        db=db,
        email=form_data.username,
        password=form_data.password,
        client_ip=client_ip,
    )


@router.post(
    "/admin/login",
    response_model=TokenResponse,
    summary="Admin Login for Access Token",
    description="A separate, secure login endpoint for administrative users.",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_auth)],
)
async def admin_login_for_access_token(
    *,
    request: Request,
    db: AsyncSession = Depends(get_session),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    Admin user login. Authenticates the user and then authorizes them based on their role.
    """
    client_ip = request.client.host if request.client else "unknown"

    # 1. First, authenticate the user normally.
    #    This reuses our secure login logic, including brute-force protection.
    token_response = await auth_service.login(
        db=db,
        email=form_data.username,
        password=form_data.password,
        client_ip=client_ip,
    )

    # 2. After successful authentication, perform an authorization check.
    #    We need to get the user object to check their role.
    from app.crud.user_crud import user_repository

    user = await user_repository.get_by_email(db, email=form_data.username)

    # Only allow moderators and admins to use this endpoint.
    if not user or user.role < UserRole.MODERATOR:
        logger.warning(
            f"Non-admin login attempt to admin portal by user: {form_data.username}"
        )
        raise NotAuthorized(
            detail="You do not have privileges to access the admin panel."
        )

    return token_response


# ----- Logout -----
@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,  # 204 is perfect for a successful action with no response body
    summary="User Logout",
)
async def logout_user(
    # --- THE FIX IS HERE ---
    # Get the tokens from the request body
    token:TokenRefresh,
    access_token:str = Depends(reusable_oauth2),
    current_user: User = Depends(get_current_verified_user),
):
    await auth_service.logout(
        access_token=access_token, refresh_token=token.refresh_token
    )
    return  # A 204 response has no body



@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Get new access token using refresh token",
    dependencies=[Depends(rate_limit_auth)],
)
async def rotate_tokens(
    *, token_data: TokenRefresh, db: AsyncSession = Depends(get_session)
):
    """
    Refresh access token using refresh token.

    The old refresh token will be revoked and a new token pair will be issued.
    This implements token rotation for enhanced security.
    """

    return await auth_service.refresh_token(db=db, refresh_token=token_data.refresh_token)


# -------PASSWORD--------
# @router.post(
#     "/change-password",
#     response_model=Dict[str, str],
#     status_code=status.HTTP_202_ACCEPTED,
#     summary="Request password reset",
#     description="Request a password reset link via email",
#     dependencies=[Depends(rate_limit_auth)],
# )
# async def change_password(
#     *,
#     db: AsyncSession = Depends(get_session),
#     current_user: User = Depends(get_current_verified_user),
#     password_data: PasswordChange,
# ):
#     await auth_service.change_password(
#         db=db, password_data=password_data, user=current_user
#     )

#     return {"message": "Password updated successfully"}


@router.post(
    "/password-reset-request",
    response_model=Dict[str, str],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request password reset",
    description="Request a password reset link via email",
    dependencies=[Depends(rate_limit_auth)],  # 3 per hour
)
async def request_password_reset(
    *,
    db: AsyncSession = Depends(get_session),
    email: PasswordResetRequest,
):
    """
    Request a password reset link.

    If the email exists in the system, a reset link will be sent.
    For security reasons, the response is always successful.

    """

    await auth_service.request_password_reset(
        db=db, email=email.email
    )

    return {"message": f"Password reset email sent successfully to {email.email}"}


@router.post(
    "/password-reset-confirm",
    status_code=status.HTTP_200_OK,
    summary="Reset password",
    description="Reset password using token from email",
    dependencies=[Depends(rate_limit_auth)],
    response_model=Dict[str, str],
)
async def reset_password_confirm(
    *,
    reset_data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_session),
):
    """
    Reset password using reset token.

    - **token**: Reset token from email
    - **new_password**: New password (must meet security requirements)

    The token is valid for 1 hour after generation.
    All existing tokens will be revoked after successful reset.
    """

    await auth_service.reset_password(db=db, reset_data=reset_data)

    return {"message": "Password reset successfully."}


# -------EMAIL--------
@router.post(
    "/email",
    response_model=Dict[str, str],
    summary="Reset email",
    description="Reset email using token from new email",
    dependencies=[Depends(rate_limit_auth)],
)
async def email_change(
    *,
    email: EmailChangeRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_session),
):
    """Change Email for logged-in User."""

    await auth_service.request_email_change(
        new_email=email.new_email, user=current_user, db=db
    )

    return {
        "message": f"Verification link sent to this eamil:{email.new_email}, verify to reflect changes"
    }


@router.post(
    "/email/confirm-change",
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Verify changed email",
    description="Verify new email using token from email",
)
async def verify_changed_email(
    *,
    db: AsyncSession = Depends(get_session),
    token: str,
):
    """Verify the changed Email"""

    await auth_service.confirm_email_change(db=db, token=token)

    return {"message": "Email updated successfully"}


@router.post(
    "/email/request-verification-email",
    response_model=Dict[str, str],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Resend verification email",
    description="Request a new email verification link",
    dependencies=[Depends(rate_limit_auth)],  # 3 per hour
)
async def request_new_verification_email(
    *,
    email_request: EmailVerificationRequest,
    db: AsyncSession = Depends(get_session),
):
    """
    Request a new verification email.

    Limited to 5 requests per hour to prevent abuse.
    Only unverified users can request verification emails.
    """

    await auth_service.request_verification_email(email=email_request.email, db=db)

    return {"message": f"Verification link sent to this eamil:{email_request.email}"}


@router.post(
    "/email/verify-email",
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Verify email address",
)
async def verify_account(
    *,
    token: str,  # It should take the token as a query parameter
    db: AsyncSession = Depends(get_session),
):
    await auth_service.verify_email(token=token, db=db)
    return {"message": "Email verified successfully"}
