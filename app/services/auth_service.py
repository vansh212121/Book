# # app/services/auth_service.py
# """
# Authentication service module.

# Handles user authentication, registration, and token management.
# """

# import logging
# from datetime import datetime, timedelta
# from typing import Optional, Dict, Any

# from sqlmodel.ext.asyncio.session import AsyncSession
# from fastapi import BackgroundTasks
# from fastapi.security import OAuth2PasswordRequestForm

# from app.core.security import (
#     token_manager,
#     hash_password,
#     verify_password,
#     needs_rehash,
#     generate_secure_token,
#     TokenType
# )
# from app.crud.user_crud import UserRepository
# from app.schemas.auth_schema import (
#     UserLogin,
#     UserRegister,
#     TokenResponse,
#     PasswordReset,
#     PasswordResetConfirm
# )
# from app.schemas.user_schema import UserCreate
# from app.models.user_model import User, UserRole
# from app.core.exceptions import (
#     InvalidCredentials,
#     InactiveUser,
#     UnverifiedUser,
#     NotAuthorized,
#     UserAlreadyExists,
#     InvalidToken,
#     ValidationError
# )
# from app.core.config import settings
# from app.db.redis_conn import redis_client

# # Import email tasks based on your setup
# try:
#     from app.celery_tasks import (
#         send_verification_email_task,
#         send_password_reset_email_task,
#         send_welcome_email_task
#     )
#     USE_CELERY = True
# except ImportError:
#     USE_CELERY = False
#     from app.utils.email import send_email

# logger = logging.getLogger(__name__)


# class AuthService:
#     """
#     Service class for authentication operations.
    
#     Handles user registration, login, logout, password reset,
#     and email verification with comprehensive security features.
#     """
    
#     def __init__(self):
#         self.user_repository = UserRepository()
#         self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
#     async def register(
#         self,
#         user_data: UserRegister,
#         db: AsyncSession,
#         background_tasks: Optional[BackgroundTasks] = None
#     ) -> User:
#         """
#         Register a new user with email verification.
        
#         Args:
#             user_data: Registration data
#             db: Database session
#             background_tasks: Background tasks for email sending
            
#         Returns:
#             Created user
            
#         Raises:
#             UserAlreadyExists: If email/username already registered
#             ValidationError: If validation fails
#         """
#         # Check if user exists
#         existing_user = await self.user_repository.get_by_email(user_data.email, db)
#         if existing_user:
#             raise UserAlreadyExists(email=user_data.email)
        
#         if user_data.username:
#             existing_username = await self.user_repository.get_by_username(
#                 user_data.username, db
#             )
#             if existing_username:
#                 raise UserAlreadyExists(
#                     detail=f"Username '{user_data.username}' is already taken"
#                 )
        
#         # Hash password
#         hashed_password = hash_password(user_data.password)
        
#         # Create user
#         user_create = UserCreate(
#             email=user_data.email,
#             username=user_data.username,
#             full_name=user_data.full_name,
#             hashed_password=hashed_password,
#             role=UserRole.USER,
#             is_active=True,
#             is_verified=False
#         )
        
#         user = await self.user_repository.create(user_create, db)
        
#         # Send verification email
#         await self._send_verification_email(user, background_tasks)
        
#         # Send welcome email
#         if settings.SEND_WELCOME_EMAIL:
#             await self._send_welcome_email(user, background_tasks)
        
#         self._logger.info(
#             f"User registered: {user.email}",
#             extra={
#                 "user_id": user.id,
#                 "email": user.email,
#                 "username": user.username
#             }
#         )
        
#         return user
    
#     async def login(
#         self,
#         credentials: OAuth2PasswordRequestForm,
#         db: AsyncSession,
#         user_agent: Optional[str] = None,
#         ip_address: Optional[str] = None
#     ) -> TokenResponse:
#         """
#         Authenticate user and return tokens.
        
#         Args:
#             credentials: Login credentials
#             db: Database session
#             user_agent: Client user agent
#             ip_address: Client IP address
            
#         Returns:
#             Token response with access and refresh tokens
            
