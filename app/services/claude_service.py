# import logging
# from datetime import timedelta
# from typing import Dict, Any, Optional, List

# from app.core.security import token_manager, password_manager, TokenType
# from app.core.exceptions import InvalidCredentials, UserNotFoundError, InvalidToken
# from app.repositories.user_repository import user_repository
# from app.repositories.session_repository import session_repository  # Hypothetical
# from app.schemas.auth_schema import LoginRequest, TokenResponse
# from sqlmodel.ext.asyncio.session import AsyncSession

# logger = logging.getLogger(__name__)

# class AuthService:
#     """
#     Handles authentication business logic - login, logout, token management.
#     This is where the "logout from all devices" logic belongs.
#     """
    
#     def __init__(self):
#         self.token_manager = token_manager
#         self.password_manager = password_manager
#         self.user_repo = user_repository
#         # self.session_repo = session_repository  # For tracking active sessions

#     async def authenticate_user(self, db: AsyncSession, email: str, password: str) -> Dict[str, Any]:
#         """Authenticate user and return token pair."""
#         # Business logic: Find and validate user
#         user = await self.user_repo.get_by_email(db, email=email)
#         if not user:
#             raise InvalidCredentials("Invalid email or password")
        
#         if not user.is_active:
#             raise InvalidCredentials("Account is deactivated")
        
#         if not self.password_manager.verify_password(password, user.hashed_password):
#             raise InvalidCredentials("Invalid email or password")
        
#         # Business logic: Check if password needs rehashing
#         if self.password_manager.needs_rehash(user.hashed_password):
#             new_hash = self.password_manager.hash_password(password)
#             await self.user_repo.update_fields(db, obj_id=user.id, fields={"hashed_password": new_hash})
        
#         # Create token pair
#         token_pair = self.create_token_pair(str(user.id))
        
#         # Business logic: Track active session (optional)
#         # await self.session_repo.create_session(db, user_id=user.id, refresh_token_jti=refresh_jti)
        
#         logger.info(f"User authenticated: {user.id}")
#         return {
#             **token_pair,
#             "user": {
#                 "id": user.id,
#                 "email": user.email,
#                 "username": user.username,
#             }
#         }

#     def create_token_pair(self, user_id: str) -> Dict[str, Any]:
#         """Create access and refresh token pair."""
#         access_token = self.token_manager.create_token(
#             subject=user_id, 
#             token_type=TokenType.ACCESS
#         )
#         refresh_token = self.token_manager.create_token(
#             subject=user_id, 
#             token_type=TokenType.REFRESH
#         )
        
#         return {
#             "access_token": access_token,
#             "refresh_token": refresh_token,
#             "token_type": "bearer",
#             "expires_in": self.token_manager.config.ACCESS_TOKEN_EXPIRE_MINUTES * 60
#         }

#     async def refresh_tokens(self, refresh_token: str) -> Dict[str, Any]:
#         """Refresh token pair using valid refresh token."""
#         # Verify the refresh token
#         payload = await self.token_manager.verify_token(refresh_token, TokenType.REFRESH)
#         user_id = payload["sub"]
        
#         # Business logic: Verify user still exists and is active
#         # user = await self.user_repo.get(db, obj_id=int(user_id))
#         # if not user or not user.is_active:
#         #     raise InvalidToken("User no longer exists or is inactive")
        
#         # Security: Revoke the used refresh token (single-use)
#         await self.token_manager.revoke_token(refresh_token, reason="Token refreshed")
        
#         # Create new token pair
#         new_tokens = self.create_token_pair(user_id)
        
#         logger.info(f"Tokens refreshed for user: {user_id}")
#         return new_tokens

#     async def logout(self, access_token: str, refresh_token: Optional[str] = None) -> bool:
#         """Logout from current session."""
#         success = True
        
#         # Revoke access token
#         if not await self.token_manager.revoke_token(access_token, reason="User logout"):
#             success = False
        
#         # Revoke refresh token if provided
#         if refresh_token:
#             if not await self.token_manager.revoke_token(refresh_token, reason="User logout"):
#                 success = False
        
