import httpx
from datetime import datetime
from config.settings import API_KEYS, SENTIMENT_THRESHOLD
from config.postgres import get_pool

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    analyzer = SentimentIntensityAnalyzer()
except ImportError:
    analyzer = None


def analyze_sentiment(text: str) -> dict:
    if not text or not analyzer:
        return {"score": 0.0, "label": "neutral", "is_negative": False}
    scores = analyzer.polarity_scores(text)
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


async def fetch_comment_rules(tenant_id: str, page: int = 1, limit: int = 100):
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


async def fetch_rules_by_media(tenant_id: str, page: int = 1, limit: int = 50):
    headers = {
        "Authorization": f"Bearer {API_KEYS['instaxbot']['key']}",
        "Content-Type": "application/json"
    }
    params = {"tenentId": tenant_id, "page": page, "limit": limit}
    url = "https://app.instaxbot.com/api/commentAutomationroute/rules-by-media"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error fetching rules-by-media for tenant {tenant_id}: {e}")
            return None


async def analyze_and_store_comments(tenant_id: str):
    rules_data = await fetch_comment_rules(tenant_id, page=1, limit=1000)

    if not rules_data:
        return {"error": "No rules fetched"}

    rules = []
    if isinstance(rules_data, dict) and "data" in rules_data:
        data = rules_data["data"]
        if isinstance(data, list):
            rules = data
        elif isinstance(data, dict):
            rules = data.get("rules", data.get("items", [data]))

    pool = get_pool()
    results = []

    async with pool.acquire() as conn:
        for rule in rules:
            trigger_text = rule.get("triggerText", "")
            comment_text = rule.get("commentReply", rule.get("replyText", ""))
            username = rule.get("username", "")

            sentiment = analyze_sentiment(comment_text or trigger_text)

            await conn.execute("""
                INSERT INTO comments (
                    tenant_id, media_id, username, text,
                    sentiment_score, sentiment_label, is_negative,
                    triggered_rule, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
                tenant_id,
                rule.get("mediaId", ""),
                username,
                comment_text or trigger_text,
                sentiment["score"],
                sentiment["label"],
                sentiment["is_negative"],
                trigger_text,
                datetime.utcnow()
            )

            if sentiment["is_negative"]:
                exists = await conn.fetchval("""
                    SELECT 1 FROM alerts
                    WHERE type = 'negative_comment'
                      AND message LIKE $1
                      AND source = 'instagram'
                    LIMIT 1
                """, f"%@{username}%")

                if not exists:
                    await conn.execute("""
                        INSERT INTO alerts (type, message, severity, source, created_at)
                        VALUES ($1, $2, $3, $4, $5)
                    """,
                        "negative_comment",
                        f"Negative comment from @{username}: '{(comment_text or trigger_text)[:100]}'",
                        "warning",
                        "instagram",
                        datetime.utcnow()
                    )

            results.append({
                "trigger_text": trigger_text,
                "sentiment": sentiment["label"],
                "is_negative": sentiment["is_negative"]
            })

    return {"analyzed": len(results), "negative_count": sum(1 for r in results if r["is_negative"])}


async def get_tenant_ids() -> list:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT raw_data->>'tenantId' AS tid FROM raw_orders WHERE raw_data->>'tenantId' IS NOT NULL")
        ids = [r["tid"] for r in rows if r["tid"]]
    if not ids:
        ids = ["5573c0ef-f0b0-4477-8681-c50e97a48280"]
    return ids
