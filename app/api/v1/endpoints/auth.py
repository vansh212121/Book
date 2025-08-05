# # app/api/v1/endpoints/auth.py
# """
# Authentication endpoints.

# Provides endpoints for user registration, login, logout, password management,
# and email verification with comprehensive security features.
# """

# import logging
# from typing import Optional

# from fastapi import APIRouter, Depends, status, BackgroundTasks, Query, Header, Request
# from fastapi.security import OAuth2PasswordRequestForm
# from sqlmodel.ext.asyncio.session import AsyncSession

# from app.core.config import settings
# from app.db.session import get_session
# from app.services.auth_service import auth_service
# from app.schemas.auth_schema import (
#     UserRegister,
#     UserLogin,
#     TokenResponse,
#     MessageResponse,
#     PasswordReset,
#     PasswordResetConfirm,
#     EmailVerification,
#     RefreshTokenRequest
# )
# from app.schemas.user_schema import UserResponse
# from app.utils.deps import (
#     get_current_user,
#     get_current_active_user,
#     get_current_verified_user,
#     RateLimiter,
#     rate_limit_auth,
#     get_request_id
# )
# from app.models.user_model import User

# logger = logging.getLogger(__name__)

# router = APIRouter(
#     tags=["Authentication"],
#     prefix=f"{settings.API_V1_STR}/auth",
#     responses={
#         429: {"description": "Too many requests"},
#         500: {"description": "Internal server error"}
#     }
# )


# # --- Registration ---

# @router.post(
#     "/signup",
#     response_model=UserResponse,
#     status_code=status.HTTP_201_CREATED,
#     summary="Register new user",
#     description="Create a new user account with email verification",
#     dependencies=[Depends(rate_limit_auth)],
#     responses={
#         201: {"description": "User created successfully"},
#         409: {"description": "User already exists"},
#         422: {"description": "Validation error"}
#     }
# )
# async def signup_user(
#     *,
#     user_data: UserRegister,
#     db: AsyncSession = Depends(get_session),
#     background_tasks: BackgroundTasks,
#     request: Request,
#     request_id: str = Depends(get_request_id)
# ):
#     """
#     Register a new user account.

#     - **email**: Valid email address (will be used for login)
#     - **username**: Unique username (3-50 characters, alphanumeric with _ and -)
#     - **password**: Strong password (min 8 characters)
#     - **full_name**: User's full name

#     A verification email will be sent to the provided email address.
#     """
#     # Get client info for logging
#     client_ip = request.client.host if request.client else "unknown"
#     user_agent = request.headers.get("User-Agent", "unknown")

#     user = await auth_service.register(
#         user_data=user_data,
#         db=db,
#         background_tasks=background_tasks
#     )

#     logger.info(
#         f"New user registered",
#         extra={
#             "user_id": user.id,
#             "email": user.email,
#             "request_id": request_id,
#             "client_ip": client_ip,
#             "user_agent": user_agent
#         }
#     )

#     return UserResponse.model_validate(user)


# # --- Login ---

# @router.post(
#     "/login",
#     response_model=TokenResponse,
#     summary="Login user",
#     description="Authenticate with email and password",
#     dependencies=[Depends(rate_limit_auth)],
#     responses={
#         200: {"description": "Login successful"},
#         401: {"description": "Invalid credentials"},
#         403: {"description": "Account inactive or unverified"}
#     }
# )
# async def login_user(
#     *,
#     form_data: OAuth2PasswordRequestForm = Depends(),
#     db: AsyncSession = Depends(get_session),
#     request: Request,
#     request_id: str = Depends(get_request_id)
# ):
#     """
#     Login with email and password.

#     Returns access and refresh tokens on successful authentication.

#     Note: The 'username' field should contain the email address.
#     """
#     # Get client info
#     client_ip = request.client.host if request.client else "unknown"
#     user_agent = request.headers.get("User-Agent", "unknown")

#     return await auth_service.login(
#         credentials=form_data,
#         db=db,
#         user_agent=user_agent,
#         ip_address=client_ip
#     )


