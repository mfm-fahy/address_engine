import os
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
import time
from typing import Optional

from config.database import connect_db, close_db
from config.redis import redis_client
from config.settings import AUTH_ENABLED, JWT_SECRET_KEY, JWT_ACCESS_TOKEN_EXPIRE_MINUTES, JWT_REFRESH_TOKEN_EXPIRE_DAYS, API_KEY
from services.cache_manager import cache_manager
from services.order_service import OrderService
from services.f3db_loader import F3DbLoader
from services.customer_profile_service import CustomerProfileService
from services.comment_service import CommentService
from services.customer_service import CustomerService
from services.alert_service import AlertService
from services.recommendation_service import RecommendationService
from services.dashboard_service import DashboardService
from services.profile_summarizer import get_profile_summarizer
from services.section_summarizer import get_section_summarizer
from c360_mcp.routes import router as mcp_router
from c360_mcp.handler import get_pool as mcp_get_pool, close_pool as mcp_close_pool
from ai.router import ai_router, business_router
from api_helpers import ok, paginated, error, LoggingMiddleware
from auth.jwt import configure_jwt
from auth.dependencies import configure_auth
from auth.rate_limiter import configure_rate_limiter
from auth.api_key import configure_api_key, verify_api_key
from auth.router import router as auth_router
from monitoring import metrics, log_event


FETCH_INTERVAL = 5
cycle = 0

_order_service = OrderService()
_profile_service = CustomerProfileService()
_comment_service = CommentService()
_customer_service = CustomerService()
_alert_service = AlertService()
_rec_service = RecommendationService()
_dashboard_service = DashboardService()


