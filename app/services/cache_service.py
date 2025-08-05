# In app/services/cache_service.py

import logging
from typing import Optional

from app.db.redis_conn import redis_client
from app.models.user_model import User

logger = logging.getLogger(__name__)


class CacheService:
    """Handles caching business logic."""

    USER_CACHE_TTL = 300  # 5 minutes
    USER_CACHE_PREFIX = "user:"

    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user from cache."""
        try:
            key = f"{self.USER_CACHE_PREFIX}{user_id}"
            cached_data = await redis_client.get(key)
            if cached_data:
                return User.model_validate_json(cached_data.decode("utf-8"))
            return None
        except Exception as e:
            logger.warning(
                f"Cache lookup failed for user {user_id}: {e}", exc_info=True
            )
            return None

    async def cache_user(self, user: User):
        """Cache user data."""
        try:
            key = f"{self.USER_CACHE_PREFIX}{user.id}"
            # model_dump_json is the correct way to serialize for caching
            await redis_client.set(key, user.model_dump_json(), ex=self.USER_CACHE_TTL)
        except Exception:
            logger.warning(f"Failed to cache user {user.id}.", exc_info=True)

    async def invalidate_user(self, user_id: int):
        """Invalidate user cache."""
        try:
            key = f"{self.USER_CACHE_PREFIX}{user_id}"
            await redis_client.delete(key)
        except Exception:
            logger.warning(
                f"Failed to invalidate cache for user {user_id}.", exc_info=True
            )


# Singleton instance
cache_service = CacheService()
