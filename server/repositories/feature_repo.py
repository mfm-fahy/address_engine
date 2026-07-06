import json
from datetime import datetime
from typing import Optional

from repositories.base import BaseRepository


class FeatureRepository(BaseRepository):
    async def upsert(self, customer_id: str, features: dict) -> None:
        await self.execute(
            """INSERT INTO customer_features (
                   customer_id, feature_version, lifetime_value, purchase_frequency,
                   average_order_value, churn_probability, loyalty_score, return_rate,
                   payment_health_score, days_since_last_activity,
                   total_orders_30d, total_orders_90d, total_spent_30d, total_spent_90d,
                   features_snapshot, computed_at, updated_at
               ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15::jsonb, $16, $17)
               ON CONFLICT (customer_id) DO UPDATE SET
                   feature_version = EXCLUDED.feature_version,
                   lifetime_value = EXCLUDED.lifetime_value,
                   purchase_frequency = EXCLUDED.purchase_frequency,
                   average_order_value = EXCLUDED.average_order_value,
                   churn_probability = EXCLUDED.churn_probability,
                   loyalty_score = EXCLUDED.loyalty_score,
                   return_rate = EXCLUDED.return_rate,
                   payment_health_score = EXCLUDED.payment_health_score,
                   days_since_last_activity = EXCLUDED.days_since_last_activity,
                   total_orders_30d = EXCLUDED.total_orders_30d,
                   total_orders_90d = EXCLUDED.total_orders_90d,
                   total_spent_30d = EXCLUDED.total_spent_30d,
                   total_spent_90d = EXCLUDED.total_spent_90d,
                   features_snapshot = EXCLUDED.features_snapshot,
                   computed_at = EXCLUDED.computed_at,
                   updated_at = EXCLUDED.updated_at""",
            customer_id,
            features.get("feature_version", 1),
            features.get("lifetime_value", 0),
            features.get("purchase_frequency", 0),
            features.get("average_order_value", 0),
            features.get("churn_probability", 0),
            features.get("loyalty_score", 0),
            features.get("return_rate", 0),
            features.get("payment_health_score", 0),
            features.get("days_since_last_activity", 0),
            features.get("total_orders_30d", 0),
            features.get("total_orders_90d", 0),
            features.get("total_spent_30d", 0),
            features.get("total_spent_90d", 0),
            json.dumps(features, default=str),
            datetime.utcnow(),
            datetime.utcnow(),
        )

    async def get_by_customer_id(self, customer_id: str) -> Optional[dict]:
        row = await self.fetchrow(
            "SELECT * FROM customer_features WHERE customer_id = $1",
            customer_id,
        )
        return dict(row) if row else None
