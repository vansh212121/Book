# app/core/cache.py
"""
Cache utilities for the application.
"""

import json
import functools
from typing import Any, Callable, Optional
from redis import asyncio as aioredis

from app.core.config import settings

# Initialize Redis client
redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> aioredis.Redis:
    """Get or create Redis client."""
    global redis_client
    if not redis_client:
        redis_client = await aioredis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )
    return redis_client


def cache_key_wrapper(key_pattern: str, expire: int = 3600) -> Callable:
    """
    Decorator for caching function results.

    Args:
        key_pattern: Cache key pattern (can include {param_name})
        expire: TTL in seconds
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Skip caching if disabled
            if not settings.CACHE_ENABLED:
                return await func(*args, **kwargs)

            # Build cache key
            cache_key = key_pattern.format(**kwargs)

            try:
                # Try to get from cache
                redis = await get_redis_client()
                cached = await redis.get(cache_key)

                if cached:
                    return json.loads(cached)
            except Exception as e:
                # Log error but continue without cache
                pass

            # Get fresh data
            result = await func(*args, **kwargs)

            try:
                # Store in cache
                redis = await get_redis_client()
                await redis.setex(cache_key, expire, json.dumps(result, default=str))
            except Exception:
                # Log error but return result
                pass

            return result

        return wrapper

    return decorator


async def invalidate_cache(pattern: str) -> None:
    """Invalidate cache keys matching pattern."""
    try:
        redis = await get_redis_client()
        keys = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)
    except Exception:
        pass
