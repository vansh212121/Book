# # app/utils/deps.py
"""
FastAPI Dependencies for Authentication, Authorization, and Request Processing.
This module focuses purely on dependency injection, delegating business logic to services.
"""

import logging
from typing import Optional
from datetime import datetime

from fastapi import Depends, HTTPException, status, Request, Query
from fastapi.security import OAuth2PasswordBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.security import token_manager, TokenType
from app.db.session import get_session
from app.models.user_model import User, UserRole
from app.core.exceptions import (
    InvalidToken,
    NotAuthorized,
    ResourceNotFound,
    InactiveUser,
    UnverifiedUser,
)

# Services - injected, not imported directly
from app.services.user_service import UserService 
from app.services.rate_limit_service import RateLimitService, rate_limit_service

# Setup logging
logger = logging.getLogger(__name__)

# OAuth2 scheme for token extraction
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login", description="JWT Access Token"
)


# ================== CORE AUTHENTICATION DEPENDENCIES ==================
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_session),
    token: str = Depends(reusable_oauth2),
    # Inject services as dependencies to prevent circular imports
    user_svc: UserService = Depends(),
    rate_limit_svc: RateLimitService = Depends(),
) -> User:
    """
    Primary authentication dependency. Validates JWT and returns current user.
    """
    client_ip = request.client.host if request.client else "unknown"

    if await rate_limit_svc.is_auth_rate_limited(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed authentication attempts.",
        )

    try:
        payload = await token_manager.verify_token(
            token, expected_type=TokenType.ACCESS
        )
        user_id = int(payload.get("sub"))
    except InvalidToken as e:
        await rate_limit_svc.record_failed_auth_attempt(client_ip)
        raise e

    user = await user_svc.get_user_for_auth(db=db, user_id=user_id)
    if not user:
        raise ResourceNotFound(detail=f"User with id {user_id} not found.")

    await rate_limit_svc.clear_failed_auth_attempts(client_ip)
    request.state.user = user
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user is active."""
    if not current_user.is_active:
        logger.warning(
            "Inactive user attempted access",
            extra={"user_id": str(current_user.id), "user_email": current_user.email},
        )
        raise InactiveUser()
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Ensure the current user is verified."""
    if not current_user.is_verified:
        logger.info(
            "Unverified user attempted access",
            extra={"user_id": str(current_user.id), "user_email": current_user.email},
        )
        raise UnverifiedUser()
    return current_user


# ================== AUTHORIZATION DEPENDENCIES ==================


class RoleChecker:
    """
    Dependency class for role-based access control.
    Uses hierarchical role checking based on UserRole enum priorities.
    """

    def __init__(self, required_role: UserRole):
        self.required_role = required_role

    def __call__(
        self, request: Request, current_user: User = Depends(get_current_active_user)
    ) -> User:
        """Check if user has sufficient role privileges."""
        if current_user.role < self.required_role:
            logger.warning(
                "Insufficient privileges for user.",
                extra={
                    "user_id": str(current_user.id),
                    "user_role": current_user.role.value,
                    "required_role": self.required_role.value,
                    "path": request.url.path,
                },
            )
            raise NotAuthorized(
                detail=f"Insufficient privileges. A role of '{self.required_role.value}' or higher is required."
            )
        return current_user


# Role-based dependency instances
require_user = RoleChecker(UserRole.USER)
require_moderator = RoleChecker(UserRole.MODERATOR)
require_admin = RoleChecker(UserRole.ADMIN)


# ================== RATE LIMITING DEPENDENCIES ==================


class RateLimitChecker:
    """
    Dependency for rate limiting. Delegates actual limiting logic to service layer.
    """

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60,
        identifier_type: str = "ip",  # "ip" or "user"
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.identifier_type = identifier_type

    async def __call__(self, request: Request):
        """Check rate limits using service layer."""
        # Get identifier
        if self.identifier_type == "user":
            user = getattr(request.state, "user", None)
            identifier = f"user:{user.id}" if user else f"ip:{request.client.host}"
        else:
            identifier = f"ip:{request.client.host if request.client else 'unknown'}"

        # Check rate limit (delegated to service)
        if await rate_limit_service.is_rate_limited(
            identifier, self.max_requests, self.window_seconds
        ):
            logger.warning(f"Rate limit exceeded for {identifier}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.max_requests} requests per {self.window_seconds} seconds.",
                headers={"Retry-After": str(self.window_seconds)},
            )


# Rate limiting instances for different use cases
rate_limit_auth = RateLimitChecker(
    max_requests=5, window_seconds=60, identifier_type="ip"
)
rate_limit_api = RateLimitChecker(
    max_requests=100, window_seconds=60, identifier_type="user"
)
rate_limit_heavy = RateLimitChecker(
    max_requests=10, window_seconds=60, identifier_type="user"
)


# ================== UTILITY DEPENDENCIES ==================


class PaginationParams:
    """Pagination parameters for list endpoints."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(20, ge=1, le=100, description="Page size"),
    ):
        self.page = page
        self.size = size
        self.skip = (page - 1) * size
        self.limit = size


async def get_pagination_params(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
) -> PaginationParams:
    """Get pagination parameters as a dependency."""
    return PaginationParams(page=page, size=size)


# ================== HEALTH CHECK DEPENDENCIES ==================


async def get_health_status():
    """
    Health check dependency. Delegates actual health checks to service layer.
    """
    # This could be delegated to a health_service if you have complex health checks
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": getattr(settings, "APP_VERSION", "unknown"),
    }


# ================== REQUEST CONTEXT DEPENDENCIES ==================


async def get_request_context(request: Request) -> dict:
    """Extract common request context information."""
    return {
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
        "path": request.url.path,
        "method": request.method,
    }


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_session),
    token: Optional[str] = Depends(reusable_oauth2),
) -> Optional[User]:
    """
    Optional authentication - returns None if no valid token.
    Useful for endpoints that work for both authenticated and anonymous users.
    """
    if not token:
        return None

    try:
        return await get_current_user(request, db, token)
    except (InvalidToken, ResourceNotFound):
        return None


# ================== EXPORTS ==================

__all__ = [
    # Core Authentication
    "get_current_user",
    "get_current_active_user",
    "get_current_verified_user",
    "get_current_user_optional",
    # Authorization
    "RoleChecker",
    "require_admin",
    "require_moderator",
    "require_user",
    # Rate Limiting
    "RateLimitChecker",
    "rate_limit_auth",
    "rate_limit_api",
    "rate_limit_heavy",
    # Utilities
    "PaginationParams",
    "get_pagination_params",
    "get_health_status",
    "get_request_context",
]
