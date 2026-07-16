from typing import Optional

from repositories.customer_repo import CustomerRepository
from repositories.feature_repo import FeatureRepository


def _calculate_customer_score(customer: dict, features: Optional[dict] = None) -> dict:
    """Score a customer on multiple factors and return a verdict."""
    total_spent = float(customer.get("total_spent", 0) or 0)
    total_orders = int(customer.get("total_orders", 0) or 0)
    total_bills = int(customer.get("total_bills", 0) or 0)
    sources = customer.get("sources", []) or []
    alerts = customer.get("alerts", []) or []
    orders = customer.get("orders", []) or []
    comments = customer.get("comments", []) or []

    score = 0
    positives = []
    negatives = []

    # --- Multi-platform usage (good) ---
    if len(sources) >= 3:
        score += 25
        positives.append(f"active on {len(sources)} platforms")
    elif len(sources) >= 2:
        score += 15
        positives.append("purchases from multiple platforms")
    elif len(sources) == 1:
        score += 5

    # --- Spending (good) ---
    if total_spent >= 100000:
        score += 25
        positives.append("high spender with significant lifetime value")
    elif total_spent >= 50000:
        score += 20
        positives.append("strong spending history")
    elif total_spent >= 10000:
        score += 10
        positives.append("moderate spending")

    # --- Order frequency (good) ---
    if total_orders >= 20:
        score += 20
        positives.append("frequent buyer with repeat purchases")
    elif total_orders >= 10:
        score += 15
        positives.append("consistent ordering pattern")
    elif total_orders >= 3:
        score += 5

    # --- Returns (bad) ---
    return_count = 0
    for o in orders:
        status = (o.get("status") or "").lower()
        if status in ("cancelled", "returned", "refunded"):
            return_count += 1
    if total_orders > 0:
        return_rate = return_count / total_orders
    else:
        return_rate = 0

    if return_rate > 0.4:
        score -= 30
        negatives.append(f"very high return/cancellation rate ({return_count} of {total_orders} orders)")
    elif return_rate > 0.2:
        score -= 15
        negatives.append(f"elevated return/cancellation rate ({return_count} of {total_orders} orders)")
    elif return_count > 0:
        score -= 5

    # --- Alerts / negative behavior (bad) ---
    neg_alerts = [a for a in alerts if a.get("severity") == "warning" or a.get("type") in ("negative_comment", "bad_command")]
    if len(neg_alerts) >= 5:
        score -= 25
        negatives.append(f"multiple alerts ({len(neg_alerts)}) for negative behavior")
    elif len(neg_alerts) >= 2:
        score -= 10
        negatives.append(f"several alerts ({len(neg_alerts)}) flagged")

    # --- Negative comments ---
    neg_comments = [c for c in comments if c.get("is_negative")]
    if len(neg_comments) >= 3:
        score -= 15
        negatives.append(f"multiple negative comments ({len(neg_comments)})")
    elif len(neg_comments) >= 1:
        score -= 5

    # --- Payment health (from features) ---
    if features:
        payment_health = float(features.get("payment_health_score", 50) or 50)
        return_rate_feat = float(features.get("return_rate", 0) or 0)
        churn = float(features.get("churn_probability", 0) or 0)
        days_inactive = int(features.get("days_since_last_activity", 0) or 0)
        orders_30d = int(features.get("total_orders_30d", 0) or 0)

        if return_rate_feat > return_rate:
            return_rate = return_rate_feat
            if return_rate > 0.4:
                score -= 20
                negatives.append("high return rate based on behavior data")
            elif return_rate > 0.2:
                score -= 10

        if payment_health < 30:
            score -= 15
            negatives.append("poor payment health")
        elif payment_health > 70:
            score += 10
            positives.append("good payment history")

        if churn > 0.7:
            score -= 15
            negatives.append("very likely to churn")
        elif churn > 0.5:
            score -= 5

        if days_inactive > 180:
            score -= 10
            negatives.append("inactive for over 6 months")
        elif days_inactive > 90:
            score -= 5

        if orders_30d >= 3:
            score += 10
            positives.append("very active recently")
        elif orders_30d >= 1:
            score += 5
            positives.append("recently active")

    # --- Clamp score 0-100 ---
    score = max(0, min(100, score))

    if score >= 70:
        verdict = "Good Customer"
    elif score >= 40:
        verdict = "Average Customer"
    else:
        verdict = "At-Risk Customer"

    return {
        "score": score,
        "verdict": verdict,
        "positives": positives,
        "negatives": negatives,
        "return_rate": return_rate,
    }


def _generate_business_summary(customer: dict, features: Optional[dict] = None) -> str:
    name = customer.get("name", "Unknown")
    total_spent = float(customer.get("total_spent", 0) or 0)
    total_orders = int(customer.get("total_orders", 0) or 0)
    total_bills = int(customer.get("total_bills", 0) or 0)

    assessment = _calculate_customer_score(customer, features)

    parts = []

    # Verdict
    parts.append(f"{name} is assessed as a {assessment['verdict']} (score: {assessment['score']}/100).")

    # Basic stats
    spend_text = f"Total spend is \u20b9{total_spent:,.2f} across {total_orders} order(s)"
    if total_bills > 0:
        spend_text += f" and {total_bills} bill(s)"
    spend_text += "."
    parts.append(spend_text)

    # What they do right
    if assessment["positives"]:
        parts.append("Strengths: " + "; ".join(assessment["positives"]) + ".")

    # What's wrong
    if assessment["negatives"]:
        parts.append("Concerns: " + "; ".join(assessment["negatives"]) + ".")

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
