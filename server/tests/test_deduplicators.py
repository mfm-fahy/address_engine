from unittest.mock import AsyncMock, MagicMock

import pytest

from pipeline.deduplicators import Deduplicator


class TestDeduplicator:

    @pytest.mark.asyncio
    async def test_is_duplicate_order_found(self):
        order_repo = MagicMock()
        order_repo.fetchval = AsyncMock(return_value=1)
        dedup = Deduplicator(order_repo=order_repo, bill_repo=MagicMock())
        result = await dedup.is_duplicate_order("gowhats", "ord1")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_duplicate_order_not_found(self):
        order_repo = MagicMock()
        order_repo.fetchval = AsyncMock(return_value=None)
        dedup = Deduplicator(order_repo=order_repo, bill_repo=MagicMock())
        result = await dedup.is_duplicate_order("gowhats", "ord1")
        assert result is False

    @pytest.mark.asyncio
    async def test_bill_source_always_false(self):
        dedup = Deduplicator()
        result = await dedup.is_duplicate_order("bill", "any_id")
        assert result is False

    @pytest.mark.asyncio
    async def test_empty_order_id(self):
        dedup = Deduplicator()
        result = await dedup.is_duplicate_order("gowhats", "")
        assert result is False
        result = await dedup.is_duplicate_order("gowhats", None)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_duplicate_bill_tx_found(self):
        bill_repo = MagicMock()
        bill_repo.fetchval = AsyncMock(return_value=1)
        dedup = Deduplicator(order_repo=MagicMock(), bill_repo=bill_repo)
        result = await dedup.is_duplicate_bill_tx("tx1")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_duplicate_bill_tx_not_found(self):
        bill_repo = MagicMock()
        bill_repo.fetchval = AsyncMock(return_value=None)
        dedup = Deduplicator(order_repo=MagicMock(), bill_repo=bill_repo)
        result = await dedup.is_duplicate_bill_tx("tx1")
        assert result is False

    @pytest.mark.asyncio
    async def test_empty_bill_tx_id(self):
        dedup = Deduplicator()
        result = await dedup.is_duplicate_bill_tx("")
        assert result is False