#         if success:
#             # Extract user ID for logging
#             payload = self.token_manager.decode_token_unsafe(access_token)
#             user_id = payload.get("sub") if payload else "unknown"
#             logger.info(f"User logged out: {user_id}")
        
#         return success

#     async def logout_all_devices(self, db: AsyncSession, user_id: int) -> int:
#         """
#         Business logic: Logout user from all devices.
#         This is the function you mentioned that should be in service layer!
#         """
#         # Method 1: If you track active sessions in database
#         # active_sessions = await self.session_repo.get_user_sessions(db, user_id=user_id)
#         # revoked_count = 0
#         # for session in active_sessions:
#         #     if await self.token_manager.revoke_token_by_jti(session.refresh_token_jti, session.expires_at):
#         #         revoked_count += 1
#         # await self.session_repo.deactivate_user_sessions(db, user_id=user_id)
        
#         # Method 2: Using Redis pattern matching (less reliable but simpler)
#         # This would require storing tokens with user ID pattern
        
#         # Method 3: User-level token invalidation timestamp (recommended)
#         user = await self.user_repo.get(db, obj_id=user_id)
#         if not user:
#             raise UserNotFoundError(f"User {user_id} not found")
        
#         # Update user's token_valid_after timestamp
#         # All tokens issued before this timestamp become invalid
#         from datetime import datetime, timezone
#         await self.user_repo.update_fields(
#             db, 
#             obj_id=user_id, 
#             fields={"tokens_valid_after": datetime.now(timezone.utc)}
#         )
        
#         logger.info(f"All tokens invalidated for user: {user_id}")
#         return 1  # Return number of "sessions" invalidated

#     async def change_password(self, db: AsyncSession, user_id: int, old_password: str, new_password: str) -> bool:
#         """Business logic: Change password and invalidate all sessions."""
#         # Get user
#         user = await self.user_repo.get(db, obj_id=user_id)
#         if not user:
#             raise UserNotFoundError(f"User {user_id} not found")
        
#         # Verify old password
#         if not self.password_manager.verify_password(old_password, user.hashed_password):
#             raise InvalidCredentials("Current password is incorrect")
        
#         # Hash new password
#         new_hash = self.password_manager.hash_password(new_password)
        
#         # Update password and invalidate all tokens
#         from datetime import datetime, timezone
#         await self.user_repo.update_fields(db, obj_id=user_id, fields={
#             "hashed_password": new_hash,
#             "tokens_valid_after": datetime.now(timezone.utc)
#         })
        
#         logger.info(f"Password changed and all tokens invalidated for user: {user_id}")
#         return True

#     async def validate_access_token(self, token: str) -> Dict[str, Any]:
#         """Validate access token and return user info."""
#         payload = await self.token_manager.verify_token(token, TokenType.ACCESS)
        
#         # Additional business validation could go here
#         # e.g., check user's tokens_valid_after timestamp
        
#         return payload

#     async def create_verification_token(self, user_id: int, token_type: TokenType) -> str:
#         """Create verification tokens (email, password reset)."""
#         if token_type not in [TokenType.EMAIL_VERIFICATION, TokenType.PASSWORD_RESET]:
#             raise ValueError(f"Invalid verification token type: {token_type}")
        
#         # Different expiry times for different verification types
#         expires_delta = timedelta(hours=24) if token_type == TokenType.EMAIL_VERIFICATION else timedelta(hours=1)
        
#         return self.token_manager.create_token(
#             subject=str(user_id),
#             token_type=token_type,
#             expires_delta=expires_delta
#         )

#     async def verify_verification_token(self, token: str, expected_type: TokenType) -> Dict[str, Any]:
#         """Verify email/password reset tokens."""
#         payload = await self.token_manager.verify_token(token, expected_type)
        
#         # Mark token as used (single-use verification tokens)
#         await self.token_manager.revoke_token(token, reason="Verification token used")
        
#         return payload

# # Singleton instance
# auth_service = AuthService()