# @router.post(
#     "/admin/login",
#     response_model=TokenResponse,
#     summary="Admin login",
#     description="Login endpoint for administrators and moderators",
#     dependencies=[Depends(rate_limit_auth)],
#     responses={
#         200: {"description": "Login successful"},
#         401: {"description": "Invalid credentials"},
#         403: {"description": "Insufficient privileges"}
#     }
# )
# async def login_admin(
#     *,
#     form_data: OAuth2PasswordRequestForm = Depends(),
#     db: AsyncSession = Depends(get_session),
#     request: Request,
#     request_id: str = Depends(get_request_id)
# ):
#     """
#     Admin portal login.

#     Only users with ADMIN or MODERATOR roles can access this endpoint.
#     Enhanced security checks are applied.
#     """
#     # Get client info
#     client_ip = request.client.host if request.client else "unknown"
#     user_agent = request.headers.get("User-Agent", "unknown")

#     return await auth_service.login_admin(
#         credentials=form_data,
#         db=db,
#         user_agent=user_agent,
#         ip_address=client_ip
#     )


# # --- Logout ---

# @router.post(
#     "/logout",
#     response_model=MessageResponse,
#     status_code=status.HTTP_200_OK,
#     summary="Logout user",
#     description="Logout current user and revoke tokens"
# )
# async def logout_user(
#     *,
#     current_user: User = Depends(get_current_user),
#     authorization: str = Header(..., description="Bearer token"),
#     refresh_token: Optional[RefreshTokenRequest] = None
# ):
#     """
#     Logout current user.

#     Revokes the access token and optionally the refresh token.
#     """
#     # Extract token from Authorization header
#     access_token = authorization.replace("Bearer ", "")

#     result = await auth_service.logout(
#         access_token=access_token,
#         refresh_token=refresh_token.refresh_token if refresh_token else None
#     )

#     return MessageResponse(**result)


# @router.post(
#     "/logout/all",
#     response_model=MessageResponse,
#     status_code=status.HTTP_200_OK,
#     summary="Logout from all devices",
#     description="Revoke all tokens for the current user"
# )
# async def logout_all_devices(
#     *,
#     current_user: User = Depends(get_current_active_user)
# ):
#     """
#     Logout user from all devices.

#     This will invalidate all existing tokens for the user,
#     requiring re-authentication on all devices.
#     """
#     from app.core.security import token_manager

#     await token_manager.revoke_all_user_tokens(
#         str(current_user.id),
#         "logout_all_devices"
#     )

#     logger.info(
#         f"User logged out from all devices",
#         extra={"user_id": current_user.id, "email": current_user.email}
#     )

#     return MessageResponse(message="Successfully logged out from all devices")


# # --- Token Management ---

# @router.post(
#     "/refresh",
#     response_model=TokenResponse,
#     summary="Refresh access token",
#     description="Get new access token using refresh token"
# )
# async def refresh_token(
#     *,
#     token_data: RefreshTokenRequest,
#     db: AsyncSession = Depends(get_session)
# ):
#     """
#     Refresh access token using refresh token.

#     The old refresh token will be revoked and a new token pair will be issued.
#     This implements token rotation for enhanced security.
#     """
#     return await auth_service.refresh_tokens(token_data.refresh_token, db)


# # --- Email Verification ---

# @router.post(
#     "/request-verification-email",
#     response_model=MessageResponse,
#     status_code=status.HTTP_202_ACCEPTED,
#     summary="Resend verification email",
#     description="Request a new email verification link",
#     dependencies=[Depends(RateLimiter(times=3, seconds=3600))]  # 3 per hour
# )
# async def request_new_verification_email(
#     *,
#     current_user: User = Depends(get_current_user),
#     db: AsyncSession = Depends(get_session),
#     background_tasks: BackgroundTasks
# ):
#     """
#     Request a new verification email.

#     Limited to 3 requests per hour to prevent abuse.
#     Only unverified users can request verification emails.
#     """
#     result = await auth_service.resend_verification_email(
#         user=current_user,
#         background_tasks=background_tasks
#     )

#     return MessageResponse(**result)


# @router.get(
#     "/verify-account",
#     response_model=MessageResponse,
#     status_code=status.HTTP_200_OK,
#     summary="Verify email address",
#     description="Verify email using token from verification email"
# )
# async def verify_account(
#     *,
#     token: str = Query(..., description="Verification token from email"),
#     db: AsyncSession = Depends(get_session)
# ):
#     """
#     Verify email address using token.

