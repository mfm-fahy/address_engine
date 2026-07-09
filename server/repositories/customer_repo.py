import json
from datetime import datetime
from typing import Any, Optional

from repositories.base import BaseRepository


class CustomerRepository(BaseRepository):
    async def count_all(self) -> int:
        return await self.fetchval("SELECT COUNT(*) FROM customers")

    async def get_all(self) -> list[dict]:
        rows = await self.fetch("""
            SELECT
                customer_id, phone, name, email, username,
                total_orders, total_bills, total_spent,
                sources, comment_count, last_activity, updated_at, metadata, stores,
                address
            FROM customers
            ORDER BY last_activity DESC NULLS LAST
        """)
        result = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("stores"), str):
                d["stores"] = json.loads(d["stores"])
            if isinstance(d.get("address"), str):
                d["address"] = json.loads(d["address"])
            result.append(d)
        return result

    async def get_by_id(self, customer_id: str) -> Optional[dict]:
        row = await self.fetchrow(
            """SELECT customer_id, phone, name, email, username,
                      total_orders, total_bills, total_spent,
                      orders, bills, sources, comment_count,
                      last_activity, created_at, updated_at, metadata, stores,
                      profile_summary, address
               FROM customers
               WHERE customer_id = $1 OR phone = $1""",
            customer_id,
        )
        if not row:
            return None
        result = dict(row)
        cid = result.pop("customer_id", "")
        result["_id"] = cid
        for col in ("orders", "bills", "metadata", "stores", "address"):
            if isinstance(result.get(col), str):
                result[col] = json.loads(result[col])

        comments = await self.fetch(
            """SELECT id, tenant_id, media_id, username, text,
                      sentiment_score, sentiment_label, is_negative,
                      triggered_rule, created_at
               FROM comments
               WHERE customer_id = $1
               ORDER BY created_at DESC
               LIMIT 50""",
            cid,
        )
        result["comments"] = [dict(r) for r in comments]

        alerts = await self.fetch(
            """SELECT id, type, message, severity, source, is_read, created_at
               FROM alerts
               WHERE customer_id = $1
               ORDER BY created_at DESC
               LIMIT 50""",
            cid,
        )
        result["alerts"] = [dict(r) for r in alerts]
        return result

    async def get_by_id_raw(self, customer_id: str) -> Optional[dict]:
        row = await self.fetchrow(
            "SELECT * FROM customers WHERE customer_id = $1 OR phone = $1",
            customer_id,
        )
        if not row:
            return None
        return dict(row)

    async def search(self, query: str) -> list[dict]:
        pattern = f"%{query}%"
        rows = await self.fetch(
            """SELECT customer_id, phone, name, email, username,
                      total_orders, total_bills, total_spent,
                      sources, comment_count, last_activity
               FROM customers
               WHERE name ILIKE $1 OR email ILIKE $1
                  OR phone ILIKE $1 OR username ILIKE $1
               ORDER BY last_activity DESC NULLS LAST""",
            pattern,
        )
        return [dict(r) for r in rows]

    async def upsert(self, data: dict) -> None:
        customer_id = data["customer_id"]
        phone = data["phone"]
        name = data.get("name", "")
        email = data.get("email", "")
        username = data.get("username", "")
        total_orders = data.get("total_orders", 0)
        total_bills = data.get("total_bills", 0)
        total_spent = data.get("total_spent", 0.0)
        orders = json.dumps(data.get("orders", []), default=str)
        bills = json.dumps(data.get("bills", []), default=str)
        sources = data.get("sources", [])
        last_activity = data.get("last_activity")
        now = data.get("updated_at", datetime.utcnow())
        metadata = json.dumps(data.get("metadata", {}), default=str)
        stores = json.dumps(data.get("stores", []), default=str)
        needs_analysis = data.get("needs_analysis", False)
        address = json.dumps(data.get("address", {}), default=str)

        await self.execute(
            """INSERT INTO customers (
                   customer_id, phone, name, email, username,
                   total_orders, total_bills, total_spent,
                   orders, bills, sources, last_activity, updated_at, metadata, stores,
                   needs_analysis, address
               ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10::jsonb, $11, $12, $13, $14::jsonb, $15::jsonb, $16, $17::jsonb)
               ON CONFLICT (customer_id) DO UPDATE SET
                   name = EXCLUDED.name,
                   email = EXCLUDED.email,
                   username = EXCLUDED.username,
                   total_orders = EXCLUDED.total_orders,
                   total_bills = EXCLUDED.total_bills,
                   total_spent = EXCLUDED.total_spent,
                   orders = EXCLUDED.orders,
                   bills = EXCLUDED.bills,
                   sources = EXCLUDED.sources,
                   last_activity = EXCLUDED.last_activity,
                   updated_at = EXCLUDED.updated_at,
                   metadata = EXCLUDED.metadata,
                   stores = EXCLUDED.stores,
                   needs_analysis = EXCLUDED.needs_analysis,
                   address = EXCLUDED.address""",
            customer_id, phone, name, email, username,
            total_orders, total_bills, round(total_spent, 2),
            orders, bills, list(sources) if not isinstance(sources, list) else sources,
            last_activity, now, metadata, stores,
            needs_analysis, address,
        )

    async def set_needs_analysis(self, customer_id: str, value: bool = True) -> None:
        await self.execute(
            "UPDATE customers SET needs_analysis = $1, updated_at = $2 WHERE customer_id = $3",
            value, datetime.utcnow(), customer_id,
        )

    async def mark_analyzed(self, customer_id: str) -> None:
        await self.set_needs_analysis(customer_id, False)

    async def get_needs_analysis_count(self) -> int:
        return await self.fetchval("SELECT COUNT(*) FROM customers WHERE needs_analysis = TRUE")

    async def get_pending_batch(self, limit: int = 10) -> list[str]:
        rows = await self.fetch(
            "SELECT customer_id FROM customers WHERE needs_analysis = TRUE ORDER BY updated_at ASC LIMIT $1",
            limit,
        )
        return [r["customer_id"] for r in rows]

    async def get_all_training(self) -> list[dict]:
        rows = await self.fetch(
            "SELECT * FROM customers ORDER BY last_activity DESC NULLS LAST"
        )
        return [dict(r) for r in rows]

    async def update_summary(self, customer_id: str, summary: str) -> None:
        await self.execute(
            "UPDATE customers SET profile_summary = $1, updated_at = $2 WHERE customer_id = $3",
            summary, datetime.utcnow(), customer_id,
        )

    async def get_profile(self, customer_id: str) -> Optional[dict]:
        row = await self.fetchrow(
            """SELECT customer_id, phone, name, email, username,
                      total_orders, total_bills, total_spent,
                      sources, comment_count, last_activity,
                      created_at, updated_at, metadata, stores,
                      address
               FROM customers
               WHERE customer_id = $1 OR phone = $1""",
            customer_id,
        )
        if not row:
            return None
        result = dict(row)
        for col in ("metadata", "stores", "address"):
            if isinstance(result.get(col), str):
                result[col] = json.loads(result[col])
        return result

    async def get_timeline(self, customer_id: str) -> list[dict]:
        rows = await self.fetch(
            """SELECT
                  'order' AS event_type,
                  (o->>'date')::TEXT AS event_date,
                  o->>'amount' AS amount,
                  o->>'status' AS status,
                  o->>'source' AS source
               FROM customers, jsonb_array_elements(orders) AS o
               WHERE customer_id = $1 AND orders != '[]'::jsonb
               UNION ALL
               SELECT
                  'bill' AS event_type,
                  (b->>'date')::TEXT AS event_date,
                  b->>'amount' AS amount,
                  b->>'status' AS status,
                  b->>'source' AS source
               FROM customers, jsonb_array_elements(bills) AS b
               WHERE customer_id = $1 AND bills != '[]'::jsonb
               UNION ALL
               SELECT
                  'alert' AS event_type,
                  created_at::TEXT AS event_date,
                  message AS amount,
                  severity AS status,
                  source AS source
               FROM alerts
               WHERE customer_id = $1
               ORDER BY event_date DESC NULLS LAST
               LIMIT 100""",
            customer_id,
        )
        return [dict(r) for r in rows]

    async def get_analytics(self, customer_id: str) -> Optional[dict]:
        row = await self.fetchrow(
            """SELECT
                  c.total_orders, c.total_bills, c.total_spent,
                  c.comment_count, c.last_activity,
                  c.created_at,
                  c.sources,
                  f.lifetime_value, f.purchase_frequency,
                  f.average_order_value, f.churn_probability,
                  f.loyalty_score, f.return_rate,
                  f.payment_health_score, f.days_since_last_activity,
                  f.total_orders_30d, f.total_orders_90d,
                  f.total_spent_30d, f.total_spent_90d
               FROM customers c
               LEFT JOIN customer_features f ON f.customer_id = c.customer_id
               WHERE c.customer_id = $1""",
            customer_id,
        )
        if not row:
            return None
        return dict(row)
