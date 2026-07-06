from typing import Any, Optional
import asyncpg
from config.postgres import get_pool


class BaseRepository:
    def __init__(self, pool: Optional[asyncpg.Pool] = None):
        self._pool = pool

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = get_pool()
        return self._pool

    async def execute(self, query: str, *args: Any) -> str:
        p = await self._get_pool()
        async with p.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        p = await self._get_pool()
        async with p.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Optional[asyncpg.Record]:
        p = await self._get_pool()
        async with p.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        p = await self._get_pool()
        async with p.acquire() as conn:
            return await conn.fetchval(query, *args)
