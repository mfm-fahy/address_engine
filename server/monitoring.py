import json
import logging
import os
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Optional

_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def _configure_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":%(message)s}',
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        ))
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, _LOG_LEVEL, logging.INFO))
        logger.propagate = False
    return logger


class MetricsCollector:
    def __init__(self):
        self._counters: dict[str, int] = {}
        self._timings: dict[str, list[float]] = {}
        self._start_time = time.monotonic()

    def increment(self, metric: str, value: int = 1):
        self._counters[metric] = self._counters.get(metric, 0) + value

    def record_timing(self, metric: str, duration_ms: float):
        if metric not in self._timings:
            self._timings[metric] = []
        self._timings[metric].append(duration_ms)
        if len(self._timings[metric]) > 1000:
            self._timings[metric] = self._timings[metric][-500:]

    def snapshot(self) -> dict:
        uptime_seconds = time.monotonic() - self._start_time
        result = {
            "uptime_seconds": round(uptime_seconds, 2),
            "counters": dict(self._counters),
            "timings": {},
        }
        for name, values in self._timings.items():
            if values:
                result["timings"][name] = {
                    "count": len(values),
                    "avg_ms": round(sum(values) / len(values), 2),
                    "max_ms": round(max(values), 2),
                    "min_ms": round(min(values), 2),
                }
        return result


metrics = MetricsCollector()


def timed(metric_name: str):
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            t0 = time.monotonic()
            try:
                return await fn(*args, **kwargs)
            finally:
                elapsed = (time.monotonic() - t0) * 1000
                metrics.record_timing(metric_name, elapsed)

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            t0 = time.monotonic()
            try:
                return fn(*args, **kwargs)
            finally:
                elapsed = (time.monotonic() - t0) * 1000
                metrics.record_timing(metric_name, elapsed)

        if hasattr(fn, "__code__") and fn.__code__.co_flags & 0x80:
            return async_wrapper
        return sync_wrapper
    return decorator


def log_event(logger_name: str, event: str, details: Optional[dict] = None):
    logger = _configure_logger(logger_name)
    record = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat()}
    if details:
        safe = {k: v for k, v in details.items() if k.lower() not in ("password", "secret", "token", "key", "authorization")}
        record["details"] = safe
    logger.info(json.dumps(record))


def log_error(logger_name: str, event: str, error: str, details: Optional[dict] = None):
    logger = _configure_logger(logger_name)
    record = {"event": event, "error": error, "timestamp": datetime.now(timezone.utc).isoformat()}
    if details:
        safe = {k: v for k, v in details.items() if k.lower() not in ("password", "secret", "token", "key", "authorization")}
        record["details"] = safe
    logger.error(json.dumps(record))
