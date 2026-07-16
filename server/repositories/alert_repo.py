from datetime import datetime
from typing import Any, Optional

from repositories.base import BaseRepository


class AlertRepository(BaseRepository):
    async def get_all(self, limit: int = 10000) -> list[dict]:
        rows = await self.fetch(
            "SELECT * FROM alerts ORDER BY created_at DESC LIMIT $1", limit
        )
        result = []
        for r in rows:
            d = dict(r)
            d["_id"] = str(d.pop("id"))
            result.append(d)
        return result

    async def get_all_paginated(
        self,
        limit: int = 50,
        offset: int = 0,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
    ) -> list[dict]:
        clauses = ["TRUE"]
        params: list[Any] = []
        idx = 1
        if severity:
            clauses.append(f"severity = ${idx}")
            params.append(severity)
            idx += 1
        if alert_type:
            clauses.append(f"type = ${idx}")
            params.append(alert_type)
            idx += 1
        where = " AND ".join(clauses)
        rows = await self.fetch(
            f"""SELECT * FROM alerts
                WHERE {where}
                ORDER BY created_at DESC
                LIMIT ${idx} OFFSET ${idx + 1}""",
            *params, limit, offset,
        )
        result = []
        for r in rows:
            d = dict(r)
            d["_id"] = str(d.pop("id"))
            result.append(d)
        return result

    async def count_all_filtered(
        self,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
    ) -> int:
        clauses = ["TRUE"]
        params: list[Any] = []
        idx = 1
        if severity:
            clauses.append(f"severity = ${idx}")
            params.append(severity)
            idx += 1
        if alert_type:
            clauses.append(f"type = ${idx}")
            params.append(alert_type)
            idx += 1
        where = " AND ".join(clauses)
        return await self.fetchval(
            f"SELECT COUNT(*) FROM alerts WHERE {where}",
            *params,
        )

    async def exists_by_message_pattern(self, pattern: str) -> bool:
        val = await self.fetchval(
            """SELECT 1 FROM alerts
               WHERE type IN ('negative_comment', 'bad_command')
                 AND message LIKE $1
                 AND source = 'instagram'
               LIMIT 1""",
            pattern,
        )
        return val is not None

    async def insert(self, alert_type: str, message: str, severity: str = "warning",
                     source: str = "instagram", customer_id: str = "") -> str:
        return await self.execute(
            """INSERT INTO alerts (type, message, severity, source, customer_id, created_at)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            alert_type,
            message,
            severity,
            source,
            customer_id or None,
            datetime.utcnow(),
        )
