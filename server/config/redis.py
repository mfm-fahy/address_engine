import os
from typing import Optional

import redis.asyncio as aioredis

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")


class RedisClient:
    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._connected = False

    @property
    def available(self) -> bool:
        return self._connected and self._redis is not None

    async def connect(self, url: Optional[str] = None) -> None:
        url = url or _REDIS_URL
        try:
            self._redis = aioredis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
                password=os.getenv("REDIS_PASSWORD") or None,
            )
            await self._redis.ping()
            self._connected = True
            print(f"[redis] Connected to {url}")
        except Exception as e:
            print(f"[redis] Connection failed: {e} (caching disabled)")

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None
            self._connected = False
            print("[redis] Connection closed")

    async def get(self, key: str) -> Optional[str]:
        if not self.available:
            return None
        try:
            return await self._redis.get(key)
        except Exception:
            return None

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        if not self.available:
            return
        try:
            await self._redis.set(key, value, ex=ex)
        except Exception:
            pass

    async def delete(self, key: str) -> None:
        if not self.available:
            return
        try:
            await self._redis.delete(key)
        except Exception:
            pass

    async def scan_delete(self, pattern: str) -> None:
        if not self.available:
            return
        try:
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            pass

    async def dbsize(self) -> int:
        if not self.available:
            return 0
        try:
            return await self._redis.dbsize()
        except Exception:
            return 0


redis_client = RedisClient()
