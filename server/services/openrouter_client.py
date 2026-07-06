import json
from datetime import datetime, timedelta

import httpx

from config.settings import OPENROUTER_API_KEY, OPENROUTER_MODEL


_AI_RECOMMENDATION_PROMPT = """You are a business recommendation engine for a retail Customer 360 platform.

Given a customer's feature data (JSON below), generate exactly ONE recommendation if you see a clear business opportunity.

Rules:
- Return ONLY valid JSON, no markdown, no code fences.
- If no good recommendation applies, return {"recommendation": null}.
- Do NOT suggest recommendations already covered by basic business rules (VIP, Churn, Dormant, Return Risk, Payment Risk, Upsell, Cross-sell, Repeat Buyer, Loyal, New Customer, Seasonal).
- Focus on personalized or nuanced insights that a rule engine would miss.

Response format:
{
  "recommendation": {
    "title": "Short title (5-10 words)",
    "description": "Why this recommendation applies to this specific customer (1-2 sentences)",
    "priority": "high" | "medium" | "low",
    "confidence": 0.0-1.0,
    "category": "Personalization" | "Engagement" | "Product" | "Retention" | "Growth",
    "recommended_action": "What the business should do (1 sentence)",
    "expected_business_impact": "Expected outcome (1 sentence)",
    "expires_in_days": 30
  }
}"""


async def generate_ai_recommendation(features: dict) -> dict | None:
    if not OPENROUTER_API_KEY:
        return None

    compact = _build_compact_input(features)
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": _AI_RECOMMENDATION_PROMPT},
            {"role": "user", "content": json.dumps(compact, indent=2)},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 500,
        "temperature": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content)
    except Exception as e:
        print(f"[openrouter] Error: {e}")
        return None

    rec = parsed.get("recommendation")
    if not rec:
        return None

    errors = _validate_ai_response(rec)
    if errors:
        print(f"[openrouter] Validation errors: {errors}")
        return None

    return rec


def _build_compact_input(features: dict) -> dict:
    return {
        "customer_id": features.get("customer_id", ""),
        "segment": features.get("segment", "unknown"),
        "lifetime_value": features.get("lifetime_value", 0),
        "orders": features.get("total_orders", 0),
        "average_order": features.get("average_order_value", 0),
        "return_rate": features.get("return_rate", 0),
        "loyalty_score": features.get("loyalty_score", 0),
        "churn_probability": features.get("churn_probability", 0),
        "days_since_last_activity": features.get("days_since_last_activity", 999),
        "sources": features.get("sources", []),
        "favorite_products": features.get("favorite_products", []),
        "payment_health": features.get("payment_health_score", 100),
    }


def _validate_ai_response(rec: dict) -> list[str]:
    errors = []
    if not isinstance(rec.get("title"), str) or len(rec["title"]) < 3:
        errors.append("title missing or too short")
    if not isinstance(rec.get("description"), str) or len(rec["description"]) < 10:
        errors.append("description missing or too short")
    if rec.get("priority") not in ("high", "medium", "low"):
        errors.append("priority must be high/medium/low")
    confidence = rec.get("confidence", 0)
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        errors.append("confidence must be 0.0-1.0")
    return errors


def build_ai_recommendation_dict(rec: dict, customer_id: str, features: dict) -> dict:
    now = datetime.utcnow()
    return {
        "customer_id": customer_id,
        "recommendation_type": rec.get("category", "ai_generated").lower().replace(" ", "_"),
        "title": rec["title"],
        "description": rec["description"],
        "priority": rec["priority"],
        "confidence": rec.get("confidence", 0.5),
        "status": "active",
        "recommended_action": rec.get("recommended_action", ""),
        "expected_business_impact": rec.get("expected_business_impact", ""),
        "feature_snapshot": features,
        "metadata": {"generated_by": "openrouter", "model": OPENROUTER_MODEL},
        "source_model": f"openrouter:{OPENROUTER_MODEL}",
        "expires_at": now + timedelta(days=rec.get("expires_in_days", 30)),
    }
