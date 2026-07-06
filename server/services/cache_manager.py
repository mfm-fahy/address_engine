import asyncio
import json
import time
from typing import Any, Callable, Optional

from config.redis import redis_client


class CacheManager:
    def __init__(self):
        self._hits = 0
        self._misses = 0
        self._latency_total = 0.0

    @property
    def hit_ratio(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    async def get_or_compute(
        self,
        key: str,
        ttl: int,
        compute_fn: Callable[[], Any],
    ) -> Any:
        t0 = time.monotonic()
        cached = await redis_client.get(key)
        if cached is not None:
            self._hits += 1
            self._latency_total += time.monotonic() - t0
            return json.loads(cached)

        self._misses += 1
        value = compute_fn()
        if asyncio.iscoroutine(value):
            value = await value
        try:
            serialized = json.dumps(value, default=str, ensure_ascii=False)
            await redis_client.set(key, serialized, ex=ttl)
        except (TypeError, ValueError):
            pass
        self._latency_total += time.monotonic() - t0
        return value

    async def invalidate(self, key: str) -> None:
        await redis_client.delete(key)

    async def invalidate_prefix(self, prefix: str) -> None:
        await redis_client.scan_delete(f"{prefix}*")

    async def get_metrics(self) -> dict:
        total = self._hits + self._misses
        dbsize = await redis_client.dbsize()
        return {
            "redis_available": redis_client.available,
            "cache_keys": dbsize,
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio": round(self.hit_ratio, 4),
            "total_requests": total,
            "avg_latency_ms": round((self._latency_total / total * 1000) if total > 0 else 0, 2),
        }


cache_manager = CacheManager()
