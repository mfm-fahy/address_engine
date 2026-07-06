from repositories.customer_repo import CustomerRepository
from repositories.dashboard_repo import DashboardRepository
from services.cache_manager import cache_manager
from config import settings


class DashboardService:
    def __init__(self, repo=None, customer_repo=None):
        self._repo = repo or DashboardRepository()
        self._customer_repo = customer_repo or CustomerRepository()

    async def get_stats(self) -> dict:
        return await cache_manager.get_or_compute(
            "dash:stats",
            settings.DASHBOARD_TTL,
            self._compute_stats,
        )

    async def _compute_stats(self) -> dict:
        raw = await self._repo.get_stats()
        sources = await self._repo.get_source_breakdown()
        pending = await self._customer_repo.get_needs_analysis_count()
        rec_counts = await self._get_rec_counts()
        return {
            "total_customers": raw["total"],
            "total_orders": raw["total_orders"],
            "total_bills": raw["total_bills"],
            "total_revenue": float(raw["total_revenue"]),
            "avg_revenue_per_customer": round(float(raw["avg_revenue"]), 2),
            "total_comments": raw["total_comments"],
            "pending_analysis": pending,
            "recommendations": rec_counts,
            "by_source": {r["src"]: r["cnt"] for r in sources},
        }

    async def _get_rec_counts(self) -> dict:
        from repositories.recommendation_repo import RecommendationRepository
        counts = await RecommendationRepository().count_by_priority()
        result = {"total": 0}
        for row in counts:
            result[row["priority"]] = row["cnt"]
            result["total"] += row["cnt"]
        return result

    async def get_summary(self) -> dict:
        return await cache_manager.get_or_compute(
            "dash:summary",
            settings.DASHBOARD_TTL,
            self._compute_summary,
        )

    async def _compute_summary(self) -> dict:
        base = await self._repo.get_detailed_summary()
        growth = await self._repo.get_customer_growth(12)
        trends = await self._repo.get_revenue_trends(12)
        top_customers = await self._repo.get_top_customers(10)
        top_products = await self._repo.get_top_products(10)
        churn = await self._repo.get_churn_risk_summary()
        activities = await self._repo.get_recent_activities(10)
        rec_counts = await self._get_rec_counts()
        sources = await self._repo.get_source_breakdown()
        return {
            "overview": {
                "total_customers": base["total_customers"],
                "total_orders": base["total_orders"],
                "total_revenue": float(base["total_revenue"]),
                "avg_revenue_per_customer": round(float(base["avg_revenue_per_customer"]), 2),
                "total_comments": base["total_comments"],
                "vip_customers": base["vip_customers"],
                "active_customers": base["active_customers"],
                "inactive_customers": base["inactive_customers"],
                "pending_analysis": base["pending_analysis"],
                "multi_source_customers": base["multi_source_customers"],
            },
            "recommendations": rec_counts,
            "by_source": {r["src"]: r["cnt"] for r in sources},
            "customer_growth": growth,
            "revenue_trends": trends,
            "top_customers": top_customers,
            "top_products": top_products,
            "churn_risk": churn,
            "recent_activities": activities,
        }

    async def get_customer_growth(self, limit: int = 12) -> list[dict]:
        return await cache_manager.get_or_compute(
            f"dash:growth:{limit}",
            settings.DASHBOARD_TTL,
            lambda: self._repo.get_customer_growth(limit),
        )

    async def get_revenue_trends(self, limit: int = 12) -> list[dict]:
        return await cache_manager.get_or_compute(
            f"dash:revenue:{limit}",
            settings.DASHBOARD_TTL,
            lambda: self._repo.get_revenue_trends(limit),
        )

    async def get_top_customers(self, limit: int = 10) -> list[dict]:
        return await cache_manager.get_or_compute(
            f"dash:top-customers:{limit}",
            settings.DASHBOARD_TTL,
            lambda: self._repo.get_top_customers(limit),
        )

    async def get_top_products(self, limit: int = 10) -> list[dict]:
        return await cache_manager.get_or_compute(
            f"dash:top-products:{limit}",
            settings.DASHBOARD_TTL,
            lambda: self._repo.get_top_products(limit),
        )

    async def get_churn_risk_summary(self) -> dict:
        return await cache_manager.get_or_compute(
            "dash:churn-risk",
            settings.DASHBOARD_TTL,
            self._repo.get_churn_risk_summary,
        )

    async def get_recent_activities(self, limit: int = 10) -> list[dict]:
        return await cache_manager.get_or_compute(
            f"dash:activities:{limit}",
            settings.DASHBOARD_TTL,
            lambda: self._repo.get_recent_activities(limit),
        )

    async def invalidate_cache(self) -> None:
        await cache_manager.invalidate("dash:stats")
        await cache_manager.invalidate("dash:summary")
