import hashlib
from typing import Optional

from repositories.customer_repo import CustomerRepository
from repositories.recommendation_repo import RecommendationRepository
from services.feature_engine import FeatureEngine
from services.rule_engine import RuleEngine
from services.profile_summarizer import get_profile_summarizer
from services.cache_manager import cache_manager
from config import settings


class RecommendationService:
    def __init__(self, customer_repo=None, rec_repo=None, feature_engine=None, rule_engine=None):
        self._customer_repo = customer_repo or CustomerRepository()
        self._rec_repo = rec_repo or RecommendationRepository()
        self._feature_engine = feature_engine or FeatureEngine()
        self._rule_engine = rule_engine or RuleEngine()

    async def process_customer(self, customer_id: str) -> dict:
        """Run the full recommendation pipeline for one customer."""
        customer = await self._customer_repo.get_by_id_raw(customer_id)
        if not customer:
            return {"customer_id": customer_id, "error": "not found"}

        features = await self._feature_engine.compute_and_store(customer)
        try:
            summarizer = get_profile_summarizer()
            await summarizer.regenerate_summary(customer, customer_id)
        except Exception as e:
            print(f"[rec-worker] Summary regeneration failed for {customer_id}: {e}")

        rule_recs = self._rule_engine.evaluate(features, customer)

        stored_count = 0
        for rec in rule_recs:
            await self._rec_repo.upsert(rec)
            stored_count += 1

        await self._customer_repo.mark_analyzed(customer_id)
        await cache_manager.invalidate_prefix(f"cust:id:{customer_id}")
        await cache_manager.invalidate_prefix("rec:")
        await cache_manager.invalidate("dash:stats")

        return {
            "customer_id": customer_id,
            "features_version": features.get("feature_version", 1),
            "rule_recommendations": len(rule_recs),
            "total_stored": stored_count,
        }

    async def get_all(self, status: str = "active", priority: str = None, limit: int = 50) -> list[dict]:
        return await self._rec_repo.get_all(status=status, priority=priority, limit=limit)

    async def get_all_paginated(
        self,
        status: str = "active",
        priority: Optional[str] = None,
        search: str = "",
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "DESC",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        category: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        cache_key = (
            f"rec:list:{status}:{priority}:{search}:{limit}:{offset}:"
            f"{sort_by}:{sort_order}:{date_from}:{date_to}:{category}"
        )
        cache_key_short = hashlib.md5(cache_key.encode(), usedforsecurity=False).hexdigest()

        async def _fetch():
            items = await self._rec_repo.get_all_paginated(
                status=status, priority=priority, search=search,
                limit=limit, offset=offset, sort_by=sort_by,
                sort_order=sort_order, date_from=date_from,
                date_to=date_to, category=category,
            )
            total = await self._rec_repo.count_all_filtered(
                status=status, priority=priority, search=search,
                date_from=date_from, date_to=date_to, category=category,
            )
            return items, total

        return await cache_manager.get_or_compute(
            f"rec:paginated:{cache_key_short}",
            settings.RECOMMENDATION_TTL,
            _fetch,
        )

    async def get_high_priority(self, limit: int = 20) -> list[dict]:
        return await self._rec_repo.get_high_priority(limit=limit)

    async def get_by_customer_id(self, customer_id: str, status: str = "active") -> list[dict]:
        return await self._rec_repo.get_by_customer_id(customer_id, status=status)

    async def deactivate_expired(self) -> int:
        return await self._rec_repo.deactivate_expired()

    async def get_pending_count(self) -> int:
        return await self._customer_repo.get_needs_analysis_count()

    async def process_batch(self, batch_size: int = 10) -> dict:
        pending = await self._customer_repo.get_pending_batch(limit=batch_size)
        if not pending:
            return {"processed": 0, "skipped": 0, "errors": 0, "total_customers": 0}
        processed = 0
        errors = 0
        results = []
        for cid in pending:
            try:
                result = await self.process_customer(cid)
                results.append(result)
                processed += 1
            except Exception as e:
                print(f"[rec-worker] Error processing {cid}: {e}")
                errors += 1
        return {
            "processed": processed,
            "errors": errors,
            "results": results,
        }
