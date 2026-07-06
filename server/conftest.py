from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_redis():
    with patch("config.redis.redis_client") as mock:
        mock.available = True
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock()
        mock.delete = AsyncMock()
        mock.dbsize = AsyncMock(return_value=0)
        yield mock


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    pool.acquire = AsyncMock()
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=0)
    conn.close = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    with patch("config.postgres.get_pool", return_value=pool):
        yield pool, conn


@pytest.fixture
def app() -> FastAPI:
    from main import app
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _setup_test_env():
    import os
    os.environ.setdefault("AUTH_ENABLED", "false")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
    yield
