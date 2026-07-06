from repositories.order_repo import RawOrderRepository
from repositories.bill_repo import BillTransactionRepository


class Deduplicator:
    def __init__(self, order_repo: RawOrderRepository = None, bill_repo: BillTransactionRepository = None):
        self._order_repo = order_repo or RawOrderRepository()
        self._bill_repo = bill_repo or BillTransactionRepository()

    async def is_duplicate_order(self, source: str, order_id: str) -> bool:
        if not order_id:
            return False
        if source == "bill":
            return False
        val = await self._order_repo.fetchval(
            "SELECT 1 FROM raw_orders WHERE source = $1 AND order_id = $2 LIMIT 1",
            source, str(order_id),
        )
        return val is not None

    async def is_duplicate_bill_tx(self, order_id: str) -> bool:
        if not order_id:
            return False
        val = await self._bill_repo.fetchval(
            "SELECT 1 FROM bill_transactions WHERE order_id = $1 LIMIT 1",
            order_id,
        )
        return val is not None
