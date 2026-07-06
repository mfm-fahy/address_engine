from datetime import datetime
from typing import Any, Optional

from repositories.base import BaseRepository


_ALLOWED_SORT_COLS = {"total_spent", "total_orders", "name", "last_activity", "created_at"}


class DashboardRepository(BaseRepository):
    async def get_stats(self) -> dict:
        stats = await self.fetchrow(
            """SELECT COUNT(*) as total,
                      COALESCE(SUM(total_orders), 0) as total_orders,
                      COALESCE(SUM(total_bills), 0) as total_bills,
                      COALESCE(SUM(total_spent), 0) as total_revenue,
                      COALESCE(AVG(total_spent), 0) as avg_revenue,
                      COALESCE(SUM(comment_count), 0) as total_comments
               FROM customers"""
        )
        return dict(stats)

    async def get_source_breakdown(self) -> list[dict]:
        rows = await self.fetch(
            """SELECT unnest(sources) as src, COUNT(*) as cnt
               FROM customers GROUP BY src ORDER BY cnt DESC"""
        )
        return [dict(r) for r in rows]

    async def get_detailed_summary(self) -> dict:
        result = await self.fetchrow("""
            SELECT
                COUNT(*)                                            AS total_customers,
                COALESCE(SUM(total_orders), 0)                      AS total_orders,
                COALESCE(SUM(total_bills), 0)                       AS total_bills,
                COALESCE(SUM(total_spent), 0)                       AS total_revenue,
                COALESCE(AVG(total_spent), 0)                       AS avg_revenue_per_customer,
                COALESCE(SUM(comment_count), 0)                     AS total_comments,
                COUNT(*) FILTER (WHERE total_spent >= 50000)        AS vip_customers,
                COUNT(*) FILTER (WHERE total_orders = 0)            AS inactive_customers,
                COUNT(*) FILTER (WHERE total_orders > 0)            AS active_customers,
                COUNT(*) FILTER (WHERE needs_analysis = TRUE)       AS pending_analysis,
                COUNT(*) FILTER (WHERE array_length(sources, 1) > 1) AS multi_source_customers
            FROM customers
        """)
        return dict(result)

    async def get_customer_growth(self, limit: int = 12) -> list[dict]:
        rows = await self.fetch("""
            SELECT
                DATE_TRUNC('month', created_at)::DATE AS month,
                COUNT(*)                               AS new_customers
            FROM customers
            WHERE created_at IS NOT NULL
            GROUP BY month
            ORDER BY month DESC
            LIMIT $1
        """, limit)
        return [dict(r) for r in rows]

    async def get_revenue_trends(self, limit: int = 12) -> list[dict]:
        rows = await self.fetch("""
            SELECT
                DATE_TRUNC('month', GREATEST(COALESCE(updated_at, created_at), created_at))::DATE AS month,
                COUNT(*)                                                                          AS customer_count,
                COALESCE(SUM(total_spent), 0)                                                     AS revenue
            FROM customers
            WHERE total_spent > 0
            GROUP BY month
            ORDER BY month DESC
            LIMIT $1
        """, limit)
        return [dict(r) for r in rows]

    async def get_top_customers(self, limit: int = 10) -> list[dict]:
        rows = await self.fetch("""
            SELECT
                customer_id, phone, name, email,
                total_orders, total_spent, sources,
                last_activity
            FROM customers
            WHERE total_spent > 0
            ORDER BY total_spent DESC
            LIMIT $1
        """, limit)
        return [dict(r) for r in rows]

    async def get_top_products(self, limit: int = 10) -> list[dict]:
        rows = await self.fetch("""
            SELECT
                item->>'name' AS product_name,
                COUNT(*)      AS order_count,
                SUM(COALESCE((item->>'quantity')::INTEGER, 1)) AS total_quantity
            FROM customers,
                 LATERAL jsonb_array_elements(orders) AS o,
                 LATERAL jsonb_array_elements(COALESCE(o->'items', '[]'::jsonb)) AS item
            WHERE item->>'name' != ''
            GROUP BY product_name
            ORDER BY order_count DESC
            LIMIT $1
        """, limit)
        return [dict(r) for r in rows]

    async def get_churn_risk_summary(self) -> dict:
        result = await self.fetchrow("""
            SELECT
                COUNT(*)                                                                    AS total_with_features,
                COUNT(*) FILTER (WHERE churn_probability >= 0.5)                             AS high_risk_count,
                COUNT(*) FILTER (WHERE churn_probability BETWEEN 0.25 AND 0.5)               AS medium_risk_count,
                COUNT(*) FILTER (WHERE churn_probability < 0.25)                             AS low_risk_count,
                COALESCE(AVG(churn_probability), 0)                                          AS avg_churn_probability,
                COUNT(*) FILTER (WHERE loyalty_score >= 70)                                  AS loyal_customers,
                COUNT(*) FILTER (WHERE return_rate >= 0.3)                                   AS high_return_risk,
                COUNT(*) FILTER (WHERE payment_health_score < 40)                            AS payment_risk
            FROM customer_features
        """)
        return dict(result)

    async def get_recent_activities(self, limit: int = 10) -> list[dict]:
        rows = await self.fetch("""
            SELECT
                customer_id, phone, name, total_orders, total_spent,
                last_activity, updated_at
            FROM customers
            ORDER BY updated_at DESC NULLS LAST
            LIMIT $1
        """, limit)
        return [dict(r) for r in rows]

    async def get_paginated_customers(
        self, limit: int = 50, offset: int = 0,
        sort: str = "last_activity", order: str = "DESC",
        search: str = "",
    ) -> list[dict]:
        sort_col = sort if sort in _ALLOWED_SORT_COLS else "last_activity"
        sort_dir = "ASC" if order.upper() == "ASC" else "DESC"
        if search:
            pattern = f"%{search}%"
            rows = await self.fetch(
                f"""SELECT customer_id, phone, name, email, username,
                           total_orders, total_bills, total_spent,
                           sources, comment_count, last_activity, updated_at
                    FROM customers
                    WHERE name ILIKE $1 OR email ILIKE $1 OR phone ILIKE $1 OR username ILIKE $1
                    ORDER BY {sort_col} {sort_dir} NULLS LAST
                    LIMIT $2 OFFSET $3""",
                pattern, limit, offset,
            )
        else:
            rows = await self.fetch(
                f"""SELECT customer_id, phone, name, email, username,
                           total_orders, total_bills, total_spent,
                           sources, comment_count, last_activity, updated_at
                    FROM customers
                    ORDER BY {sort_col} {sort_dir} NULLS LAST
                    LIMIT $1 OFFSET $2""",
                limit, offset,
            )
        return [dict(r) for r in rows]

    async def count_customers_filtered(self, search: str = "") -> int:
        if search:
            pattern = f"%{search}%"
            return await self.fetchval(
                "SELECT COUNT(*) FROM customers WHERE name ILIKE $1 OR email ILIKE $1 OR phone ILIKE $1 OR username ILIKE $1",
                pattern,
            )
        return await self.fetchval("SELECT COUNT(*) FROM customers")
