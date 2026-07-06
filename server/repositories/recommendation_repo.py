import json
from datetime import datetime, timedelta
from typing import Optional

from repositories.base import BaseRepository


class RecommendationRepository(BaseRepository):
    async def upsert(self, rec: dict) -> None:
        await self.execute(
            """INSERT INTO recommendations (
                   customer_id, recommendation_type, title, description, confidence,
                   priority, status, metadata, feature_snapshot, expires_at,
                   recommended_action, expected_business_impact, source_model,
                   created_at, updated_at
               ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10,
                         $11, $12, $13, $14, $15)
               ON CONFLICT DO NOTHING""",
            rec["customer_id"],
            rec.get("recommendation_type", ""),
            rec.get("title", ""),
            rec.get("description", ""),
            rec.get("confidence", 0),
            rec.get("priority", "normal"),
            rec.get("status", "active"),
            json.dumps(rec.get("metadata", {}), default=str),
            json.dumps(rec.get("feature_snapshot", {}), default=str),
            rec.get("expires_at"),
            rec.get("recommended_action", ""),
            rec.get("expected_business_impact", ""),
            rec.get("source_model", "rule_engine"),
            datetime.utcnow(),
            datetime.utcnow(),
        )

    async def get_by_customer_id(self, customer_id: str, status: str = "active") -> list[dict]:
        rows = await self.fetch(
            """SELECT * FROM recommendations
               WHERE customer_id = $1 AND status = $2
               ORDER BY priority DESC, confidence DESC""",
            customer_id, status,
        )
        return [dict(r) for r in rows]

    async def get_all(self, status: str = "active", priority: str = None, limit: int = 50) -> list[dict]:
        if priority:
            rows = await self.fetch(
                """SELECT * FROM recommendations
                   WHERE status = $1 AND priority = $2
                   ORDER BY confidence DESC, created_at DESC
                   LIMIT $3""",
                status, priority, limit,
            )
        else:
            rows = await self.fetch(
                """SELECT * FROM recommendations
                   WHERE status = $1
                   ORDER BY priority DESC, confidence DESC, created_at DESC
                   LIMIT $2""",
                status, limit,
            )
        return [dict(r) for r in rows]

    async def get_high_priority(self, limit: int = 20) -> list[dict]:
        return await self.get_all(status="active", priority="high", limit=limit)

    async def deactivate_expired(self) -> int:
        result = await self.execute(
            """UPDATE recommendations SET status = 'expired', updated_at = $1
               WHERE status = 'active' AND expires_at IS NOT NULL AND expires_at < $1""",
            datetime.utcnow(),
        )
        parts = result.split()
        return int(parts[-1]) if parts else 0

    async def count_by_priority(self, status: str = "active") -> list[dict]:
        rows = await self.fetch(
            """SELECT priority, COUNT(*) AS cnt
               FROM recommendations WHERE status = $1
               GROUP BY priority ORDER BY priority""",
            status,
        )
        return [dict(r) for r in rows]

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
    ) -> list[dict]:
        allowed_sort = {"created_at", "confidence", "priority", "title", "updated_at"}
        col = sort_by if sort_by in allowed_sort else "created_at"
        dir = "ASC" if sort_order.upper() == "ASC" else "DESC"
        clauses = ["r.status = $1"]
        params = [status]
        idx = 2
        if priority:
            clauses.append(f"r.priority = ${idx}")
            params.append(priority)
            idx += 1
        if search:
            clauses.append(f"(r.title ILIKE ${idx} OR r.description ILIKE ${idx})")
            params.append(f"%{search}%")
            idx += 1
        if date_from:
            clauses.append(f"r.created_at >= ${idx}::TIMESTAMPTZ")
            params.append(date_from)
            idx += 1
        if date_to:
            clauses.append(f"r.created_at <= ${idx}::TIMESTAMPTZ")
            params.append(date_to)
            idx += 1
        if category:
            clauses.append(f"r.recommendation_type = ${idx}")
            params.append(category)
            idx += 1
        params.extend([limit, offset])
        where = " AND ".join(clauses)
        rows = await self.fetch(
            f"""SELECT r.*, c.name AS customer_name, c.phone AS customer_phone
                FROM recommendations r
                LEFT JOIN customers c ON c.customer_id = r.customer_id
                WHERE {where}
                ORDER BY r.{col} {dir} NULLS LAST
                LIMIT ${idx} OFFSET ${idx + 1}""",
            *params,
        )
        return [dict(r) for r in rows]

    async def count_all_filtered(
        self,
        status: str = "active",
        priority: Optional[str] = None,
        search: str = "",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        category: Optional[str] = None,
    ) -> int:
        clauses = ["status = $1"]
        params = [status]
        idx = 2
        if priority:
            clauses.append(f"priority = ${idx}")
            params.append(priority)
            idx += 1
        if search:
            clauses.append(f"(title ILIKE ${idx} OR description ILIKE ${idx})")
            params.append(f"%{search}%")
            idx += 1
        if date_from:
            clauses.append(f"created_at >= ${idx}::TIMESTAMPTZ")
            params.append(date_from)
            idx += 1
        if date_to:
            clauses.append(f"created_at <= ${idx}::TIMESTAMPTZ")
            params.append(date_to)
            idx += 1
        if category:
            clauses.append(f"recommendation_type = ${idx}")
            params.append(category)
            idx += 1
        where = " AND ".join(clauses)
        return await self.fetchval(
            f"SELECT COUNT(*) FROM recommendations WHERE {where}",
            *params,
        )