#         Raises:
#             InvalidCredentials: If credentials are invalid
#             InactiveUser: If account is inactive
#             UnverifiedUser: If email not verified (based on settings)
#         """
#         # Get user by email (username field contains email)
#         user = await self.user_repository.get_by_email(credentials.username, db)
        
#         if not user or not verify_password(credentials.password, user.hashed_password):
#             self._logger.warning(
#                 f"Failed login attempt",
#                 extra={
#                     "email": credentials.username,
#                     "ip_address": ip_address,
#                     "user_agent": user_agent
#                 }
#             )
#             raise InvalidCredentials()
        
#         # Check if password needs rehashing
#         if needs_rehash(user.hashed_password):
#             new_hash = hash_password(credentials.password)
#             await self.user_repository.update_password(user.id, new_hash, db)
        
#         # Check account status
#         if not user.is_active:
#             raise InactiveUser()
        
#         # Check email verification if required
#         if settings.REQUIRE_EMAIL_VERIFICATION and not user.is_verified:
#             raise UnverifiedUser()
        
#         # Create tokens
#         token_pair = token_manager.create_token_pair(
#             subject=user.email,
#             additional_claims={
#                 "user_id": str(user.id),
#                 "role": user.role.value,
#                 "is_verified": user.is_verified,
#                 "permissions": self._get_user_permissions(user)
#             }
#         )
        
#         # Update last login
#         await self.user_repository.update_last_login(user.id, db)
        
#         # Log successful login
#         self._logger.info(
#             f"User logged in",
#             extra={
#                 "user_id": user.id,
#                 "email": user.email,
#                 "ip_address": ip_address,
#                 "user_agent": user_agent
#             }
#         )
        
#         return TokenResponse(**token_pair)
    
#     async def login_admin(
#         self,
#         credentials: OAuth2PasswordRequestForm,
#         db: AsyncSession,
#         user_agent: Optional[str] = None,
#         ip_address: Optional[str] = None
#     ) -> TokenResponse:
#         """
#         Admin login with additional security checks.
        
#         Args:
#             credentials: Login credentials
#             db: Database session
#             user_agent: Client user agent
#             ip_address: Client IP address
            
#         Returns:
#             Token response
            
#         Raises:
#             NotAuthorized: If user is not admin/moderator
#         """
#         # First authenticate normally
#         user = await self.user_repository.get_by_email(credentials.username, db)
        
#         if not user or not verify_password(credentials.password, user.hashed_password):
#             raise InvalidCredentials()
        
#         # Check if user has admin privileges
#         if user.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
#             self._logger.warning(
#                 f"Non-admin login attempt to admin portal",
#                 extra={
#                     "user_id": user.id,
#                     "email": user.email,
#                     "role": user.role.value
#                 }
#             )
#             raise NotAuthorized(
#                 detail="Access denied. Admin privileges required."
#             )
        
#         # Admin accounts must be verified
#         if not user.is_verified:
#             raise UnverifiedUser()
        
#         if not user.is_active:
#             raise InactiveUser()
        
#         # Create tokens with admin flag
#         token_pair = token_manager.create_token_pair(
#             subject=user.email,
#             additional_claims={
#                 "user_id": str(user.id),
#                 "role": user.role.value,
#                 "is_verified": user.is_verified,
#                 "is_admin": True,
#                 "permissions": self._get_user_permissions(user)
#             }
#         )
        
#         # Update last login
#         await self.user_repository.update_last_login(user.id, db)
        
#         self._logger.info(
#             f"Admin logged in",
#             extra={
#                 "user_id": user.id,
#                 "email": user.email,
#                 "role": user.role.value,
#                 "ip_address": ip_address
#             }
#         )
        
#         return TokenResponse(**token_pair)
    
#     async def logout(
#         self,
#         access_token: str,
#         refresh_token: Optional[str] = None
#     ) -> Dict[str, str]:
#         """
#         Logout user by revoking tokens.
        
#         Args:
#             access_token: Access token to revoke
#             refresh_token: Optional refresh token to revoke
            
#         Returns:
#             Success message
#         """
#         # Revoke access token
#         await token_manager.revoke_token(access_token, "logout")
        
