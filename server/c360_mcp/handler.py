import json
import os
from datetime import datetime
from typing import Any

import asyncpg

from services.customer_service import CustomerService
from services.alert_service import AlertService
from services.dashboard_service import DashboardService
from services.recommendation_service import RecommendationService

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://customer360:customer360@localhost:5432/customer360",
)

_pool: asyncpg.Pool = None
_customer_svc: CustomerService = None
_alert_svc: AlertService = None
_dashboard_svc: DashboardService = None
_rec_svc: RecommendationService = None


async def _create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)


def _init_services(pool: asyncpg.Pool):
    global _customer_svc, _alert_svc, _dashboard_svc, _rec_svc
    from repositories.customer_repo import CustomerRepository
    from repositories.alert_repo import AlertRepository
    from repositories.dashboard_repo import DashboardRepository
    from repositories.recommendation_repo import RecommendationRepository
    from services.feature_engine import FeatureEngine
    from services.rule_engine import RuleEngine
    _customer_svc = CustomerService(CustomerRepository(pool=pool))
    _alert_svc = AlertService(AlertRepository(pool=pool))
    _dashboard_svc = DashboardService(DashboardRepository(pool=pool))
    _rec_svc = RecommendationService(
        customer_repo=CustomerRepository(pool=pool),
        rec_repo=RecommendationRepository(pool=pool),
        feature_engine=FeatureEngine(),
        rule_engine=RuleEngine(),
    )


async def get_pool() -> asyncpg.Pool:
    global _pool, _customer_svc, _alert_svc, _dashboard_svc
    if _pool is not None:
        return _pool

    # Try to use the shared application pool first
    try:
        from config.postgres import get_pool as get_main_pool
        main_pool = get_main_pool()
        if main_pool is not None:
            _pool = main_pool
            _init_services(_pool)
            return _pool
    except (ImportError, Exception):
        pass

    # Fallback: create dedicated pool (standalone mode)
    _pool = await _create_pool()
    _init_services(_pool)
    return _pool


async def close_pool():
    global _pool, _customer_svc, _alert_svc, _dashboard_svc
    if _pool:
        # Only close if this is our own pool (not the shared one)
        try:
            from config.postgres import get_pool as get_main_pool
            if get_main_pool() is not _pool:
                await _pool.close()
        except (ImportError, Exception):
            await _pool.close()
        _pool = None
        _customer_svc = None
        _alert_svc = None
        _dashboard_svc = None


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
    await get_pool()

    if uri == "customers://list":
        rows = await _customer_svc.get_all()
        data = [{k: json_serialize(v) for k, v in row.items()
                 if k in ("customer_id", "phone", "name", "email", "username",
                          "total_orders", "total_bills", "total_spent",
                          "sources", "comment_count", "last_activity", "updated_at")}
                for row in rows]
        return json.dumps(data, default=str, indent=2)

    if uri == "customers://training/export":
        rows = await _customer_svc.get_training_data()
        data = [format_training_record(row) for row in rows]
        return json.dumps(data, default=str, indent=2)

    if uri == "customers://stats":
        data = await _dashboard_svc.get_stats()
        return json.dumps(data, default=str, indent=2)

    if uri == "alerts://list":
        rows = await _alert_svc.get_all(limit=100)
        data = [clean_row(r) for r in rows]
        return json.dumps(data, default=str, indent=2)

    if uri == "recommendations://list":
        rows = await _rec_svc.get_all(status="active", limit=100)
        return json.dumps(rows, default=str, indent=2)

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
        Tool(
            name="get_customer_recommendations",
            description="Get AI-powered recommendations for a specific customer",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID (e.g. CUST91...)",
                    }
                },
                "required": ["customer_id"],
            },
        ),
    ]


async def handle_call_tool(name: str, arguments: dict = None):
    from mcp.types import TextContent

    await get_pool()
    args = arguments or {}

    if name == "export_training_data":
        rows = await _customer_svc.get_training_data()
        data = [format_training_record(row) for row in rows]
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
        from repositories.customer_repo import CustomerRepository
        pool = await get_pool()
        row = await CustomerRepository(pool=pool).get_by_id_raw(cid)
        if not row:
            return [TextContent(type="text", text=json.dumps({"error": "Customer not found"}))]
        data = clean_row(row)
        for col in ("orders", "bills", "metadata", "stores"):
            if isinstance(data.get(col), str):
                data[col] = json.loads(data[col])
        return [TextContent(type="text", text=json.dumps(data, default=str, indent=2))]

    if name == "search_customers":
        q = args.get("query", "")
        if not q:
            raise ValueError("query is required")
        rows = await _customer_svc.search(q)
        data = [clean_row(r) for r in rows]
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
        data = await _dashboard_svc.get_stats()
        return [TextContent(type="text", text=json.dumps(data, default=str, indent=2))]

    if name == "get_alerts":
        limit = args.get("limit", 50)
        rows = await _alert_svc.get_all(limit=limit)
        data = [clean_row(r) for r in rows]
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"total": len(data), "alerts": data}, default=str, indent=2
                ),
            )
        ]

    if name == "get_customer_recommendations":
        cid = args.get("customer_id", "")
        if not cid:
            raise ValueError("customer_id is required")
        rows = await _rec_svc.get_by_customer_id(cid)
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"customer_id": cid, "total": len(rows), "recommendations": rows},
                    default=str,
                    indent=2,
                ),
            )
        ]

    raise ValueError(f"Unknown tool: {name}")
