import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("audit")


class AuditLogger:
    def __init__(self):
        self._handler = logging.StreamHandler()
        self._handler.setFormatter(logging.Formatter(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":%(message)s}',
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        ))
        logger.addHandler(self._handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    def log(
        self,
        event: str,
        username: str,
        ip_address: str = "",
        success: bool = True,
        details: Optional[dict] = None,
    ):
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "username": username,
            "ip_address": ip_address,
            "success": success,
        }
        if details:
            # Strip sensitive fields
            safe = {k: v for k, v in details.items() if k.lower() not in ("password", "secret", "token", "key")}
            record["details"] = safe
        logger.info(json.dumps(record))


audit_logger = AuditLogger()
