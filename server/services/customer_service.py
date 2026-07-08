import hashlib
from typing import Optional

from repositories.customer_repo import CustomerRepository
from repositories.dashboard_repo import DashboardRepository
from services.cache_manager import cache_manager
from config import settings


class CustomerService:
    def __init__(self, repo=None):
        self._repo = repo or CustomerRepository()
        self._dash_repo = DashboardRepository()

    async def get_all(self) -> list[dict]:
        return await cache_manager.get_or_compute(
            "cust:list",
            settings.CUSTOMER_LIST_TTL,
            self._repo.get_all,
        )

    async def get_by_id(self, customer_id: str):
        return await cache_manager.get_or_compute(
            f"cust:id:{customer_id}",
            settings.CUSTOMER_PROFILE_TTL,
            lambda: self._repo.get_by_id(customer_id),
        )

    async def search(self, query: str) -> list[dict]:
        q_hash = hashlib.md5(query.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
        return await cache_manager.get_or_compute(
            f"cust:search:{q_hash}",
            settings.SEARCH_TTL,
            lambda: self._repo.search(query),
        )

    async def count_all(self) -> int:
        return await self._repo.count_all()

    async def get_training_data(self) -> list[dict]:
        return await self._repo.get_all_training()

    async def get_pending_analysis_count(self) -> int:
        return await self._repo.get_needs_analysis_count()

    async def get_all_paginated(
        self,
        limit: int = 50,
        offset: int = 0,
        sort: str = "last_activity",
        order: str = "DESC",
        search: str = "",
    ) -> tuple[list[dict], int]:
        total = await self._dash_repo.count_customers_filtered(search)
        items = await self._dash_repo.get_paginated_customers(
            limit=limit, offset=offset,
            sort=sort, order=order, search=search,
        )
        return items, total

    async def get_profile(self, customer_id: str) -> Optional[dict]:
        return await cache_manager.get_or_compute(
            f"cust:profile:{customer_id}",
            settings.CUSTOMER_PROFILE_TTL,
            lambda: self._repo.get_profile(customer_id),
        )

    async def get_timeline(self, customer_id: str) -> list[dict]:
        return await self._repo.get_timeline(customer_id)

    async def get_analytics(self, customer_id: str) -> Optional[dict]:
        return await cache_manager.get_or_compute(
            f"cust:analytics:{customer_id}",
            settings.CUSTOMER_PROFILE_TTL,
            lambda: self._repo.get_analytics(customer_id),
        )

    async def get_form_data(self, phone: str) -> Optional[dict]:
        customer = await self._repo.get_by_id(phone)
        if not customer:
            return None
        return {
            "customer_id": customer.get("customer_id"),
            "phone": customer.get("phone"),
            "name": customer.get("name", ""),
            "email": customer.get("email", ""),
            "username": customer.get("username", ""),
            "address": customer.get("address", {}),
            "stores": customer.get("stores", []),
        }

    async def invalidate_cache(self, customer_id: str = None) -> None:
        await cache_manager.invalidate_prefix("cust:list")
        if customer_id:
            await cache_manager.invalidate(f"cust:id:{customer_id}")
            await cache_manager.invalidate(f"cust:profile:{customer_id}")
            await cache_manager.invalidate(f"cust:analytics:{customer_id}")
