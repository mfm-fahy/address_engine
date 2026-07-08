from typing import Optional

from repositories.customer_repo import CustomerRepository
from repositories.feature_repo import FeatureRepository


def _summarize_orders(customer: dict, features: Optional[dict] = None) -> str:
    orders = customer.get("orders", []) or []
    if not orders:
        return "No orders found."

    total = len(orders)
    total_spent = float(customer.get("total_spent", 0) or 0)
    sources = {}
    statuses = {}
    dates = []

    for o in orders:
        src = o.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
        st = o.get("status", "").lower()
        statuses[st] = statuses.get(st, 0) + 1
        d = o.get("date", "")
        if d:
            dates.append(d)

    parts = [f"{total} order(s) totaling \u20b9{total_spent:,.2f}."]

    if sources:
        src_summary = ", ".join(f"{k}: {v}" for k, v in sorted(sources.items(), key=lambda x: -x[1]))
        parts.append(f"Sources: {src_summary}.")

    if dates:
        dates.sort(reverse=True)
        parts.append(f"Most recent: {dates[0][:10]}.")
        if len(dates) >= 2:
            parts.append(f"Earliest: {dates[-1][:10]}.")

    if features:
        orders_30d = int(features.get("total_orders_30d", 0) or 0)
        spent_30d = float(features.get("total_spent_30d", 0) or 0)
        aov = float(features.get("average_order_value", 0) or 0)
        if orders_30d:
            parts.append(f"{orders_30d} order(s) in last 30d (\u20b9{spent_30d:,.2f}).")
        if aov:
            parts.append(f"Avg order value: \u20b9{aov:,.2f}.")
    elif total > 0:
        aov = total_spent / total
        parts.append(f"Avg order value: \u20b9{aov:,.2f}.")

    return " ".join(parts)


def _summarize_bills(customer: dict) -> str:
    bills = customer.get("bills", []) or []
    if not bills:
        return "No bills found."

    total = len(bills)
    total_amount = sum(float(b.get("amount", 0) or 0) for b in bills)
    orgs = {}
    dates = []

    for b in bills:
        org = b.get("org_name", "unknown")
        orgs[org] = orgs.get(org, 0) + 1
        d = b.get("date", "")
        if d:
            dates.append(d)

    parts = [f"{total} bill(s) totaling \u20b9{total_amount:,.2f}."]

    if orgs:
        org_summary = ", ".join(f"{k}: {v}" for k, v in sorted(orgs.items(), key=lambda x: -x[1]))
        parts.append(f"Organizations: {org_summary}.")

    if dates:
        dates.sort(reverse=True)
        parts.append(f"Most recent: {dates[0][:10]}.")

    return " ".join(parts)


def _summarize_stores(customer: dict) -> str:
    stores = customer.get("stores", []) or []
    if not stores:
        return "No stores data."

    total = len(stores)
    total_store_spent = sum(float(s.get("total_spent", 0) or 0) for s in stores)
    by_type = {}
    sorted_stores = sorted(stores, key=lambda s: float(s.get("total_spent", 0) or 0), reverse=True)

    for s in stores:
        t = s.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    parts = [f"Purchased from {total} store(s), totaling \u20b9{total_store_spent:,.2f}."]
    if by_type:
        type_summary = ", ".join(f"{k}: {v}" for k, v in sorted(by_type.items(), key=lambda x: -x[1]))
        parts.append(f"Types: {type_summary}.")

    top_stores = sorted_stores[:3]
    if top_stores:
        top_names = [f"{s.get('name', '?')} (\u20b9{float(s.get('total_spent', 0) or 0):,.0f})" for s in top_stores]
        parts.append(f"Top: {', '.join(top_names)}.")

    return " ".join(parts)


def _summarize_timeline(customer: dict) -> str:
    orders = customer.get("orders", []) or []
    bills = customer.get("bills", []) or []
    alerts = customer.get("alerts", []) or []

    if not orders and not bills and not alerts:
        return "No activity recorded."

    parts = []
    if orders:
        parts.append(f"{len(orders)} order(s)")
    if bills:
        parts.append(f"{len(bills)} bill(s)")
    if alerts:
        parts.append(f"{len(alerts)} alert(s)")

    all_dates = []
    for o in orders:
        d = o.get("date", "")
        if d:
            all_dates.append(d)
    for b in bills:
        d = b.get("date", "")
        if d:
            all_dates.append(d)

    summary = f"Timeline includes {', '.join(parts)}."
    if all_dates:
        all_dates.sort(reverse=True)
        summary += f" Spanning {all_dates[-1][:10]} to {all_dates[0][:10]}."

    return summary


def _summarize_alerts(customer: dict) -> str:
    alerts = customer.get("alerts", []) or []
    if not alerts:
        return "No active alerts."

    total = len(alerts)
    by_severity = {}
    by_type = {}

    for a in alerts:
        sev = a.get("severity", "info")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        t = a.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    parts = [f"{total} alert(s)."]
    if by_severity:
        parts.append(f"Severity: {', '.join(f'{k}: {v}' for k, v in sorted(by_severity.items(), key=lambda x: -x[1]))}.")
    if by_type:
        type_summary = ", ".join(f"{k}: {v}" for k, v in sorted(by_type.items(), key=lambda x: -x[1])[:3])
        parts.append(f"Types: {type_summary}.")

    return " ".join(parts)


class SectionSummarizer:
    def __init__(self, customer_repo=None, feature_repo=None):
        self._repo = customer_repo or CustomerRepository()
        self._feature_repo = feature_repo or FeatureRepository()

    async def get_section_summaries(self, customer_id: str) -> dict:
        customer = await self._repo.get_by_id(customer_id)
        if not customer:
            raise ValueError("Customer not found")

        features = None
        try:
            features = await self._feature_repo.get_by_customer_id(customer_id)
        except Exception as e:
            print(f"[section-summarizer] Failed to fetch features for {customer_id}: {e}")

        return {
            "customer_id": customer_id,
            "sections": {
                "orders": _summarize_orders(customer, features),
                "bills": _summarize_bills(customer),
                "stores": _summarize_stores(customer),
                "timeline": _summarize_timeline(customer),
                "alerts": _summarize_alerts(customer),
            },
        }


_section_summarizer: Optional[SectionSummarizer] = None


def get_section_summarizer() -> SectionSummarizer:
    global _section_summarizer
    if _section_summarizer is None:
        _section_summarizer = SectionSummarizer()
    return _section_summarizer
