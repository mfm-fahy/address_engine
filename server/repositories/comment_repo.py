from datetime import datetime
from typing import Any, Optional

from repositories.base import BaseRepository


class CommentRepository(BaseRepository):
    async def insert(self, tenant_id: str, media_id: str, username: str, text: str,
                     sentiment_score: float, sentiment_label: str, is_negative: bool,
                     triggered_rule: str = "", customer_id: str = "", comment_id: str = "") -> str:
        if comment_id:
            exists = await self.fetchval(
                "SELECT 1 FROM comments WHERE comment_id = $1 LIMIT 1", comment_id
            )
            if exists:
                return None
        return await self.execute(
            """INSERT INTO comments (
                   customer_id, tenant_id, media_id, username, text,
                   sentiment_score, sentiment_label, is_negative,
                   triggered_rule, comment_id, created_at
               ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
            customer_id or None,
            tenant_id,
            media_id,
            username,
            text,
            sentiment_score,
            sentiment_label,
            is_negative,
            triggered_rule,
            comment_id or None,
            datetime.utcnow(),
        )

    async def get_by_customer_id(self, customer_id: str, limit: int = 50) -> list[dict]:
        rows = await self.fetch(
            """SELECT id, tenant_id, media_id, username, text,
                      sentiment_score, sentiment_label, is_negative,
                      triggered_rule, created_at
               FROM comments
               WHERE customer_id = $1
               ORDER BY created_at DESC
               LIMIT $2""",
            customer_id, limit,
        )
        return [dict(r) for r in rows]

    async def count_by_customer_id(self, customer_id: str) -> int:
        return await self.fetchval(
            "SELECT COUNT(*) FROM comments WHERE customer_id = $1",
            customer_id,
        )

    async def get_by_username(self, username: str, limit: int = 50) -> list[dict]:
        rows = await self.fetch(
            """SELECT id, customer_id, tenant_id, media_id, username, text,
                      sentiment_score, sentiment_label, is_negative,
                      triggered_rule, created_at
               FROM comments
               WHERE username ILIKE $1
               ORDER BY created_at DESC
               LIMIT $2""",
            username, limit,
        )
        return [dict(r) for r in rows]

    async def get_bad_by_customer_id(self, customer_id: str, limit: int = 50) -> list[dict]:
        rows = await self.fetch(
            """SELECT id, tenant_id, media_id, username, text,
                      sentiment_score, sentiment_label, is_negative,
                      triggered_rule, created_at
               FROM comments
               WHERE customer_id = $1 AND triggered_rule = 'bad_command'
               ORDER BY created_at DESC
               LIMIT $2""",
            customer_id, limit,
        )
        return [dict(r) for r in rows]

    async def count_bad_by_customer_id(self, customer_id: str) -> int:
        return await self.fetchval(
            "SELECT COUNT(*) FROM comments WHERE customer_id = $1 AND triggered_rule = 'bad_command'",
            customer_id,
        )
