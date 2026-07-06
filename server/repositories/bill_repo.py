import json
from datetime import datetime
from typing import Any

from repositories.base import BaseRepository


class BillTransactionRepository(BaseRepository):
    async def delete_all(self) -> str:
        return await self.execute("DELETE FROM bill_transactions")

    async def upsert(self, doc: dict) -> None:
        await self.execute(
            """INSERT INTO bill_transactions (
                   order_id, phone, org_id, org_name, bill_id, bill_no,
                   amount, amount_paid, balance, billing_mode, status,
                   payment_status, date, notes, customer_id, address,
                   raw_transaction, fetched_at
               ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17::jsonb, $18)
               ON CONFLICT (order_id) DO UPDATE SET
                   phone = EXCLUDED.phone, org_id = EXCLUDED.org_id,
                   org_name = EXCLUDED.org_name, bill_id = EXCLUDED.bill_id,
                   bill_no = EXCLUDED.bill_no, amount = EXCLUDED.amount,
                   amount_paid = EXCLUDED.amount_paid, balance = EXCLUDED.balance,
                   billing_mode = EXCLUDED.billing_mode, status = EXCLUDED.status,
                   payment_status = EXCLUDED.payment_status, date = EXCLUDED.date,
                   notes = EXCLUDED.notes, customer_id = EXCLUDED.customer_id,
                   address = EXCLUDED.address, raw_transaction = EXCLUDED.raw_transaction,
                   fetched_at = EXCLUDED.fetched_at""",
            doc["order_id"],
            doc["phone"],
            doc.get("org_id", ""),
            doc.get("org_name", ""),
            doc.get("bill_id"),
            doc.get("bill_no"),
            doc.get("amount", 0),
            doc.get("amount_paid", 0),
            doc.get("balance", 0),
            doc.get("billing_mode", ""),
            doc.get("status", ""),
            doc.get("payment_status", ""),
            doc.get("date", ""),
            doc.get("notes", ""),
            doc.get("customer_id", ""),
            doc.get("address", ""),
            json.dumps(doc.get("raw_transaction", {}), default=str),
            datetime.utcnow(),
        )

    async def get_all(self) -> list[dict]:
        rows = await self.fetch("SELECT * FROM bill_transactions")
        return [dict(r) for r in rows]