#     The token is sent via email after registration or when requested.
#     Tokens are valid for 24 hours.
#     """
#     result = await auth_service.verify_email(token, db)

#     return MessageResponse(**result)


# @router.post(
#     "/verify-account",
#     response_model=MessageResponse,
#     status_code=status.HTTP_200_OK,
#     summary="Verify email address (POST)",
#     description="Alternative POST endpoint for email verification"
# )
# async def verify_account_post(
#     *,
#     verification: EmailVerification,
#     db: AsyncSession = Depends(get_session)
# ):
#     """
#     Verify email address using token (POST method).

#     Alternative to GET method for clients that prefer POST.
#     """
#     result = await auth_service.verify_email(verification.token, db)

#     return MessageResponse(**result)


# # --- Password Reset ---

# @router.post(
#     "/password-reset-request",
#     response_model=MessageResponse,
#     status_code=status.HTTP_202_ACCEPTED,
#     summary="Request password reset",
#     description="Request a password reset link via email",
#     dependencies=[Depends(RateLimiter(times=3, seconds=3600))]  # 3 per hour
# )
# async def request_password_reset_email(
#     *,
#     request_data: PasswordReset,
#     db: AsyncSession = Depends(get_session),
#     background_tasks: BackgroundTasks,
#     request: Request
# ):
#     """
#     Request a password reset link.

#     If the email exists in the system, a reset link will be sent.
#     For security reasons, the response is always successful.

#     Limited to 3 requests per hour per IP.
#     """
#     result = await auth_service.request_password_reset(
#         email=request_data.email,
#         db=db,
#         background_tasks=background_tasks
#     )

#     # Log attempt
#     client_ip = request.client.host if request.client else "unknown"
#     logger.info(
#         f"Password reset requested",
#         extra={"email": request_data.email, "client_ip": client_ip}
#     )

#     return MessageResponse(**result)


# @router.post(
#     "/password-reset-confirm",
#     response_model=MessageResponse,
#     status_code=status.HTTP_200_OK,
#     summary="Reset password",
#     description="Reset password using token from email"
# )
# async def confirm_password_reset(
#     *,
#     request_data: PasswordResetConfirm,
#     db: AsyncSession = Depends(get_session)
# ):
#     """
#     Reset password using reset token.

#     - **token**: Reset token from email
#     - **new_password**: New password (must meet security requirements)

#     The token is valid for 1 hour after generation.
#     All existing tokens will be revoked after successful reset.
#     """
#     result = await auth_service.reset_password(
#         token=request_data.token,
#         new_password=request_data.new_password,
#         db=db
#     )

#     return MessageResponse(**result)


# # --- Account Security ---

# @router.get(
#     "/sessions",
#     response_model=MessageResponse,
#     summary="Get active sessions",
#     description="Get information about active sessions (future feature)",
#     include_in_schema=False
# )
# async def get_active_sessions(
#     current_user: User = Depends(get_current_verified_user)
# ):
#     """
#     Get information about all active sessions.

#     This is a placeholder for future session management features.
#     """
#     return MessageResponse(
#         message="Session management feature coming soon"
#     )


# # --- Health Check ---

# @router.get(
#     "/health",
#     response_model=MessageResponse,
#     summary="Auth service health check",
#     description="Check if authentication service is operational",
#     include_in_schema=False
# )
# async def health_check():
#     """Simple health check for the auth service."""
#     return MessageResponse(message="Auth service is healthy")


import logging

# from typing import Dict

from fastapi import APIRouter, Depends, status, Request
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
from app.models.user_model import UserRole
from app.schemas.user_schema import (
    UserResponse,
    UserCreate,
)
from app.schemas.token_schema import TokenResponse

from app.core.exceptions import NotAuthorized
from app.services.user_service import user_services
from app.services.auth_service import auth_service

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


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login for Access Token",
    description="Authenticate with email and password to receive JWT tokens.",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_auth)],  # Rate limit login attempts by IP
)
async def login_for_access_token(
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
