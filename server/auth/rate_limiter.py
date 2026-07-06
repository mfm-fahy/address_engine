import os
import time
from collections import defaultdict
from typing import Optional

_RATE_LIMIT_ENABLED: bool = False
_RATE_LIMIT_REQUESTS: int = 100
_RATE_LIMIT_WINDOW: int = 60


def configure_rate_limiter(enabled: bool, requests: int = 100, window_seconds: int = 60):
    global _RATE_LIMIT_ENABLED, _RATE_LIMIT_REQUESTS, _RATE_LIMIT_WINDOW
    _RATE_LIMIT_ENABLED = enabled
    _RATE_LIMIT_REQUESTS = requests
    _RATE_LIMIT_WINDOW = window_seconds


class InMemoryRateLimiter:
    def __init__(self):
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        bucket = self._buckets[key]
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        if len(bucket) >= max_requests:
            return False
        bucket.append(now)
        return True

    def remaining(self, key: str, max_requests: int, window_seconds: int) -> int:
        now = time.monotonic()
        cutoff = now - window_seconds
        bucket = self._buckets[key]
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        return max(0, max_requests - len(bucket))

    def reset(self, key: str):
        self._buckets.pop(key, None)


_rate_limiter = InMemoryRateLimiter()


def get_rate_limiter() -> InMemoryRateLimiter:
    return _rate_limiter


def check_rate_limit(key: str) -> tuple[bool, int, int]:
    if not _RATE_LIMIT_ENABLED:
        return True, _RATE_LIMIT_REQUESTS, _RATE_LIMIT_WINDOW
    allowed = _rate_limiter.check(key, _RATE_LIMIT_REQUESTS, _RATE_LIMIT_WINDOW)
    remaining = _rate_limiter.remaining(key, _RATE_LIMIT_REQUESTS, _RATE_LIMIT_WINDOW)
    return allowed, remaining, _RATE_LIMIT_WINDOW
