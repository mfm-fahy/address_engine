from typing import Optional

from repositories.alert_repo import AlertRepository
from services.cache_manager import cache_manager
from config import settings


class AlertService:
    def __init__(self, repo=None):
        self._repo = repo or AlertRepository()

    async def get_all(self, limit: int = 100) -> list[dict]:
        return await cache_manager.get_or_compute(
            f"alerts:list:{limit}",
            settings.ALERTS_TTL,
            lambda: self._repo.get_all(limit=limit),
        )

    async def get_all_paginated(
        self,
        limit: int = 50,
        offset: int = 0,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        items = await self._repo.get_all_paginated(
            limit=limit, offset=offset,
            severity=severity, alert_type=alert_type,
        )
        total = await self._repo.count_all_filtered(
            severity=severity, alert_type=alert_type,
        )
        return items, total

    async def invalidate_cache(self) -> None:
        await cache_manager.invalidate_prefix("alerts:list:")
