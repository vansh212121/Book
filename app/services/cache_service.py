import json
import logging
from typing import Optional, Type, TypeVar, Any
from sqlmodel import SQLModel
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
                if any(t in str(field_type) for t in ["datetime", "date"]):
                    try:
                        # Use isoparse to correctly handle timezone-aware strings
                        data[field_name] = isoparse(data[field_name])
                    except (ValueError, TypeError):
                        logger.warning(
                            f"Could not parse date string '{data[field_name]}' for field '{field_name}'."
                        )
                        pass  # Let Pydantic handle the final validation
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
        if not hasattr(obj, "id") or obj.id is None:
            logger.warning(
                f"Attempted to cache an object of type {type(obj).__name__} without an ID."
            )
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
