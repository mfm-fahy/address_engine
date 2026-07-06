import json
import os
from datetime import datetime
from typing import Any

import asyncpg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://customer360:customer360@localhost:5432/customer360",
)

_pool: asyncpg.Pool = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def json_serialize(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode()
    if isinstance(obj, set):
        return list(obj)
    return str(obj)


def clean_row(row: dict) -> dict:
    return {k: json_serialize(v) for k, v in row.items()}


def format_training_record(row: dict) -> dict:
    orders_raw = row.get("orders", "[]")
    bills_raw = row.get("bills", "[]")
    if isinstance(orders_raw, str):
        orders = json.loads(orders_raw)
    else:
        orders = orders_raw
    if isinstance(bills_raw, str):
        bills = json.loads(bills_raw)
    else:
        bills = bills_raw

    order_items = []
    for o in orders:
        items = o.get("items", [])
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    order_items.append(it.get("name", it.get("product", "")))
                else:
                    order_items.append(str(it))

    bill_items = []
    for b in bills:
        items = b.get("items", [])
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    bill_items.append(it.get("name", it.get("product", "")))
                else:
                    bill_items.append(str(it))

    return {
        "customer_id": row.get("customer_id", ""),
        "phone": row.get("phone", ""),
        "name": row.get("name", ""),
        "email": row.get("email", ""),
        "username": row.get("username", ""),
        "total_orders": row.get("total_orders", 0),
        "total_bills": row.get("total_bills", 0),
        "total_spent": float(row.get("total_spent", 0)),
        "sources": row.get("sources", []),
        "comment_count": row.get("comment_count", 0),
        "last_activity": json_serialize(row.get("last_activity")),
        "avg_order_value": round(
            float(row.get("total_spent", 0))
            / max(row.get("total_orders", 1), 1),
            2,
        ),
        "purchased_items": sorted(set(order_items + bill_items)),
    }


async def handle_list_resources():
    from mcp.types import Resource

    return [
        Resource(
            uri="customers://list",
            name="Customer List",
            description="List of all customer profiles with summary fields",
            mimeType="application/json",
        ),
        Resource(
            uri="customers://training/export",
            name="Training Data Export",
            description="Customer profiles formatted for ML model training",
            mimeType="application/json",
        ),
        Resource(
            uri="customers://stats",
            name="Customer Statistics",
            description="Aggregate statistics over all customer profiles",
            mimeType="application/json",
        ),
        Resource(
            uri="alerts://list",
            name="Alerts List",
            description="All customer alerts",
            mimeType="application/json",
        ),
    ]


async def handle_read_resource(uri: str) -> str:
    pool = await get_pool()

    if uri == "customers://list":
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT customer_id, phone, name, email, username,
                          total_orders, total_bills, total_spent,
                          sources, comment_count, last_activity, updated_at
                   FROM customers ORDER BY last_activity DESC NULLS LAST"""
            )
            data = [clean_row(dict(r)) for r in rows]
        return json.dumps(data, default=str, indent=2)

    if uri == "customers://training/export":
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM customers ORDER BY last_activity DESC NULLS LAST"
            )
            data = [format_training_record(dict(r)) for r in rows]
        return json.dumps(data, default=str, indent=2)

    if uri == "customers://stats":
        async with pool.acquire() as conn:
            stats = await conn.fetchrow(
                """SELECT COUNT(*) as total,
                          COALESCE(SUM(total_orders), 0) as total_orders,
                          COALESCE(SUM(total_bills), 0) as total_bills,
                          COALESCE(SUM(total_spent), 0) as total_revenue,
                          COALESCE(AVG(total_spent), 0) as avg_revenue,
                          COALESCE(SUM(comment_count), 0) as total_comments
                   FROM customers"""
            )
            sources = await conn.fetch(
                """SELECT unnest(sources) as src, COUNT(*) as cnt
                   FROM customers GROUP BY src ORDER BY cnt DESC"""
            )
            data = {
                "total_customers": stats["total"],
                "total_orders": stats["total_orders"],
                "total_bills": stats["total_bills"],
                "total_revenue": float(stats["total_revenue"]),
                "avg_revenue_per_customer": round(float(stats["avg_revenue"]), 2),
                "total_comments": stats["total_comments"],
                "by_source": {r["src"]: r["cnt"] for r in sources},
            }
        return json.dumps(data, default=str, indent=2)

    if uri == "alerts://list":
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM alerts ORDER BY created_at DESC LIMIT 100"
            )
            data = [clean_row(dict(r)) for r in rows]
        return json.dumps(data, default=str, indent=2)

    raise ValueError(f"Unknown resource URI: {uri}")


async def handle_list_tools():
    from mcp.types import Tool

    return [
        Tool(
            name="export_training_data",
            description="Export all customer profiles formatted for ML model training. Returns structured JSON with features like total_orders, total_spent, avg_order_value, sources, comment_count, purchased_items.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_customer_by_id",
            description="Get full customer profile by customer_id or phone number",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Customer ID (e.g. CUST91...) or phone number",
                    }
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="search_customers",
            description="Search customers by name, email, phone, or username",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term to match against name, email, phone, or username",
                    }
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_customer_stats",
            description="Get aggregate statistics over all customer profiles",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_alerts",
            description="Get recent alerts for all customers",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of alerts to return (default 50)",
                    }
                },
            },
        ),
    ]


async def handle_call_tool(name: str, arguments: dict = None):
    from mcp.types import TextContent

    pool = await get_pool()
    args = arguments or {}

    if name == "export_training_data":
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM customers ORDER BY last_activity DESC NULLS LAST"
            )
            data = [format_training_record(dict(r)) for r in rows]
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "total": len(data),
                        "customers": data,
                        "export_metadata": {
                            "exported_at": datetime.utcnow().isoformat(),
                            "total_customers": len(data),
                            "features": [
                                "customer_id",
                                "phone",
                                "name",
                                "email",
                                "total_orders",
                                "total_spent",
                                "avg_order_value",
                                "sources",
                                "comment_count",
                                "purchased_items",
                                "last_activity",
                            ],
                            "format": "tabular_json",
                            "recommended_use": "supervised_learning",
                        },
                    },
                    default=str,
                    indent=2,
                ),
            )
        ]

    if name == "get_customer_by_id":
        cid = args.get("id", "")
        if not cid:
            raise ValueError("id is required")
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM customers WHERE customer_id = $1 OR phone = $1", cid
            )
            if not row:
                return [TextContent(type="text", text=json.dumps({"error": "Customer not found"}))]
            data = clean_row(dict(row))
            for col in ("orders", "bills", "metadata", "stores"):
                if isinstance(data.get(col), str):
                    data[col] = json.loads(data[col])
        return [TextContent(type="text", text=json.dumps(data, default=str, indent=2))]

    if name == "search_customers":
        q = args.get("query", "")
        if not q:
            raise ValueError("query is required")
        pattern = f"%{q}%"
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT customer_id, phone, name, email, username,
                          total_orders, total_bills, total_spent,
                          sources, comment_count, last_activity
                   FROM customers
                   WHERE name ILIKE $1 OR email ILIKE $1
                      OR phone ILIKE $1 OR username ILIKE $1
                   ORDER BY last_activity DESC NULLS LAST""",
                pattern,
            )
            data = [clean_row(dict(r)) for r in rows]
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"query": q, "total": len(data), "customers": data},
                    default=str,
                    indent=2,
                ),
            )
        ]

    if name == "get_customer_stats":
        async with pool.acquire() as conn:
            stats = await conn.fetchrow(
                """SELECT COUNT(*) as total,
                          COALESCE(SUM(total_orders), 0) as total_orders,
                          COALESCE(SUM(total_bills), 0) as total_bills,
                          COALESCE(SUM(total_spent), 0) as total_revenue,
                          COALESCE(AVG(total_spent), 0) as avg_revenue,
                          COALESCE(SUM(comment_count), 0) as total_comments
                   FROM customers"""
            )
            sources = await conn.fetch(
                """SELECT unnest(sources) as src, COUNT(*) as cnt
                   FROM customers GROUP BY src ORDER BY cnt DESC"""
            )
            data = {
                "total_customers": stats["total"],
                "total_orders": stats["total_orders"],
                "total_bills": stats["total_bills"],
                "total_revenue": float(stats["total_revenue"]),
                "avg_revenue_per_customer": round(float(stats["avg_revenue"]), 2),
                "total_comments": stats["total_comments"],
                "by_source": {r["src"]: r["cnt"] for r in sources},
            }
        return [TextContent(type="text", text=json.dumps(data, default=str, indent=2))]

    if name == "get_alerts":
        limit = args.get("limit", 50)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM alerts ORDER BY created_at DESC LIMIT $1", limit
            )
            data = [clean_row(dict(r)) for r in rows]
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"total": len(data), "alerts": data}, default=str, indent=2
                ),
            )
        ]

    raise ValueError(f"Unknown tool: {name}")
