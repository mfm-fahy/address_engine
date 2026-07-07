from typing import Optional

from repositories.customer_repo import CustomerRepository
from repositories.feature_repo import FeatureRepository


def _generate_business_summary(customer: dict, features: Optional[dict] = None) -> str:
    name = customer.get("name", "Unknown")
    total_spent = float(customer.get("total_spent", 0) or 0)
    total_orders = int(customer.get("total_orders", 0) or 0)
    total_bills = int(customer.get("total_bills", 0) or 0)
    sources = customer.get("sources", []) or []
    stores = customer.get("stores", []) or []
    last_activity = customer.get("last_activity", "")
    alerts = customer.get("alerts", []) or []
    has_alerts = len(alerts) > 0

    store_count = len(stores)
    source_count = len(sources)

    parts = []
    parts.append(
        f"{name} has a total spend of \u20b9{total_spent:,.2f} "
        f"across {total_orders} order(s) and {total_bills} bill(s)."
    )

    if features:
        def _f(key, default):
            v = features.get(key)
            return v if v is not None else default

        ltv = float(_f("lifetime_value", total_spent))
        aov = float(_f("average_order_value", 0))
        churn = float(_f("churn_probability", 0))
        loyalty = float(_f("loyalty_score", 0))
        return_rate = float(_f("return_rate", 0))
        payment_health = float(_f("payment_health_score", 0))
        days_inactive = int(_f("days_since_last_activity", 999))
        orders_30d = int(_f("total_orders_30d", 0))
        spent_30d = float(_f("total_spent_30d", 0))

        parts.append(
            f"Average order value is \u20b9{aov:,.2f} "
            f"with a customer lifetime value of \u20b9{ltv:,.2f}."
        )

        recent_activity = []
        if orders_30d > 0:
            recent_activity.append(f"{orders_30d} order(s) in the last 30 days")
        if spent_30d > 0:
            recent_activity.append(f"\u20b9{spent_30d:,.2f} spent recently")
        if recent_activity:
            parts.append(f"Recent engagement shows {'; '.join(recent_activity)}.")

        opportunities = []
        risks = []

        if loyalty >= 70:
            opportunities.append("high loyalty score")
        if days_inactive <= 7:
            opportunities.append("recently active")
        if days_inactive <= 30 and orders_30d >= 2:
            opportunities.append("consistent purchase pattern")

        if churn >= 0.5:
            risks.append("elevated churn risk")
        if payment_health < 40:
            risks.append("low payment health")
        if return_rate > 0.2:
            risks.append("high return rate")
        if days_inactive > 90:
            risks.append("long inactivity period")

        if opportunities:
            parts.append(f"Opportunities include {', '.join(opportunities)}.")
        if risks:
            parts.append(f"Risks include {', '.join(risks)}.")
        if has_alerts:
            parts.append(f"Has {len(alerts)} active alert(s) requiring attention.")

    if source_count > 0:
        clean_sources = [s for s in sources if s]
        if clean_sources:
            parts.append(f"Data sources: {', '.join(clean_sources)}.")
    if store_count > 0:
        store_names = [s.get("name", "") for s in stores if s and s.get("name")]
        if store_names:
            parts.append(f"Stores: {', '.join(store_names[:5])}.")

    summary = " ".join(parts)

    word_count = len(summary.split())
    if word_count > 120:
        words = summary.split()
        summary = " ".join(words[:120])

    return summary


class ProfileSummarizer:
    def __init__(self, customer_repo=None, feature_repo=None):
        self._repo = customer_repo or CustomerRepository()
        self._feature_repo = feature_repo or FeatureRepository()

    async def generate_summary(self, customer: dict, customer_id: str = None) -> str:
        existing = customer.get("profile_summary", "")
        if existing and existing.strip():
            return existing

        cid = customer_id or customer.get("_id") or customer.get("customer_id", "")
        return await self.regenerate_summary(customer, cid)

    async def regenerate_summary(self, customer: dict, customer_id: str = None) -> str:
        cid = customer_id or customer.get("_id") or customer.get("customer_id", "")
        if not cid:
            raise ValueError("No customer ID available for summarization")

        try:
            features = await self._feature_repo.get_by_customer_id(cid)
        except Exception as e:
            print(f"[summarizer] Failed to fetch features for {cid}: {e}")
            features = None

        try:
            summary = _generate_business_summary(customer, features)
        except Exception as e:
            print(f"[summarizer] Failed to generate summary for {cid}: {e}")
            raise

        await self._repo.update_summary(cid, summary)
        return summary

    async def generate_for_all(self) -> int:
        rows = await self._repo.get_all()
        count = 0
        for row in rows:
            cid = row.get("customer_id") or row.get("_id", "")
            if not cid:
                continue
            try:
                customer = await self._repo.get_by_id(cid)
                if not customer:
                    continue
                await self.regenerate_summary(customer, cid)
                count += 1
            except Exception as e:
                print(f"[summarizer] Error generating summary for {cid}: {e}")
        return count


_profile_summarizer: Optional[ProfileSummarizer] = None


def get_profile_summarizer() -> ProfileSummarizer:
    global _profile_summarizer
    if _profile_summarizer is None:
        _profile_summarizer = ProfileSummarizer()
    return _profile_summarizer
