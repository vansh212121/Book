# app/services/auth_service.py
"""
Authentication service module.

Handles user authentication, registration, and token management.
"""
import logging
from typing import Optional, Dict, Any

from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, timezone
from app.crud.user_crud import user_repository
from app.services.rate_limit_service import rate_limit_service

from app.schemas.token_schema import TokenResponse
from app.models.user_model import User, UserRole
from app.core.security import token_manager, TokenType

from app.services import cache_service
from app.core.exception_utils import raise_for_status
from app.core.exceptions import (
    RateLimitExceeded,
    InactiveUser,
    InvalidCredentials,
    ValidationError,
    ResourceAlreadyExists,
)
from app.core.security import password_manager

logger = logging.getLogger(__name__)


class AuthService:
    """
    Service class for authentication operations.

    Handles user registration, login, logout, password reset,
    and email verification with comprehensive security features.
    """

    def __init__(self):
        self.user_repository = user_repository
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def login(
        self, 
        db: AsyncSession, 
        *, 
        email: str, 
        password: str, 
        client_ip: str
    ) -> TokenResponse:
        """
        The core authentication workflow.

        Args:
            db: The database session.
            email: The user's email.
            password: The user's plain-text password.
            client_ip: The IP address of the user making the request.

        Returns:
            A TokenResponse containing the new access and refresh tokens.

        Raises:
            InvalidCredentials: If the email or password is incorrect, or if the user is rate-limited.
            InactiveUser: If the user's account is deactivated.
        """
        # 1. Brute-force protection check
        if await rate_limit_service.is_auth_rate_limited(client_ip):
            raise InvalidCredentials(detail="Too many failed login attempts. Please try again later.")

        # 2. Fetch the user from the database
        user = await user_repository.get_by_email(db, email=email)
        
        # 3. Verify the user and password
        # We use a combined check to prevent "user enumeration" attacks.
        password_is_valid = user and password_manager.verify_password(password, user.hashed_password)
        
        if not password_is_valid:
            # If the login attempt is invalid, record the failure and then raise.
            await rate_limit_service.record_failed_auth_attempt(client_ip)
            raise InvalidCredentials()

        # 4. Check if the user's account is active
        if not user.is_active:
            raise InactiveUser()

        # 5. On successful login, clear any previous failed attempts
        await rate_limit_service.clear_failed_auth_attempts(client_ip)

        # 6. Check if the password needs to be re-hashed with stronger parameters
        if password_manager.needs_rehash(user.hashed_password):
            user.hashed_password = password_manager.hash_password(password)
            db.add(user)
            await db.commit()
            # Invalidate the cache since we updated the user object
            await cache_service.invalidate_user(user.id)
            logger.info(f"Password re-hashed for user {user.id}")

        # 7. Create a new token pair by calling the token_manager twice.
        # This is the business logic for creating a "token pair".
        access_token = token_manager.create_token(
            subject=str(user.id), token_type=TokenType.ACCESS
        )
        refresh_token = token_manager.create_token(
            subject=str(user.id), token_type=TokenType.REFRESH
        )
        
        logger.info(f"User {user.id} logged in successfully.")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token
        )


auth_service = AuthService()
