import logging

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Cache TTL in seconds (24 hours)
CACHE_TTL = 86400


async def create_redis(redis_url: str) -> redis.Redis:
    """Create and return an async Redis client."""
    return redis.from_url(redis_url, decode_responses=True)


async def get_cached_url(r: redis.Redis, short_code: str) -> str | None:
    """Look up a short code in the Redis cache.

    Returns the full URL if found, None otherwise.
    Gracefully returns None if Redis is unavailable.
    """
    try:
        return await r.get(f"url:{short_code}")
    except redis.RedisError as e:
        logger.warning("Redis GET failed for %s: %s", short_code, e)
        return None


async def cache_url(r: redis.Redis, short_code: str, full_url: str) -> None:
    """Cache a short_code -> full_url mapping with a 24h TTL.

    Silently fails if Redis is unavailable.
    """
    try:
        await r.setex(f"url:{short_code}", CACHE_TTL, full_url)
    except redis.RedisError as e:
        logger.warning("Redis SETEX failed for %s: %s", short_code, e)


async def invalidate_url(r: redis.Redis, short_code: str) -> None:
    """Remove a short code from the cache (for future use).

    Silently fails if Redis is unavailable.
    """
    try:
        await r.delete(f"url:{short_code}")
    except redis.RedisError as e:
        logger.warning("Redis DELETE failed for %s: %s", short_code, e)