#         # Revoke refresh token if provided
#         if refresh_token:
#             await token_manager.revoke_token(refresh_token, "logout")
        
#         self._logger.info("User logged out successfully")
        
#         return {"message": "Successfully logged out"}
    
#     async def refresh_tokens(
#         self,
#         refresh_token: str,
#         db: AsyncSession
#     ) -> TokenResponse:
#         """
#         Refresh access token using refresh token.
        
#         Args:
#             refresh_token: Valid refresh token
#             db: Database session
            
#         Returns:
#             New token pair
            
#         Raises:
#             InvalidToken: If refresh token is invalid
#         """
#         try:
#             # Verify and refresh tokens
#             token_pair = await token_manager.refresh_token_pair(refresh_token)
            
#             # Get user to check if still active
#             payload = await token_manager.verify_token(
#                 refresh_token,
#                 expected_type=TokenType.REFRESH
#             )
#             user = await self.user_repository.get_by_email(payload["sub"], db)
            
#             if not user or not user.is_active:
#                 raise InvalidToken("User account is no longer active")
            
#             # Add updated claims
#             token_pair = token_manager.create_token_pair(
#                 subject=user.email,
#                 additional_claims={
#                     "user_id": str(user.id),
#                     "role": user.role.value,
#                     "is_verified": user.is_verified,
#                     "permissions": self._get_user_permissions(user)
#                 }
#             )
            
#             self._logger.info(f"Tokens refreshed for user: {user.id}")
            
#             return TokenResponse(**token_pair)
            
#         except Exception as e:
#             self._logger.error(f"Token refresh failed: {e}")
#             raise InvalidToken(detail="Invalid or expired refresh token")
    
#     async def request_password_reset(
#         self,
#         email: str,
#         db: AsyncSession,
#         background_tasks: Optional[BackgroundTasks] = None
#     ) -> Dict[str, str]:
#         """
#         Request password reset email.
        
#         Args:
#             email: User email
#             db: Database session
#             background_tasks: Background tasks
            
#         Returns:
#             Success message (always succeeds for security)
#         """
#         user = await self.user_repository.get_by_email(email, db)
        
#         if user and user.is_active:
#             # Create reset token
#             reset_token = token_manager.create_token(
#                 subject=user.email,
#                 token_type=TokenType.RESET_PASSWORD,
#                 expires_delta=timedelta(hours=1),
#                 additional_claims={"user_id": str(user.id)}
#             )
            
#             # Send reset email
#             await self._send_password_reset_email(
#                 user, reset_token, background_tasks
#             )
            
#             self._logger.info(f"Password reset requested for: {email}")
#         else:
#             # Log attempt but don't reveal if user exists
#             self._logger.warning(f"Password reset requested for unknown email: {email}")
        
#         # Always return success for security
#         return {
#             "message": "If the email exists in our system, you will receive a password reset link"
#         }
    
#     async def reset_password(
#         self,
#         token: str,
#         new_password: str,
#         db: AsyncSession
#     ) -> Dict[str, str]:
#         """
#         Reset password using token.
        
#         Args:
#             token: Reset token
#             new_password: New password
#             db: Database session
            
#         Returns:
#             Success message
            
#         Raises:
#             InvalidToken: If token is invalid
#         """
#         try:
#             # Verify token
#             payload = await token_manager.verify_token(
#                 token,
#                 expected_type=TokenType.RESET_PASSWORD
#             )
            
#             email = payload["sub"]
#             user = await self.user_repository.get_by_email(email, db)
            
#             if not user:
#                 raise InvalidToken("Invalid reset token")
            
#             # Hash new password
#             hashed_password = hash_password(new_password)
            
#             # Update password
#             await self.user_repository.update_password(
#                 user.id,
#                 hashed_password,
#                 db
#             )
            
#             # Revoke all user tokens for security
#             await token_manager.revoke_all_user_tokens(
#                 str(user.id),
#                 "password_reset"
#             )
            
#             # Revoke the reset token
#             await token_manager.revoke_token(token, "used")
            
#             self._logger.info(
#                 f"Password reset completed",
#                 extra={"user_id": user.id, "email": email}
#             )
            
#             return {"message": "Password has been reset successfully"}
            
