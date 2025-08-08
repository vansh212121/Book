# app/services/auth_service.py
"""
Authentication service module.

Handles user authentication, registration, and token management.
"""
import logging
from typing import Optional, Dict

from fastapi import BackgroundTasks
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, timezone, timedelta
from app.crud.user_crud import user_repository
from app.services.rate_limit_service import rate_limit_service

from app.schemas.token_schema import TokenResponse
from app.schemas.auth_schema import (
    PasswordChange,
    PasswordResetConfirm,
)
from app.models.user_model import User
from app.core.security import token_manager, TokenType, password_manager
from app.tasks.email_tasks import (
    send_password_reset_email_task,
    send_verification_email_task,
    send_email_change_confirmation_task,
)

from app.services.cache_service import cache_service
from app.core.exception_utils import raise_for_status
from app.core.exceptions import (
    ResourceAlreadyExists,
    InactiveUser,
    InvalidCredentials,
    ResourceNotFound,
    InvalidToken,
    UnverifiedUser,
    InternalServerError,
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

    def create_token_pair(self, *, user: User) -> TokenResponse:
        """
        Creates and returns a new access and refresh token pair for a user.
        This is a helper method used by login and refresh flows.
        """
        access_token = token_manager.create_token(
            subject=str(user.id), token_type=TokenType.ACCESS
        )
        refresh_token = token_manager.create_token(
            subject=str(user.id), token_type=TokenType.REFRESH
        )

        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    async def login(
        self, db: AsyncSession, *, email: str, password: str, client_ip: str
    ) -> TokenResponse:
        """The core authentication workflow."""
        # 1. Brute-force protection check
        if await rate_limit_service.is_auth_rate_limited(client_ip):
            raise InvalidCredentials(
                detail="Too many failed login attempts. Please try again later."
            )

        # 2. Fetch the user from the database
        user = await user_repository.get_by_email(db, email=email)

        # 3. Verify the user and password
        password_is_valid = user and password_manager.verify_password(
            password, user.hashed_password
        )

        if not password_is_valid:
            await rate_limit_service.record_failed_auth_attempt(client_ip)
            raise InvalidCredentials()

        # 4. Check if the user's account is active
        if not user.is_active:
            raise InactiveUser()

        if not user.is_verified:
            raise UnverifiedUser()

        # 5. On successful login, clear any previous failed attempts
        await rate_limit_service.clear_failed_auth_attempts(client_ip)

        # 6. Check if the password needs to be re-hashed with stronger parameters
        if password_manager.needs_rehash(user.hashed_password):
            user.hashed_password = password_manager.hash_password(password)
            db.add(user)
            await db.commit()
            await cache_service.invalidate_user(user.id)
            logger.info(f"Password re-hashed for user {user.id}")

        # Use the helper to create the token pair
        token_response = self.create_token_pair(user=user)

        logger.info(f"User {user.id} logged in successfully.")
        return token_response

    async def refresh_token(
        self, db: AsyncSession, *, refresh_token: str
    ) -> TokenResponse:
        """
        Refreshes a user's session using a valid refresh token.
        Implements Refresh Token Rotation for enhanced security.
        """
        # 1. Verify the refresh token. This also checks the blacklist.
        payload = await token_manager.verify_token(
            refresh_token, expected_type=TokenType.REFRESH
        )
        user_id = int(payload.get("sub"))

        # 2. Fetch the user from the database
        user = await user_repository.get(db, obj_id=user_id)
        if not user or not user.is_active:
            raise InvalidCredentials(detail="User not found or inactive.")

        # 3. Revoke the old refresh token (one-time use)
        #    Revoke the old refresh token and ensure the operation was successful.
        revoked_successfully = await token_manager.revoke_token(
            refresh_token, reason="Token refreshed"
        )

        # If the revocation fails, we must not issue a new token.
        # This is a critical security backstop.
        if not revoked_successfully:
            raise InternalServerError(
                detail="Could not refresh token. Please try logging in again."
            )

        # 4. Issue a new token pair
        new_token_response = self.create_token_pair(user=user)

        logger.info(f"Token refreshed for user {user.id}")
        return new_token_response

    async def logout(self, *, access_token: str, refresh_token: str) -> None:
        """
        Logs a user out by revoking their current access and refresh tokens.
        """
        await token_manager.revoke_token(access_token, reason="User logout")
        await token_manager.revoke_token(refresh_token, reason="User logout")
        logger.info("User logged out successfully.")

    async def revoke_all_user_tokens(self, db: AsyncSession, *, user: User):
        """
        Revokes all tokens for a user by updating the tokens_valid_from_utc timestamp.
        """
        # Set the revocation timestamp to the current time
        await user_repository.update(
            db=db,
            user=user,
            fields_to_update={"tokens_valid_from_utc": datetime.now(timezone.utc)},
        )
        # Important: Invalidate the cache so the next fetch gets the new timestamp
        await cache_service.invalidate_user(user.id)
        self._logger.info(f"All tokens revoked for user {user.id}")

    # -------PASSWORD------
    async def change_password(
        self, db: AsyncSession, *, user: User, password_data: PasswordChange
    ):
        """
        Allows an authenticated user to change their own password.
        """
        # 1. Verify the user's current password is correct.
        if not password_manager.verify_password(
            password_data.current_password, user.hashed_password
        ):
            raise InvalidCredentials(detail="Incorrect current password.")

        # 2. Hash the new password.
        new_hashed_password = password_manager.hash_password(password_data.new_password)

        # 3. Update the password in the database.
        await user_repository.update(
            db, user=user, fields_to_update={"hashed_password": new_hashed_password}
        )

        # 4. For security, revoke all existing tokens after a password change.
        await self.revoke_all_user_tokens(db, user=user)

        self._logger.info(f"Password changed successfully for user {user.id}")

    async def request_password_reset(
        self,
        db: AsyncSession,
        *,
        background_tasks: Optional[BackgroundTasks] = None,
        email: str,
    ) -> Dict[str, str]:
        """
        Request password reset email.

        Args:
            email: User email
            db: Database session
            background_tasks: Background tasks

        Returns:
            Success message (always succeeds for security)
        """
        user = await self.user_repository.get_by_email(email=email, db=db)

        raise_for_status(
            condition=(user is None),
            exception=ResourceNotFound,
            detail=f"User not found.",
            resource_type="User",
        )

        if user and user.is_active:
            reset_token = token_manager.create_token(
                subject=user.id,
                token_type=TokenType.PASSWORD_RESET,
                expires_delta=timedelta(hours=1),
                additional_claims={"user_id": str(user.id)},
            )
            # Send reset email
            await self._send_password_reset_email(user, reset_token)

            self._logger.info(f"Password reset requested for: {email}")
        else:
            # Log attempt but don't reveal if user exists
            self._logger.warning(f"Password reset requested for unknown email: {email}")

        # Always return success for security
        return {
            "message": "If the email exists in our system, you will receive a password reset link"
        }

    async def reset_password(
        self, db: AsyncSession, *, reset_data: PasswordResetConfirm
    ):
        """Finalizes the password reset process using a valid token."""
        # 1. Verify the token
        payload = await token_manager.verify_token(
            reset_data.token, expected_type=TokenType.PASSWORD_RESET
        )
        # --- FIX: Get the user ID from the 'sub' claim ---
        user_id = int(payload.get("sub"))

        # 2. Fetch the user
        user = await self.user_repository.get(db, obj_id=user_id)
        if not user or not user.is_active:
            # Use a generic error to avoid confirming if a user exists/is inactive
            raise InvalidToken(detail="Invalid token or user is inactive.")

        # 3. Hash the new password
        new_hashed_password = password_manager.hash_password(reset_data.new_password)

        # 4. Update the user's password using the correct repository method
        await self.user_repository.update(
            db=db, user=user, fields_to_update={"hashed_password": new_hashed_password}
        )

        # 5. Revoke all other tokens for security
        await self.revoke_all_user_tokens(db=db, user=user)  # <-- FIX: Added 'db'

        # 6. Revoke the reset token itself so it can't be reused
        await token_manager.revoke_token(token=reset_data.token, reason="used")

        self._logger.info(f"Password has been reset for user {user.id}")
        return {"message": "Password has been reset successfully"}

    # ------EMAIL-------
    async def request_email_change(
        self, db: AsyncSession, *, user: User, new_email: str
    ):
        """Initiates the two-step email change process."""
        if await user_repository.exists_by_email(db, email=new_email):
            raise ResourceAlreadyExists(
                f"The email address '{new_email}' is already in use."
            )

        additional_claims = {"new_email": new_email}
        change_token = token_manager.create_token(
            subject=str(user.id),
            token_type=TokenType.EMAIL_CHANGE,
            additional_claims=additional_claims,
        )
        await self._send_email_change_confirmation_email(user, new_email, change_token)
        logger.info(
            f"Email change requested for user {user.id} to new email {new_email}"
        )

    async def confirm_email_change(self, db: AsyncSession, *, token: str) -> User:
        """
        Confirms and finalizes an email change using a valid token.
        This follows the user-friendly flow we designed.
        """
        # 1. Verify the token is a valid EMAIL_CHANGE token.
        payload = await token_manager.verify_token(
            token, expected_type=TokenType.EMAIL_CHANGE
        )
        user_id = int(payload.get("sub"))
        new_email = payload.get("new_email")

        if not new_email:
            raise InvalidToken(
                detail="Invalid email change token: missing new email claim."
            )

        # 2. Fetch the user from the database.
        user = await user_repository.get(db, obj_id=user_id)
        if not user or not user.is_active:
            raise InvalidToken(detail="Invalid token or user is inactive.")

        # 3. ** THE FIX IS HERE **
        #    Update the user's email. We do NOT change is_verified, because
        #    clicking the link sent to the new email IS the verification.
        updated_user = await user_repository.update(
            db, user=user, fields_to_update={"email": new_email}
        )

        # 4. For security, revoke all old sessions and invalidate the cache.
        await self.revoke_all_user_tokens(db, user=updated_user)

        logger.info(f"Email successfully changed for user {user.id} to {new_email}")
        return updated_user

    async def request_verification_email(self, db: AsyncSession, *, email: str):
        """Sends a verification email to a user."""
        user = await user_repository.get_by_email(db, email=email)
        if user and not user.is_verified:
            await self._send_verification_email(user)
        logger.info(f"Verification email requested for: {email}")

    async def verify_email(self, db: AsyncSession, *, token: str) -> User:
        """Verifies a user's email address using a valid token."""
        payload = await token_manager.verify_token(
            token, expected_type=TokenType.EMAIL_VERIFICATION
        )
        user_id = int(payload.get("sub"))

        user = await user_repository.get(db, obj_id=user_id)
        if not user:
            raise InvalidToken(detail="Invalid verification token.")

        if user.is_verified:
            return user

        verified_user = await user_repository.update(
            db, user=user, fields_to_update={"is_verified": True}
        )

        await cache_service.invalidate_user(user.id)

        logger.info(f"Email successfully verified for user {user.first_name}")
        return verified_user

    async def send_verification_email(self, user: User):
        """
        Creates a verification token and dispatches the email-sending task.
        This is a public method that can be called by other services.
        """
        # This reuses the logic from our private helper.
        await self._send_verification_email(user)

    # --- Private Helper Methods for Email Sending (Simulated) ---
    async def _send_verification_email(self, user: User):
        """
        Helper to create a token and dispatch the verification email task.
        """
        # 1. Create the token
        token = token_manager.create_token(
            subject=str(user.id), token_type=TokenType.EMAIL_VERIFICATION
        )

        # 2. Dispatch the Celery task
        send_verification_email_task.delay(email_to=user.email, token=token)

        self._logger.info(f"Dispatched verification email task for {user.email}")

    async def _send_email_change_confirmation_email(
        self, user: User, new_email: str, token: str
    ):
        """
        Dispatches a Celery task to send an email reset email.
        """
        send_email_change_confirmation_task.delay(email_to=new_email, token=token)

        # We can still log that the task was dispatched.
        logger.info(
            f"Dispatched a change Email verification email task for {user.email}"
        )

    async def _send_password_reset_email(self, user: User, token: str):
        """
        Dispatches a Celery task to send a password reset email.
        """
        send_password_reset_email_task.delay(email_to=user.email, token=token)

        # We can still log that the task was dispatched.
        logger.info(f"Dispatched password reset email task for {user.email}")


auth_service = AuthService()
