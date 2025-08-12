import uuid
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from enum import Enum

from passlib.context import CryptContext
from jose import jwt, JWTError

from app.core.config import settings
from app.core.exceptions import (
    InternalServerError,
    TokenExpired,
    TokenRevoked,
    TokenTypeInvalid,
    InvalidToken,
)
from app.db.redis_conn import redis_client

# --- Setup ---
logger = logging.getLogger(__name__)


# --- Enums & Config ---
class TokenType(str, Enum):
    """Defines the types of tokens the system can issue."""

    ACCESS = "access"
    REFRESH = "refresh"
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"
    EMAIL_CHANGE = "email_change"


class SecurityConfig:
    """Validates and holds all security-related configurations."""

    JWT_SECRET_KEY: str = settings.JWT_SECRET
    JWT_ALGORITHM: str = getattr(settings, "JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = getattr(
        settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 15
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7)
    TOKEN_ISSUER: str = getattr(settings, "TOKEN_ISSUER", "my-app")
    TOKEN_AUDIENCE: str = getattr(settings, "TOKEN_AUDIENCE", "my-app:users")
    ENABLE_TOKEN_BLACKLIST: bool = getattr(settings, "ENABLE_TOKEN_BLACKLIST", True)
    REDIS_FAIL_SECURE: bool = getattr(settings, "REDIS_FAIL_SECURE", True)

    @classmethod
    def validate(cls):
        if not cls.JWT_SECRET_KEY or len(cls.JWT_SECRET_KEY) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be configured and be at least 32 characters long."
            )


SecurityConfig.validate()


# --- Password Management ---
class PasswordManager:
    """Encapsulates all password hashing and verification logic."""

    pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

    @classmethod
    def hash_password(cls, password: str) -> str:
        """Hashes a plain-text password."""
        try:
            return cls.pwd_context.hash(password)
        except Exception:
            logger.critical("Password hashing failed.", exc_info=True)
            raise InternalServerError(detail="Could not process password.")

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        """Verifies a plain-text password against a hash."""
        try:
            return cls.pwd_context.verify(plain_password, hashed_password)
        except Exception:
            logger.warning(
                "Password verification failed due to a malformed hash or other error."
            )
            return False

    @classmethod
    def needs_rehash(cls, hashed_password: str) -> bool:
        """Checks if a hash needs to be updated to the latest parameters."""
        return cls.pwd_context.needs_update(hashed_password)


# --- Token Management (Infrastructure Only) ---
class TokenManager:
    """Low-level token operations - creation, verification, blacklisting."""

    config = SecurityConfig

    def create_token(
        self,
        subject: str,
        token_type: TokenType,
        expires_delta: Optional[timedelta] = None,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Creates a JWT with specified type and claims."""
        now = datetime.now(timezone.utc)

        if not expires_delta:
            if token_type == TokenType.ACCESS:
                expires_delta = timedelta(
                    minutes=self.config.ACCESS_TOKEN_EXPIRE_MINUTES
                )
            elif token_type == TokenType.REFRESH:
                expires_delta = timedelta(days=self.config.REFRESH_TOKEN_EXPIRE_DAYS)
            else:
                expires_delta = timedelta(hours=1)

        expire = now + expires_delta

        claims = {
            "sub": str(subject),
            "exp": expire,
            "iat": now,
            "nbf": now,
            "iss": self.config.TOKEN_ISSUER,
            "aud": self.config.TOKEN_AUDIENCE,
            "jti": str(uuid.uuid4()),
            "type": token_type.value,
        }
        if additional_claims:
            claims.update(additional_claims)

        return jwt.encode(
            claims, self.config.JWT_SECRET_KEY, algorithm=self.config.JWT_ALGORITHM
        )

    async def verify_token(
        self, token: str, expected_type: TokenType
    ) -> Dict[str, Any]:
        """Verifies and decodes a JWT."""
        if not token:
            raise InvalidToken("Token cannot be empty.")

        try:
            payload = jwt.decode(
                token,
                self.config.JWT_SECRET_KEY,
                algorithms=[self.config.JWT_ALGORITHM],
                audience=self.config.TOKEN_AUDIENCE,
                issuer=self.config.TOKEN_ISSUER,
            )

            token_type = payload.get("type")
            if token_type != expected_type.value:
                raise TokenTypeInvalid(
                    f"Expected '{expected_type.value}' token, but got '{token_type}'.",
                    expected=expected_type.value,
                    received=token_type,
                )

            if self.config.ENABLE_TOKEN_BLACKLIST:
                jti = payload.get("jti")
                if not jti:
                    raise InvalidToken("Token is missing the required 'jti' claim.")
                if await self.is_token_revoked(jti):
                    raise TokenRevoked()

            return payload

        except jwt.ExpiredSignatureError:
            raise TokenExpired() from None
        except JWTError as e:
            raise InvalidToken(f"Token is invalid: {e}") from e

    # --- Low-level blacklist operations ---
    async def revoke_token(self, token: str, reason: str = "Revoked") -> bool:
        """Revokes a token by extracting its JTI and calculating TTL."""
        if not self.config.ENABLE_TOKEN_BLACKLIST:
            return False
        try:
            payload = jwt.decode(
                token,
                self.config.JWT_SECRET_KEY,
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_aud": False,
                },
            )
            jti = payload.get("jti")
            exp = payload.get("exp")
            if not jti or not exp:
                return False

            remaining_time = exp - int(datetime.now(timezone.utc).timestamp())
            if remaining_time <= 0:
                return True  # Already expired

            key = f"revoked_token:{jti}"
            await redis_client.set(key, reason, ex=remaining_time)
            logger.info(f"Token revoked: {jti}")
            return True
        except Exception:
            logger.error("Failed to revoke token.", exc_info=True)
            return False

    async def is_token_revoked(self, jti: str) -> bool:
        """Checks if a token's JTI is blacklisted."""
        if not self.config.ENABLE_TOKEN_BLACKLIST:
            return False
        try:
            key = f"revoked_token:{jti}"
            return await redis_client.exists(key) > 0
        except Exception:
            logger.error(
                "Failed to check token revocation status in Redis.", exc_info=True
            )
            if self.config.REDIS_FAIL_SECURE:
                raise InternalServerError("Token validation service unavailable")
            return False

    def decode_token_unsafe(self, token: str) -> Optional[Dict[str, Any]]:
        """Decode token without verification - for utility purposes only."""
        try:
            return jwt.decode(
                token,
                self.config.JWT_SECRET_KEY,
                options={"verify_signature": False, "verify_exp": False},
            )
        except Exception:
            return None


# --- Security Utilities ---
def generate_secure_token(length: int = 32) -> str:
    """Generates a cryptographically secure, URL-safe random token."""
    return secrets.token_urlsafe(length)


def constant_time_compare(val1: str, val2: str) -> bool:
    """Compares two strings in constant time to prevent timing attacks."""
    return secrets.compare_digest(val1, val2)


# --- Singleton Instances ---
password_manager = PasswordManager()
token_manager = TokenManager()


class SecurityHeaders:
    """Centralized definition of security headers for API responses."""

    @staticmethod
    def get_headers() -> Dict[str, str]:
        """Returns a dictionary of recommended security headers."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        }