async def background_fetch_loop():
    global cycle
    while True:
        try:
            cycle += 1
            t0 = time.time()
            print(f"[scheduler] Cycle {cycle}: Fetching data...")

            fetch_result = await _order_service.fetch_and_store_all()
            fetch_elapsed = time.time() - t0
            print(f"[scheduler] Fetch done in {fetch_elapsed:.2f}s: {fetch_result}")

            pending = await _customer_service.get_pending_analysis_count()
            if pending:
                print(f"[scheduler] {pending} customer(s) pending analysis")

            if cycle % 2 == 0:
                t1 = time.time()
                print("[scheduler] Building profiles...")
                profile_result = await _profile_service.build_profiles()
                profile_elapsed = time.time() - t1
                print(f"[scheduler] Profiles done in {profile_elapsed:.2f}s: {profile_result}")

            if cycle % 6 == 0:
                t2 = time.time()
                print("[scheduler] Analyzing comments...")
                result = await _comment_service.fetch_and_store()
                comment_elapsed = time.time() - t2
                print(f"[scheduler] Comments done in {comment_elapsed:.2f}s: {result}")

            if cycle % 4 == 0:
                t3 = time.time()
                pending = await _rec_service.get_pending_count()
                if pending:
                    print(f"[scheduler] Processing {pending} customer(s) for recommendations...")
                    batch_result = await _rec_service.process_batch(batch_size=10)
                    rec_elapsed = time.time() - t3
                    print(f"[scheduler] Recommendations done in {rec_elapsed:.2f}s: {batch_result}")
                else:
                    print(f"[scheduler] No pending customers for recommendations")

            if cycle % 10 == 0:
                t4 = time.time()
                from services.profile_summarizer import get_profile_summarizer
                summarizer = get_profile_summarizer()
                summary_count = await summarizer.generate_for_all()
                summary_elapsed = time.time() - t4
                if summary_count:
                    print(f"[scheduler] Generated {summary_count} summary(ies) in {summary_elapsed:.2f}s")

            cycle_elapsed = time.time() - t0
            print(f"[scheduler] Cycle {cycle} complete in {cycle_elapsed:.2f}s")

            await asyncio.sleep(FETCH_INTERVAL)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[scheduler] Error: {e}")
            await asyncio.sleep(FETCH_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await redis_client.connect()
    try:
        await mcp_get_pool()
    except Exception:
        print("[mcp] PostgreSQL not available, MCP pool will be lazy")

    # Configure authentication
    secret_key = JWT_SECRET_KEY or os.urandom(32).hex()
    configure_jwt(secret_key, JWT_ACCESS_TOKEN_EXPIRE_MINUTES, JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    configure_auth(AUTH_ENABLED)
    # Configure rate limiting (default: 100 requests per 60s window)
    configure_rate_limiter(AUTH_ENABLED, requests=100, window_seconds=60)
    # Configure API key for external app auth
    configure_api_key(API_KEY)
    from auth.user_store import load_users
    load_users()

    task = asyncio.create_task(background_fetch_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await mcp_close_pool()
    await redis_client.close()
    await close_db()


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"] = "no-store"
    return response


app = FastAPI(title="Customer360 API", lifespan=lifespan)
app.include_router(mcp_router)
app.include_router(ai_router)
app.include_router(business_router)
app.include_router(auth_router)

app.add_middleware(LoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(security_headers_middleware)


@app.get("/api/health")
async def health():
    from repositories.order_repo import RawOrderRepository
    raw_count = await RawOrderRepository().count_all()
    profile_count = await _customer_service.count_all()
    pending_count = await _customer_service.get_pending_analysis_count()
    return {"status": "ok", "raw_orders": raw_count, "profiles": profile_count, "pending_analysis": pending_count, "cycle": cycle}


@app.post("/api/fetch-data")
async def trigger_fetch():
    results = await _order_service.fetch_and_store_all()
    return {"message": "Data fetch completed", "results": results}


@app.post("/api/build-profiles")
async def trigger_profiles():
    result = await _profile_service.build_profiles()
    return {"message": "Profiles built", "result": result}


@app.post("/api/analyze-comments")
async def trigger_comment_analysis():
    result = await _comment_service.fetch_and_store()
    return {"message": "Comment analysis completed", "result": result}


@app.post("/api/refresh-all")
async def refresh_all():
    from services.profile_summarizer import get_profile_summarizer
    fetch_result = await _order_service.fetch_and_store_all()
    profile_result = await _profile_service.build_profiles()
    comment_result = await _comment_service.fetch_and_store()
    summarizer = get_profile_summarizer()
    summary_count = await summarizer.generate_for_all()
    return {
        "fetch": fetch_result,
        "profiles": profile_result,
        "comments": comment_result,
        "summaries_generated": summary_count,
    }


@app.post("/api/f3db/load")
async def trigger_f3db_load():
    loader = F3DbLoader()
    result = await loader.load_all_files()
    return {"message": "F3DB load completed", "result": {
        "files_processed": result.total_fetched,
        "valid": result.valid_count,
        "inserted": result.inserted_count,
        "duplicates": result.duplicate_count,
        "errors": result.validation_errors[:20],
    }}


@app.post("/api/summarize-all")
async def trigger_summarize_all():
    from services.profile_summarizer import get_profile_summarizer
    summarizer = get_profile_summarizer()
    count = await summarizer.generate_for_all()
    return {"message": f"Summaries generated for {count} customer(s)", "count": count}


@app.get("/api/customers")
async def list_customers(
    limit: int = Query(0, ge=0, description="Max records (0 = all via cache)"),
    offset: int = Query(0, ge=0, description="Skip N records"),
    sort: str = Query("last_activity", description="Sort column"),
    order: str = Query("DESC", pattern="^(ASC|DESC)$"),
    search: str = Query("", description="Search name/email/phone/username"),
):
    if limit > 0:
        items, total = await _customer_service.get_all_paginated(
            limit=limit, offset=offset, sort=sort, order=order, search=search,
        )
        return paginated(items, total, limit, offset)
    if search:
        items = await _customer_service.search(search)
        return ok(items, total=len(items))
    customers = await _customer_service.get_all()
    return {"customers": customers, "total": len(customers)}


@app.get("/api/customers/{customer_id}")
async def customer_detail(customer_id: str):
    customer = await _customer_service.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@app.get("/api/customers/{customer_id}/bad-comments")
async def customer_bad_comments(customer_id: str):
    comments = await _comment_service.get_bad_comments(customer_id)
    count = await _comment_service.get_bad_comment_count(customer_id)
    return {"customer_id": customer_id, "bad_comments": comments, "count": count}

@app.get("/api/customers/{customer_id}/profile")
async def customer_profile(customer_id: str):
    profile = await _customer_service.get_profile(customer_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Customer not found")
    return ok(profile)


@app.get("/api/customers/{customer_id}/timeline")
async def customer_timeline(customer_id: str):
    timeline = await _customer_service.get_timeline(customer_id)
    return ok(timeline)


@app.get("/api/customers/{customer_id}/analytics")
async def customer_analytics(customer_id: str):
    analytics = await _customer_service.get_analytics(customer_id)
    if not analytics:
        raise HTTPException(status_code=404, detail="Customer not found")
    return ok(analytics)


@app.get("/api/customers/{customer_id}/summary")
async def customer_summary(customer_id: str, refresh: bool = False):
    customer = await _customer_service.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    summarizer = get_profile_summarizer()
    if refresh:
        summary = await summarizer.regenerate_summary(customer, customer_id)
    else:
        summary = await summarizer.generate_summary(customer, customer_id)
    return {"customer_id": customer_id, "summary": summary}


@app.get("/api/customer-form/{phone}")
async def customer_form_data(phone: str, _: None = Depends(verify_api_key)):
    data = await _customer_service.get_form_data(phone)
    if not data:
        raise HTTPException(status_code=404, detail="Customer not found")
    return ok(data)


@app.get("/api/customers/{customer_id}/section-summaries")
async def customer_section_summaries(customer_id: str):
    summarizer = get_section_summarizer()
    try:
        result = await summarizer.get_section_summaries(customer_id)
        return ok(result)
    except ValueError:
        raise HTTPException(status_code=404, detail="Customer not found")


@app.get("/api/alerts")
async def list_alerts(
    limit: int = Query(10000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    alert_type: Optional[str] = Query(None, description="Filter by type"),
):
    if offset > 0 or severity or alert_type:
        items, total = await _alert_service.get_all_paginated(
            limit=limit, offset=offset, severity=severity, alert_type=alert_type,
        )
        return paginated(items, total, limit, offset)
    alerts = await _alert_service.get_all(limit=limit)
    return {"alerts": alerts, "total": len(alerts)}


@app.get("/api/recommendations")
async def list_recommendations(
    status: str = Query("active"),
    priority: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("DESC", pattern="^(ASC|DESC)$"),
    search: str = Query(""),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    if offset > 0 or search or date_from or date_to or category or sort_by != "created_at" or sort_order != "DESC":
        items, total = await _rec_service.get_all_paginated(
            status=status, priority=priority, search=search,
            limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order,
            date_from=date_from, date_to=date_to, category=category,
        )
        return paginated(items, total, limit, offset)
    recs = await _rec_service.get_all(status=status, priority=priority, limit=limit)
    return {"recommendations": recs, "total": len(recs)}


@app.get("/api/recommendations/high-priority")
async def high_priority_recommendations(limit: int = Query(20, ge=1, le=200)):
    recs = await _rec_service.get_high_priority(limit=limit)
    return {"recommendations": recs, "total": len(recs)}


@app.get("/api/customers/{customer_id}/recommendations")
async def customer_recommendations(customer_id: str, status: str = Query("active")):
    recs = await _rec_service.get_by_customer_id(customer_id, status=status)
    return {"customer_id": customer_id, "recommendations": recs, "total": len(recs)}


@app.post("/api/recommendations/process")
async def trigger_recommendation_worker(batch_size: int = 10):
    result = await _rec_service.process_batch(batch_size=batch_size)
    return {"message": "Recommendation processing completed", "result": result}


@app.get("/api/dashboard/summary")
async def dashboard_summary():
    data = await _dashboard_service.get_summary()
    return ok(data)


@app.get("/api/cache/metrics")
async def cache_metrics():
    return await cache_manager.get_metrics()


# ── Health Endpoints ─────────────────────────────────────────────────────────

@app.get("/health")
async def health_full():
    db_ok = False
    redis_ok = redis_client.available
    mcp_ok = False
    try:
        from config.postgres import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT 1")
            db_ok = val == 1
    except Exception:
        db_ok = False
    try:
        from c360_mcp.handler import handle_list_resources
        resources = await handle_list_resources()
        mcp_ok = len(resources) > 0
    except Exception:
        mcp_ok = False
    all_ok = db_ok and redis_ok
    status_code = 200 if all_ok else 503
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_ok else "degraded",
            "checks": {
                "database": "ok" if db_ok else "fail",
                "redis": "ok" if redis_ok else "fail",
                "mcp": "ok" if mcp_ok else "fail",
            },
            "uptime_seconds": metrics.snapshot().get("uptime_seconds", 0),
            "version": "1.0.0",
        },
    )


@app.get("/health/live")
async def health_live():
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    db_ok = False
    try:
        from config.postgres import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT 1")
            db_ok = val == 1
    except Exception:
        db_ok = False
    redis_ok = redis_client.available
    if not db_ok or not redis_ok:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "ok" if db_ok else "fail", "redis": "ok" if redis_ok else "fail"})
    return {"status": "ready"}


# ── Metrics Endpoint ─────────────────────────────────────────────────────────

@app.get("/metrics")
async def prometheus_metrics():
    snapshot = metrics.snapshot()
    lines = [
        "# HELP c360_uptime_seconds Application uptime",
        "# TYPE c360_uptime_seconds gauge",
        f"c360_uptime_seconds {snapshot['uptime_seconds']}",
    ]
    for name, value in snapshot["counters"].items():
        safe_name = name.replace(".", "_").replace("-", "_")
        lines.append(f"# HELP c360_{safe_name} Counter for {name}")
        lines.append(f"# TYPE c360_{safe_name} counter")
        lines.append(f"c360_{safe_name} {value}")
    for name, timing in snapshot["timings"].items():
        safe_name = name.replace(".", "_").replace("-", "_")
        lines.append(f"# HELP c360_{safe_name}_duration_ms Duration for {name}")
        lines.append(f"# TYPE c360_{safe_name}_duration_ms gauge")
        lines.append(f"c360_{safe_name}_duration_ms{{quantile=\"avg\"}} {timing['avg_ms']}")
        lines.append(f"c360_{safe_name}_duration_ms{{quantile=\"max\"}} {timing['max_ms']}")
        lines.append(f"c360_{safe_name}_duration_ms{{quantile=\"min\"}} {timing['min_ms']}")
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines) + "\n")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