#         except Exception as e:
#             self._logger.error(f"Password reset failed: {e}")
#             raise InvalidToken(detail="Invalid or expired reset token")
    
#     async def verify_email(
#         self,
#         token: str,
#         db: AsyncSession
#     ) -> Dict[str, str]:
#         """
#         Verify user email address.
        
#         Args:
#             token: Verification token
#             db: Database session
            
#         Returns:
#             Success message
            
#         Raises:
#             InvalidToken: If token is invalid
#         """
#         try:
#             # Verify token
#             payload = await token_manager.verify_token(
#                 token,
#                 expected_type=TokenType.EMAIL_VERIFICATION
#             )
            
#             email = payload["sub"]
#             user = await self.user_repository.get_by_email(email, db)
            
#             if not user:
#                 raise InvalidToken("Invalid verification token")
            
#             if user.is_verified:
#                 return {"message": "Email is already verified"}
            
#             # Verify email
#             await self.user_repository.verify_email(user.id, db)
            
#             # Revoke the verification token
#             await token_manager.revoke_token(token, "used")
            
#             self._logger.info(
#                 f"Email verified",
#                 extra={"user_id": user.id, "email": email}
#             )
            
#             return {"message": "Email has been verified successfully"}
            
#         except Exception as e:
#             self._logger.error(f"Email verification failed: {e}")
#             raise InvalidToken(detail="Invalid or expired verification token")
    
#     async def resend_verification_email(
#         self,
#         user: User,
#         background_tasks: Optional[BackgroundTasks] = None
#     ) -> Dict[str, str]:
#         """
#         Resend verification email.
        
#         Args:
#             user: User object
#             background_tasks: Background tasks
            
#         Returns:
#             Success message
            
#         Raises:
#             ValidationError: If already verified
#         """
#         if user.is_verified:
#             raise ValidationError(
#                 detail="Email is already verified",
#                 field="email"
#             )
        
#         # Check rate limiting
#         rate_limit_key = f"verification_resend:{user.id}"
#         attempts = await redis_client.get(rate_limit_key)
        
#         if attempts and int(attempts) >= 3:
#             raise ValidationError(
#                 detail="Too many verification emails requested. Please try again later.",
#                 field="email"
#             )
        
#         # Send new verification email
#         await self._send_verification_email(user, background_tasks)
        
#         # Update rate limit
#         await redis_client.incr(rate_limit_key)
#         await redis_client.expire(rate_limit_key, 3600)  # 1 hour
        
#         return {"message": "Verification email has been resent"}
    
#     # Private helper methods
    
#     def _get_user_permissions(self, user: User) -> List[str]:
#         """Get user permissions based on role."""
#         permissions_map = {
#             UserRole.USER: [
#                 "read:own_profile",
#                 "update:own_profile",
#                 "create:book",
#                 "update:own_book",
#                 "delete:own_book",
#                 "create:review",
#                 "update:own_review",
#                 "delete:own_review"
#             ],
#             UserRole.MODERATOR: [
#                 "read:own_profile",
#                 "update:own_profile",
#                 "create:book",
#                 "update:own_book",
#                 "update:any_book",
#                 "delete:own_book",
#                 "delete:any_book",
#                 "create:review",
#                 "update:own_review",
#                 "delete:own_review",
#                 "delete:any_review",
#                 "moderate:content"
#             ],
#             UserRole.ADMIN: [
#                 "all:permissions"
#             ]
#         }
        
#         return permissions_map.get(user.role, [])
    
#     async def _send_verification_email(
#         self,
#         user: User,
#         background_tasks: Optional[BackgroundTasks] = None
#     ) -> None:
#         """Send verification email."""
#         token = token_manager.create_token(
#             subject=user.email,
#             token_type=TokenType.EMAIL_VERIFICATION,
#             expires_delta=timedelta(hours=24),
#             additional_claims={"user_id": str(user.id)}
#         )
        
#         verification_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        
#         if USE_CELERY:
#             send_verification_email_task.delay(
#                 email_to=user.email,
#                 token=token
#             )
#         else:
#             email_data = {
#                 "to_email": user.email,
#                 "subject": "Verify your email address",
#                 "template": "email_verification",
#                 "context": {
#                     "user_name": user.full_name,
#                     "verification_link": verification_link
#                 }
#             }
            
