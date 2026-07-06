import json
from datetime import datetime
from typing import Any, Optional

from repositories.base import BaseRepository


class RawOrderRepository(BaseRepository):
    async def count_all(self) -> int:
        return await self.fetchval("SELECT COUNT(*) FROM raw_orders")

    async def delete_by_source(self, source: str) -> str:
        return await self.execute(
            "DELETE FROM raw_orders WHERE source = $1", source
        )

    async def upsert_bill_customer(self, doc: dict) -> None:
        await self.execute(
            """INSERT INTO raw_orders (source, order_id, raw_data, phone, customer_name, customer_id, address, customer_total_spent, fetched_at)
               VALUES ($1, $2, $3::jsonb, $4, $5, $6, $7, $8, $9)
               ON CONFLICT (source, order_id) DO UPDATE SET
                   raw_data = EXCLUDED.raw_data,
                   phone = EXCLUDED.phone,
                   customer_name = EXCLUDED.customer_name,
                   customer_id = EXCLUDED.customer_id,
                   address = EXCLUDED.address,
                   customer_total_spent = EXCLUDED.customer_total_spent,
                   fetched_at = EXCLUDED.fetched_at""",
            "bill",
            doc["order_id"],
            json.dumps(doc["raw_data"], default=str),
            doc["phone"],
            doc["customer_name"],
            doc.get("customer_id", ""),
            doc.get("address", ""),
            doc.get("customer_total_spent", 0),
            datetime.utcnow(),
        )

    async def upsert_generic_order(self, source: str, order_id: str, order_data: dict, phone: str, customer_name: str) -> None:
        await self.execute(
            """INSERT INTO raw_orders (source, order_id, raw_data, phone, customer_name, fetched_at)
               VALUES ($1, $2, $3::jsonb, $4, $5, $6)
               ON CONFLICT (source, order_id) DO UPDATE SET
                   raw_data = EXCLUDED.raw_data,
                   phone = EXCLUDED.phone,
                   customer_name = EXCLUDED.customer_name,
                   fetched_at = EXCLUDED.fetched_at""",
            source,
            str(order_id),
            json.dumps(order_data, default=str),
            phone,
            customer_name,
            datetime.utcnow(),
        )

    async def get_bill_customer_mapping(self) -> list[dict]:
        rows = await self.fetch(
            "SELECT phone, customer_id FROM raw_orders WHERE source = 'bill' AND raw_data->>'type' = 'customer'"
        )
        return [dict(r) for r in rows]

    async def get_grouped_by_phone(self) -> list[dict]:
        rows = await self.fetch("""
            SELECT
                phone,
                jsonb_agg(jsonb_build_object(
                    'source', source,
                    'data', raw_data,
                    'customer_name', customer_name,
                    'customer_total_spent', customer_total_spent
                )) AS records,
                array_agg(DISTINCT customer_name) FILTER (WHERE customer_name != '') AS names,
                array_agg(DISTINCT source) AS sources
            FROM raw_orders
            WHERE phone != ''
            GROUP BY phone
        """)
        return [dict(r) for r in rows]

    async def get_distinct_tenant_ids(self) -> list[str]:
        rows = await self.fetch(
            "SELECT DISTINCT raw_data->>'tenantId' AS tid FROM raw_orders WHERE raw_data->>'tenantId' IS NOT NULL"
        )
        return [r["tid"] for r in rows if r["tid"]]
