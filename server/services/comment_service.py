import httpx
from datetime import datetime

from config.settings import API_KEYS, SENTIMENT_THRESHOLD
from repositories.comment_repo import CommentRepository
from repositories.alert_repo import AlertRepository
from repositories.order_repo import RawOrderRepository
from services.cache_manager import cache_manager

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _analyzer = SentimentIntensityAnalyzer()
except ImportError:
    _analyzer = None


def _analyze_sentiment(text: str) -> dict:
    if not text or not _analyzer:
        return {"score": 0.0, "label": "neutral", "is_negative": False}
    scores = _analyzer.polarity_scores(text)
    compound = scores["compound"]
    if compound <= SENTIMENT_THRESHOLD:
        label = "negative"
        is_neg = True
    elif compound >= 0.3:
        label = "positive"
        is_neg = False
    else:
        label = "neutral"
        is_neg = False
    return {"score": compound, "label": label, "is_negative": is_neg}


class CommentService:
    def __init__(self, comment_repo=None, alert_repo=None, order_repo=None):
        self._comment_repo = comment_repo or CommentRepository()
        self._alert_repo = alert_repo or AlertRepository()
        self._order_repo = order_repo or RawOrderRepository()

    async def _fetch_comment_rules(self, tenant_id: str, page: int = 1, limit: int = 100):
        headers = {
            "Authorization": f"Bearer {API_KEYS['instaxbot']['key']}",
            "Content-Type": "application/json"
        }
        params = {"tenentId": tenant_id, "page": page, "limit": limit}
        url = "https://app.instaxbot.com/api/commentAutomationroute/rules"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                print(f"Error fetching rules for tenant {tenant_id}: {e}")
                return None

    async def analyze_and_store(self, tenant_id: str) -> dict:
        rules_data = await self._fetch_comment_rules(tenant_id, page=1, limit=1000)

        if not rules_data:
            return {"error": "No rules fetched"}

        rules = []
        if isinstance(rules_data, dict) and "data" in rules_data:
            data = rules_data["data"]
            if isinstance(data, list):
                rules = data
            elif isinstance(data, dict):
                rules = data.get("rules", data.get("items", [data]))

        results = []

        for rule in rules:
            trigger_text = rule.get("triggerText", "")
            comment_text = rule.get("commentReply", rule.get("replyText", ""))
            username = rule.get("username", "")

            sentiment = _analyze_sentiment(comment_text or trigger_text)

            await self._comment_repo.insert(
                tenant_id=tenant_id,
                media_id=rule.get("mediaId", ""),
                username=username,
                text=comment_text or trigger_text,
                sentiment_score=sentiment["score"],
                sentiment_label=sentiment["label"],
                is_negative=sentiment["is_negative"],
                triggered_rule=trigger_text,
            )

            if sentiment["is_negative"]:
                exists = await self._alert_repo.exists_by_message_pattern(f"%@{username}%")
                if not exists:
                    await self._alert_repo.insert(
                        alert_type="negative_comment",
                        message=f"Negative comment from @{username}: '{(comment_text or trigger_text)[:100]}'",
                        severity="warning",
                        source="instagram",
                    )

            results.append({
                "trigger_text": trigger_text,
                "sentiment": sentiment["label"],
                "is_negative": sentiment["is_negative"]
            })

        await cache_manager.invalidate_prefix("cust:list")
        await cache_manager.invalidate("dash:stats")
        return {"analyzed": len(results), "negative_count": sum(1 for r in results if r["is_negative"])}

    async def get_tenant_ids(self) -> list:
        ids = await self._order_repo.get_distinct_tenant_ids()
        if not ids:
            ids = ["5573c0ef-f0b0-4477-8681-c50e97a48280"]
        return ids
