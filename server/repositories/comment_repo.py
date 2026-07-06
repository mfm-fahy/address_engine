from datetime import datetime
from typing import Any

from repositories.base import BaseRepository


class CommentRepository(BaseRepository):
    async def insert(self, tenant_id: str, media_id: str, username: str, text: str,
                     sentiment_score: float, sentiment_label: str, is_negative: bool,
                     triggered_rule: str) -> str:
        return await self.execute(
            """INSERT INTO comments (
                   tenant_id, media_id, username, text,
                   sentiment_score, sentiment_label, is_negative,
                   triggered_rule, created_at
               ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
            tenant_id,
            media_id,
            username,
            text,
            sentiment_score,
            sentiment_label,
            is_negative,
            triggered_rule,
            datetime.utcnow(),
        )
