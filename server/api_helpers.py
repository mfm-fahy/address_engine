import time
from typing import Any, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from monitoring import log_event, log_error, metrics


_SLOW_REQUEST_MS = 500


def ok(data: Any, total: Optional[int] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> dict:
    result = {"success": True, "data": data}
    if total is not None:
        result["total"] = total
        pagination = {"limit": limit, "offset": offset, "total": total}
        result["pagination"] = pagination
    return result


def paginated(data: list, total: int, limit: int, offset: int) -> dict:
    return {
        "success": True,
        "data": data,
        "total": total,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
        },
    }


def error(detail: str, code: str = "error") -> dict:
    return {"success": False, "error": {"code": code, "detail": detail}}


def sanitize_error(detail: str) -> str:
    if "password" in detail.lower() or "secret" in detail.lower() or "token" in detail.lower() or "key" in detail.lower():
        return "An internal error occurred"
    return detail


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        t0 = time.monotonic()
        method = request.method
        path = request.url.path
        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - t0) * 1000
            metrics.increment("api.error")
            log_error("api", "unhandled_exception", type(exc).__name__, {"method": method, "path": path})
            metrics.record_timing(f"api.{method}.{path.replace('/', '_')}", elapsed_ms)
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": {"code": "internal_error", "detail": "Internal server error"}},
            )
        elapsed_ms = (time.monotonic() - t0) * 1000
        status = response.status_code
        metrics.increment(f"api.{status}")
        metrics.record_timing(f"api.{method}.{path.replace('/', '_')}", elapsed_ms)
        slow = ""
        if elapsed_ms > _SLOW_REQUEST_MS:
            slow = " SLOW"
            metrics.increment("api.slow")
        if elapsed_ms > 100 or status >= 400:
            level = "error" if status >= 500 else "warn" if status >= 400 else "info"
            if level == "error":
                log_error("api", "request", f"{status}", {"method": method, "path": path, "duration_ms": round(elapsed_ms, 2)})
            else:
                log_event("api", "request", {"method": method, "path": path, "status": status, "duration_ms": round(elapsed_ms, 2)})
        return response
