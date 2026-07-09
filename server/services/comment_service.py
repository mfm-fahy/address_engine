import httpx

from config.settings import API_KEYS, SENTIMENT_THRESHOLD, COMMENTS_URL, BAD_COMMANDS_URL
from repositories.comment_repo import CommentRepository
from repositories.alert_repo import AlertRepository
from repositories.order_repo import RawOrderRepository
from repositories.customer_repo import CustomerRepository
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


def _extract_items(data: dict) -> list:
    if isinstance(data, dict):
        if "data" in data:
            d = data["data"]
            if isinstance(d, list):
                return d
            if isinstance(d, dict):
                return d.get("items", d.get("comments", d.get("commands", [])))
        return data.get("items", data.get("comments", data.get("commands", [])))
    return []


class CommentService:
    def __init__(self, comment_repo=None, alert_repo=None, order_repo=None, customer_repo=None):
        self._comment_repo = comment_repo or CommentRepository()
        self._alert_repo = alert_repo or AlertRepository()
        self._order_repo = order_repo or RawOrderRepository()
        self._customer_repo = customer_repo or CustomerRepository()

    async def _fetch_page(self, url: str, page: int = 1, limit: int = 100, extra_params: dict = None):
        headers = {
            "Authorization": f"Bearer {API_KEYS['instaxbot']['key']}",
            "Content-Type": "application/json"
        }
        params = {"page": page, "limit": limit}
        if extra_params:
            params.update(extra_params)
        parsed = httpx.URL(url)
        merged = dict(parsed.params)
        merged.update(params)

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(str(parsed.copy_with(params=None)), headers=headers, params=merged)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                print(f"[comment_service] Error fetching {url} page {page}: {e}")
                return None

    async def _fetch_all_paginated(self, url: str, max_pages: int = 10) -> list:
        all_items = []
        for page in range(1, max_pages + 1):
            data = await self._fetch_page(url, page=page, limit=100)
            if not data:
                break
            items = _extract_items(data)
            if not items:
                break
            all_items.extend(items)
            if len(items) < 100:
                break
        return all_items

    async def _match_customer_by_username(self, username: str) -> str:
        if not username:
            return ""
        row = await self._customer_repo.fetchrow(
            "SELECT customer_id FROM customers WHERE username ILIKE $1 AND username != '' LIMIT 1",
            username,
        )
        if row:
            return row["customer_id"]
        row = await self._customer_repo.fetchrow(
            "SELECT customer_id FROM customers WHERE username ILIKE $1 AND username != '' LIMIT 1",
            f"%{username}%",
        )
        return row["customer_id"] if row else ""

    def _extract_username(self, item: dict) -> str:
        username = item.get("username") or ""
        if not username:
            username = item.get("user", {}) if isinstance(item.get("user"), dict) else {}
            if isinstance(username, dict):
                username = username.get("username", username.get("handle", username.get("name", "")))
        if not username:
            username = item.get("from", "") or item.get("sender", "") or item.get("userName", "")
        return str(username) if username else ""

    async def _process_comment(self, item: dict, tenant_id: str = "", is_auto_negative: bool = False):
        text = item.get("text") or item.get("commentText") or item.get("message", item.get("triggerText", ""))
        username = self._extract_username(item)
        media_id = item.get("mediaId") or item.get("postId") or item.get("media_id", "")
        comment_id = item.get("commentId", "") or item.get("_id", "")
        item_id = item.get("id") or item.get("_id", "")
        triggered_rule = item.get("triggerText", "")

        if not text and not username:
            return None

        if is_auto_negative:
            sentiment = {"score": -1.0, "label": "negative", "is_negative": True}
            triggered_rule = "bad_command"
        else:
            sentiment = _analyze_sentiment(text)

        customer_id = await self._match_customer_by_username(username)

        inserted = await self._comment_repo.insert(
            customer_id=customer_id,
            tenant_id=tenant_id or item.get("tenantId", ""),
            media_id=media_id,
            username=username,
            text=text,
            sentiment_score=sentiment["score"],
            sentiment_label=sentiment["label"],
            is_negative=sentiment["is_negative"],
            triggered_rule=triggered_rule,
            comment_id=comment_id,
        )
        if inserted is None:
            return None

        is_bad = is_auto_negative
        if sentiment["is_negative"]:
            alert_type = "negative_comment"
            alert_message = f"Negative comment from @{username}: '{text[:100]}'"
            if is_bad:
                alert_type = "bad_command"
                alert_message = f"Bad command detected from @{username}: '{text[:100]}'"
            exists = await self._alert_repo.exists_by_message_pattern(f"%@{username}%")
            if not exists:
                await self._alert_repo.insert(
                    alert_type=alert_type,
                    message=alert_message,
                    severity="warning",
                    source="instagram",
                )

        return {
            "id": item_id,
            "username": username,
            "sentiment": sentiment["label"],
            "is_negative": sentiment["is_negative"],
            "is_bad_command": is_bad,
        }

    async def fetch_and_store(self) -> dict:
        results = {"comments": [], "bad_commands": []}

        comments = await self._fetch_all_paginated(COMMENTS_URL)
        for item in comments:
            r = await self._process_comment(item)
            if r:
                results["comments"].append(r)

        bad = await self._fetch_all_paginated(BAD_COMMANDS_URL)
        for item in bad:
            r = await self._process_comment(item, is_auto_negative=True)
            if r:
                results["bad_commands"].append(r)

        await cache_manager.invalidate_prefix("cust:list")
        await cache_manager.invalidate("dash:stats")
        return {
            "comments_fetched": len(results["comments"]),
            "bad_fetched": len(results["bad_commands"]),
            "negative_count": sum(1 for r in results["comments"] + results["bad_commands"] if r["is_negative"]),
        }

    async def get_bad_comments(self, customer_id: str) -> list:
        return await self._comment_repo.get_bad_by_customer_id(customer_id)

    async def get_bad_comment_count(self, customer_id: str) -> int:
        return await self._comment_repo.count_bad_by_customer_id(customer_id)

    async def analyze_and_store(self, tenant_id: str = "") -> dict:
        return await self.fetch_and_store()

    async def get_tenant_ids(self) -> list:
        ids = await self._order_repo.get_distinct_tenant_ids()
        if not ids:
            ids = ["5573c0ef-f0b0-4477-8681-c50e97a48280"]
        return ids
