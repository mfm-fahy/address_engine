import json
from unittest.mock import AsyncMock, patch

import pytest

from services.cache_manager import CacheManager


@pytest.fixture
def cache():
    return CacheManager()


class TestCacheManager:

    def test_hit_ratio_zero_initially(self, cache):
        assert cache.hit_ratio == 0.0

    @pytest.mark.asyncio
    async def test_miss_computes_and_caches(self, cache):
        with patch("services.cache_manager.redis_client") as mock_redis:
            mock_redis.available = True
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.set = AsyncMock()

            result = await cache.get_or_compute("key1", 60, lambda: {"value": 42})

            assert result == {"value": 42}
            mock_redis.set.assert_awaited_once()
            assert cache._misses == 1
            assert cache._hits == 0

    @pytest.mark.asyncio
    async def test_hit_returns_cached(self, cache):
        with patch("services.cache_manager.redis_client") as mock_redis:
            mock_redis.available = True
            mock_redis.get = AsyncMock(return_value=json.dumps({"value": 99}))
            mock_redis.set = AsyncMock()

            result = await cache.get_or_compute("key2", 60, lambda: {"value": 0})

            assert result == {"value": 99}
            mock_redis.set.assert_not_called()
            assert cache._misses == 0
            assert cache._hits == 1

    @pytest.mark.asyncio
    async def test_hit_ratio(self, cache):
        with patch("services.cache_manager.redis_client") as mock_redis:
            mock_redis.available = True
            mock_redis.get = AsyncMock(side_effect=[None, json.dumps("ok"), json.dumps("ok2")])
            mock_redis.set = AsyncMock()

            await cache.get_or_compute("a", 60, lambda: "first")
            await cache.get_or_compute("b", 60, lambda: "second")
            await cache.get_or_compute("c", 60, lambda: "third")

            assert cache._hits == 2
            assert cache._misses == 1
            assert cache.hit_ratio == 2 / 3

    @pytest.mark.asyncio
    async def test_async_compute_fn(self, cache):
        with patch("services.cache_manager.redis_client") as mock_redis:
            mock_redis.available = True
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.set = AsyncMock()

            async def compute():
                return {"async": True}

            result = await cache.get_or_compute("async_key", 60, compute)
            assert result == {"async": True}

    @pytest.mark.asyncio
    async def test_invalidate(self, cache):
        with patch("services.cache_manager.redis_client") as mock_redis:
            mock_redis.available = True
            mock_redis.delete = AsyncMock()

            await cache.invalidate("some_key")
            mock_redis.delete.assert_awaited_once_with("some_key")

    @pytest.mark.asyncio
    async def test_invalidate_prefix(self, cache):
        with patch("services.cache_manager.redis_client") as mock_redis:
            mock_redis.available = True
            mock_redis.scan_delete = AsyncMock()

            await cache.invalidate_prefix("prefix:")
            mock_redis.scan_delete.assert_awaited_once_with("prefix:*")

    @pytest.mark.asyncio
    async def test_get_metrics(self, cache):
        with patch("services.cache_manager.redis_client") as mock_redis:
            mock_redis.available = True
            mock_redis.dbsize = AsyncMock(return_value=5)

            metrics = await cache.get_metrics()
            assert metrics["redis_available"] is True
            assert metrics["cache_keys"] == 5
            assert metrics["hits"] == 0
            assert metrics["misses"] == 0
            assert metrics["total_requests"] == 0