#             if background_tasks:
#                 background_tasks.add_task(send_email, **email_data)
#             else:
#                 await send_email(**email_data)
    
#     async def _send_password_reset_email(
#         self,
#         user: User,
#         reset_token: str,
#         background_tasks: Optional[BackgroundTasks] = None
#     ) -> None:
#         """Send password reset email."""
#         reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        
#         if USE_CELERY:
#             send_password_reset_email_task.delay(
#                 email_to=user.email,
#                 token=reset_token
#             )
#         else:
#             email_data = {
#                 "to_email": user.email,
#                 "subject": "Reset your password",
#                 "template": "password_reset",
#                 "context": {
#                     "user_name": user.full_name,
#                     "reset_link": reset_link,
#                     "valid_hours": 1
#                 }
#             }
            
#             if background_tasks:
#                 background_tasks.add_task(send_email, **email_data)
#             else:
#                 await send_email(**email_data)
    
#     async def _send_welcome_email(
#         self,
#         user: User,
#         background_tasks: Optional[BackgroundTasks] = None
#     ) -> None:
#         """Send welcome email."""
#         if USE_CELERY:
#             send_welcome_email_task.delay(email_to=user.email)
#         else:
#             email_data = {
#                 "to_email": user.email,
#                 "subject": f"Welcome to {settings.APP_NAME}!",
#                 "template": "welcome",
#                 "context": {
#                     "user_name": user.full_name,
#                     "app_name": settings.APP_NAME,
#                     "support_email": settings.SUPPORT_EMAIL
#                 }
#             }
            
#             if background_tasks:
#                 background_tasks.add_task(send_email, **email_data)
#             else:
#                 await send_email(**email_data)


# # Create singleton instance
# auth_service = AuthService()


# # Legacy functions for backward compatibility
# async def login_user(
#     db: AsyncSession,
#     form_data: OAuth2PasswordRequestForm
# ) -> Dict[str, str]:
#     """Legacy login function."""
#     response = await auth_service.login(form_data, db)
#     return response.model_dump()


# async def login_admin(
#     db: AsyncSession,
#     form_data: OAuth2PasswordRequestForm
# ) -> Dict[str, str]:
#     """Legacy admin login function."""
#     response = await auth_service.login_admin(form_data, db)
#     return response.model_dump()


# async def create_user_and_send_verification(
#     db: AsyncSession,
#     user_data: UserCreate
# ) -> User:
#     """Legacy registration function."""
#     from app.schemas.auth_schema import UserRegister
    
#     register_data = UserRegister(
#         email=user_data.email,
#         username=user_data.username,
#         password=user_data.password,
#         full_name=user_data.full_name
#     )
    
#     return await auth_service.register(register_data, db)


# async def logout_user(token: str) -> None:
#     """Legacy logout function."""
#     await auth_service.logout(token)


# async def refresh_access_token(
#     refresh_token: str,
#     db: AsyncSession
# ) -> Dict[str, str]:
#     """Legacy token refresh function."""
#     response = await auth_service.refresh_tokens(refresh_token, db)
#     return response.model_dump()


# async def request_verification_email(
#     db: AsyncSession,
#     user: User
# ) -> None:
#     """Legacy resend verification function."""
#     await auth_service.resend_verification_email(user)


# async def verify_user_account(
#     db: AsyncSession,
#     token: str
# ) -> User:
#     """Legacy email verification function."""
#     await auth_service.verify_email(token, db)
#     user = await db.execute(
#         select(User).where(User.email == payload["sub"])
#     )
#     return user.scalar_one()


# async def request_password_reset(
#     db: AsyncSession,
#     email_address: str
# ) -> None:
#     """Legacy password reset request function."""
#     await auth_service.request_password_reset(email_address, db)


# async def reset_password_with_token(
#     db: AsyncSession,
#     token: str,
#     new_password: str
# ) -> None:
#     """Legacy password reset function."""
#     await auth_service.reset_password(token, new_password, db)