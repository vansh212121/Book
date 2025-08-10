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

# import json
# import logging
# from typing import Optional, Type, TypeVar, Any
# from sqlmodel import SQLModel
# from sqlmodel.ext.asyncio.session import AsyncSession
# from dateutil.parser import isoparse

# from app.db.redis_conn import redis_client

# logger = logging.getLogger(__name__)

# # Create a TypeVar that is bound to our SQLModel base class.
# # This means 'T' can be User, Book, Review, etc.
# ModelType = TypeVar("ModelType", bound=SQLModel)


# class CacheService:
#     """
#     A generic, reusable service for caching SQLModel objects in Redis.
#     """

#     CACHE_TTL = 300  # Default cache time: 5 minutes

#     def _get_key(self, model_type: Type[ModelType], obj_id: Any) -> str:
#         """Generates a consistent cache key for a given model and ID."""
#         return f"{model_type.__name__.lower()}:{obj_id}"

#     def _coerce_datetime_fields(self, obj: dict) -> dict:
#         for field in ("created_at", "updated_at"):
#             if field in obj and isinstance(obj[field], str):
#                 try:
#                     obj[field] = isoparse(obj[field])
#                 except Exception:
#                     pass
#         return obj

#     async def get(
#         self, model_type: Type[ModelType], obj_id: Any
#     ) -> Optional[ModelType]:
#         key = self._get_key(model_type, obj_id)
#         try:
#             cached_data = await redis_client.get(key)
#             if cached_data:
#                 raw_dict = json.loads(cached_data)
#                 parsed_dict = self._coerce_datetime_fields(raw_dict)
#                 return model_type(**parsed_dict)
#             return None
#         except Exception:
#             logger.warning(f"Cache lookup failed for key: {key}", exc_info=True)
#             return None

#     async def set(self, obj: ModelType):
#         key = self._get_key(type(obj), obj.id)
#         try:
#             await redis_client.set(key, obj.model_dump_json(), ex=self.CACHE_TTL)
#         except Exception:
#             logger.warning(f"Failed to cache object with key: {key}", exc_info=True)

#     async def invalidate(self, model_type: Type[ModelType], obj_id: Any):
#         key = self._get_key(model_type, obj_id)
#         try:
#             await redis_client.delete(key)
#         except Exception:
#             logger.warning(f"Failed to invalidate cache for key: {key}", exc_info=True)


# cache_service = CacheService()



# In app/services/cache_service.py

import json
import logging
from typing import Optional, Type, TypeVar, Any
from sqlmodel import SQLModel
from datetime import datetime, date
from dateutil.parser import isoparse

from app.db.redis_conn import redis_client

logger = logging.getLogger(__name__)

# Create a TypeVar that is bound to our SQLModel base class.
ModelType = TypeVar("ModelType", bound=SQLModel)

class CacheService:
    """
    A generic, reusable service for caching SQLModel objects in Redis.
    """
    
    CACHE_TTL = 300  # Default cache time: 5 minutes

    def _get_key(self, model_type: Type[ModelType], obj_id: Any) -> str:
        """Generates a consistent cache key for a given model and ID."""
        return f"{model_type.__name__.lower()}:{obj_id}"

    def _coerce_types(self, data: dict, model_type: Type[ModelType]) -> dict:
        """
        A truly generic helper to parse fields back to their correct Python types.
        It introspects the model to find fields that need conversion.
        """
        for field_name, field_info in model_type.model_fields.items():
            # Check if the field is a datetime or date and is a string in the cached data
            if field_name in data and isinstance(data[field_name], str):
                # Get the type annotation (e.g., datetime, Optional[datetime])
                field_type = field_info.annotation
                # Check if the base type is datetime or date
                if any(t in str(field_type) for t in ['datetime', 'date']):
                    try:
                        # Use isoparse to correctly handle timezone-aware strings
                        data[field_name] = isoparse(data[field_name])
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse date string '{data[field_name]}' for field '{field_name}'.")
                        pass # Let Pydantic handle the final validation
        return data

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
                # 1. Load the raw JSON string into a Python dictionary
                raw_dict = json.loads(cached_data)
                # 2. Use our smart helper to convert strings back to datetimes/dates
                parsed_dict = self._coerce_types(raw_dict, model_type)
                # 3. Create the model instance from the corrected dictionary
                return model_type.model_validate(parsed_dict)
            return None
        except Exception:
            logger.warning(f"Cache lookup failed for key: {key}", exc_info=True)
            return None

    async def set(self, obj: ModelType):
        """
        Caches a SQLModel object.
        """
        if not hasattr(obj, 'id') or obj.id is None:
            logger.warning(f"Attempted to cache an object of type {type(obj).__name__} without an ID.")
            return

        key = self._get_key(type(obj), obj.id)
        try:
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