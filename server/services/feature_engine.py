from datetime import datetime, timezone
from typing import Any

from repositories.feature_repo import FeatureRepository


_PAID_STATUSES = {
    "paid", "shipped", "delivered", "completed", "confirmed", "processing",
    "tracked", "shipping_selected", "printed", "packed",
    "created", "dispatched",
}


def _parse_ts(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, datetime):
        return value.timestamp()
    return 0.0


def _days_ago(value) -> int:
    if not value:
        return 999
    now = datetime.utcnow()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                value = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        else:
            return 999
    if isinstance(value, datetime):
        return (now - value).days
    return 999


class FeatureEngine:
    def __init__(self, feature_repo=None):
        self._repo = feature_repo or FeatureRepository()

    def compute_features(self, customer: dict) -> dict:
        orders = customer.get("orders", []) or []
        bills = customer.get("bills", []) or []
        all_transactions = orders + bills

        total_orders = customer.get("total_orders", 0) or 0
        total_bills = customer.get("total_bills", 0) or 0
        total_spent = float(customer.get("total_spent", 0) or 0)

        lifetime_value = total_spent
        average_order_value = round(total_spent / max(total_orders, 1), 2)
        purchase_frequency = round(total_orders / max(len(all_transactions), 1), 4)

        paid_orders = [o for o in orders if str(o.get("status", "")).lower() in _PAID_STATUSES]
        paid_bills = [b for b in bills if str(b.get("status", "")).lower() in _PAID_STATUSES]
        paid_count = len(paid_orders) + len(paid_bills)
        return_rate = round(
            (total_orders - paid_count) / max(total_orders, 1), 4
        ) if total_orders > 0 else 0.0

        now = datetime.utcnow()
        dates_ts = []
        for t in all_transactions:
            dt = t.get("date", "") or t.get("createdAt", "") or t.get("updatedAt", "")
            if dt:
                d = _days_ago(dt)
                if d != 999:
                    dates_ts.append(d)

        days_since_last_activity = min(dates_ts) if dates_ts else 999
        customer_ts = customer.get("last_activity")
        if customer_ts:
            cust_days = _days_ago(customer_ts)
            days_since_last_activity = min(days_since_last_activity, cust_days)

        last_30d = now.timestamp() - 30 * 86400
        last_90d = now.timestamp() - 90 * 86400

        total_orders_30d = 0
        total_orders_90d = 0
        total_spent_30d = 0.0
        total_spent_90d = 0.0

        for o in orders:
            d = o.get("date", "") or o.get("createdAt", "")
            if d:
                ts = _parse_ts(d)
                if ts == 0:
                    dd = _days_ago(d)
                    ts = now.timestamp() - dd * 86400
                if ts >= last_90d:
                    total_orders_90d += 1
                    amt = float(o.get("amount", 0) or 0)
                    total_spent_90d += amt
                    if ts >= last_30d:
                        total_orders_30d += 1
                        total_spent_30d += amt

        for b in bills:
            d = b.get("date", "")
            if d:
                dd = _days_ago(d)
                ts = now.timestamp() - dd * 86400
                if ts >= last_90d:
                    total_orders_90d += 1
                    total_spent_90d += float(b.get("amount", 0) or 0)
                    if ts >= last_30d:
                        total_orders_30d += 1
                        total_spent_30d += float(b.get("amount", 0) or 0)

        loyalty_score = round(
            min(total_orders * 5 + (days_since_last_activity < 30) * 20 + (total_spent > 10000) * 15, 100), 2
        )

        churn_probability = round(
            min((days_since_last_activity / 365) * 0.8 + (1 - purchase_frequency) * 0.2, 1), 4
        )

        payment_health_score = round(
            max(0, min(100 - (return_rate * 200) + (total_orders > 5) * 10, 100)), 2
        )

        sources = customer.get("sources", []) or []
        comment_count = customer.get("comment_count", 0) or 0

        items_seen = {}
        for o in orders:
            for item in (o.get("items", []) or []):
                name = item.get("name", "") or item.get("product", "") or ""
                if name:
                    items_seen[name] = items_seen.get(name, 0) + 1

        favorite_products = sorted(items_seen, key=items_seen.get, reverse=True)[:5] if items_seen else []
        complaint_count = sum(1 for o in orders if str(o.get("status", "")).lower() == "cancelled")

        features = {
            "feature_version": 1,
            "lifetime_value": round(lifetime_value, 2),
            "purchase_frequency": purchase_frequency,
            "average_order_value": average_order_value,
            "churn_probability": churn_probability,
            "loyalty_score": loyalty_score,
            "return_rate": return_rate,
            "payment_health_score": payment_health_score,
            "days_since_last_activity": days_since_last_activity,
            "total_orders_30d": total_orders_30d,
            "total_orders_90d": total_orders_90d,
            "total_spent_30d": round(total_spent_30d, 2),
            "total_spent_90d": round(total_spent_90d, 2),
            "total_orders": total_orders,
            "total_bills": total_bills,
            "total_spent": round(total_spent, 2),
            "comment_count": comment_count,
            "source_count": len(sources),
            "sources": sources,
            "complaint_count": complaint_count,
            "favorite_products": favorite_products,
            "customer_lifetime_days": days_since_last_activity,
        }
        features["features_snapshot"] = features
        return features

    async def compute_and_store(self, customer: dict) -> dict:
        features = self.compute_features(customer)
        await self._repo.upsert(customer["customer_id"], features)
        return features
