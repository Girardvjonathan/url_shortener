from unittest.mock import AsyncMock

import pytest
import redis.asyncio as redis_lib

from app.cache import CACHE_TTL, cache_url, get_cached_url, invalidate_url


@pytest.fixture
def r():
    return AsyncMock()


class TestGetCachedUrl:
    async def test_hit_returns_url(self, r):
        r.get.return_value = "https://example.com"
        result = await get_cached_url(r, "abc")
        assert result == "https://example.com"
        r.get.assert_called_once_with("url:abc")

    async def test_miss_returns_none(self, r):
        r.get.return_value = None
        result = await get_cached_url(r, "xyz")
        assert result is None

    async def test_redis_error_returns_none_gracefully(self, r):
        r.get.side_effect = redis_lib.RedisError("connection refused")
        result = await get_cached_url(r, "abc")
        assert result is None


class TestCacheUrl:
    async def test_setex_called_with_correct_key_and_ttl(self, r):
        await cache_url(r, "abc", "https://example.com")
        r.setex.assert_called_once_with("url:abc", CACHE_TTL, "https://example.com")

    async def test_redis_error_is_silenced(self, r):
        r.setex.side_effect = redis_lib.RedisError("connection refused")
        await cache_url(r, "abc", "https://example.com")  # must not raise


class TestInvalidateUrl:
    async def test_delete_called_with_correct_key(self, r):
        await invalidate_url(r, "abc")
        r.delete.assert_called_once_with("url:abc")

    async def test_redis_error_is_silenced(self, r):
        r.delete.side_effect = redis_lib.RedisError("connection refused")
        await invalidate_url(r, "abc")  # must not raise
