# # In app/services/cache_service.py

# import logging
# from typing import Optional

# from app.db.redis_conn import redis_client
# from app.models.user_model import User

# logger = logging.getLogger(__name__)


# class CacheService:
#     """Handles caching business logic."""

#     USER_CACHE_TTL = 300  # 5 minutes
#     USER_CACHE_PREFIX = "user:"

#     async def get_user(self, user_id: int) -> Optional[User]:
#         """Get user from cache."""
#         try:
#             key = f"{self.USER_CACHE_PREFIX}{user_id}"
#             cached_data = await redis_client.get(key)
#             if cached_data:
#                 return User.model_validate_json(cached_data.decode("utf-8"))
#             return None
#         except Exception as e:
#             logger.warning(
#                 f"Cache lookup failed for user {user_id}: {e}", exc_info=True
#             )
#             return None

#     async def cache_user(self, user: User):
#         """Cache user data."""
#         try:
#             key = f"{self.USER_CACHE_PREFIX}{user.id}"
#             # model_dump_json is the correct way to serialize for caching
#             await redis_client.set(key, user.model_dump_json(), ex=self.USER_CACHE_TTL)
#         except Exception:
#             logger.warning(f"Failed to cache user {user.id}.", exc_info=True)

#     async def invalidate_user(self, user_id: int):
#         """Invalidate user cache."""
#         try:
#             key = f"{self.USER_CACHE_PREFIX}{user_id}"
#             await redis_client.delete(key)
#         except Exception:
#             logger.warning(
#                 f"Failed to invalidate cache for user {user_id}.", exc_info=True
#             )


# # Singleton instance
# cache_service = CacheService()

import json
import logging
from typing import Optional, Type, TypeVar, Any
from sqlmodel import SQLModel

from app.db.redis_conn import redis_client

logger = logging.getLogger(__name__)

# Create a TypeVar that is bound to our SQLModel base class.
# This means 'T' can be User, Book, Review, etc.
ModelType = TypeVar("ModelType", bound=SQLModel)


class CacheService:
    """
    A generic, reusable service for caching SQLModel objects in Redis.
    """

    CACHE_TTL = 300  # Default cache time: 5 minutes

    def _get_key(self, model_type: Type[ModelType], obj_id: Any) -> str:
        """Generates a consistent cache key for a given model and ID."""
        return f"{model_type.__name__.lower()}:{obj_id}"

    async def get(
        self, model_type: Type[ModelType], obj_id: Any
    ) -> Optional[ModelType]:
        """
        Retrieves an object from the cache by its model type and ID.
        """
        key = self._get_key(model_type, obj_id)
        try:
            cached_data = await redis_client.get(key)
            if cached_data:
                # Use Pydantic's robust JSON parsing to correctly handle types
                return model_type.model_validate_json(cached_data)
            return None
        except Exception:
            logger.warning(f"Cache lookup failed for key: {key}", exc_info=True)
            return None

    async def set(self, obj: ModelType):
        """
        Caches a SQLModel object.
        """
        key = self._get_key(type(obj), obj.id)
        try:
            # Use model_dump_json to correctly serialize complex types like datetimes
            await redis_client.set(key, obj.model_dump_json(), ex=self.CACHE_TTL)
        except Exception:
            logger.warning(f"Failed to cache object with key: {key}", exc_info=True)

    async def invalidate(self, model_type: Type[ModelType], obj_id: Any):
        """
        Invalidates the cache for a specific object.
        """
        key = self._get_key(model_type, obj_id)
        try:
            await redis_client.delete(key)
        except Exception:
            logger.warning(f"Failed to invalidate cache for key: {key}", exc_info=True)


# Create a single, reusable instance for the rest of the application
cache_service = CacheService()
