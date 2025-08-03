# app/services/rate_limit_service.py
import logging
from typing import Dict, List
from datetime import datetime, timedelta
from collections import defaultdict

from app.db.redis_conn import redis_client

logger = logging.getLogger(__name__)


class RateLimitService:
    """Handles rate limiting business logic."""

    def __init__(self):
        self.memory_store: Dict[str, List[datetime]] = defaultdict(list)
        self.use_redis = redis_client is not None

    async def is_rate_limited(
        self, identifier: str, max_requests: int, window_seconds: int
    ) -> bool:
        """Check if identifier is rate limited."""
        if self.use_redis:
            return await self._check_redis_rate_limit(
                identifier, max_requests, window_seconds
            )
        else:
            return self._check_memory_rate_limit(
                identifier, max_requests, window_seconds
            )

    async def _check_redis_rate_limit(
        self, identifier: str, max_requests: int, window_seconds: int
    ) -> bool:
        """Redis-based rate limiting."""
        try:
            key = f"rate_limit:{identifier}:{window_seconds}"
            current = await redis_client.incr(key)
            if current == 1:
                await redis_client.expire(key, window_seconds)
            return current > max_requests
        except Exception:
            logger.error("Redis rate limit check failed.", exc_info=True)
            return False  # Fail open

    def _check_memory_rate_limit(
        self, identifier: str, max_requests: int, window_seconds: int
    ) -> bool:
        """Memory-based rate limiting."""
        now = datetime.now()
        # Clean old entries
        self.memory_store[identifier] = [
            call
            for call in self.memory_store[identifier]
            if now - call < timedelta(seconds=window_seconds)
        ]
        # Check limit
        if len(self.memory_store[identifier]) >= max_requests:
            return True
        # Record this request
        self.memory_store[identifier].append(now)
        return False

    async def is_auth_rate_limited(
        self, identifier: str, max_attempts: int = 5
    ) -> bool:
        """Check authentication rate limiting."""
        try:
            key = f"failed_auth:{identifier}"
            current_attempts = await redis_client.get(key)
            return current_attempts and int(current_attempts) >= max_attempts
        except Exception:
            return False

    async def record_failed_auth_attempt(
        self, identifier: str, lockout_duration: int = 300
    ):
        """Record failed authentication attempt."""
        try:
            key = f"failed_auth:{identifier}"
            await redis_client.incr(key)
            await redis_client.expire(key, lockout_duration)
        except Exception:
            logger.error("Failed to record auth attempt.", exc_info=True)

    async def clear_failed_auth_attempts(self, identifier: str):
        """Clear failed auth attempts on successful login."""
        try:
            key = f"failed_auth:{identifier}"
            await redis_client.delete(key)
        except Exception:
            logger.error("Failed to clear auth attempts.", exc_info=True)


# Singleton instance
rate_limit_service = RateLimitService()
