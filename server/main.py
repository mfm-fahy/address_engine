from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from config.database import connect_db, close_db
from config.postgres import get_pool
from api.data_fetcher import fetch_and_store_all
from api.comment_fetcher import analyze_and_store_comments, get_tenant_ids
from api.customer_matching import build_customer_profiles, get_all_customers, get_customer_by_id, get_alerts
from c360_mcp.routes import router as mcp_router
from c360_mcp.handler import get_pool as mcp_get_pool, close_pool as mcp_close_pool


FETCH_INTERVAL = 5

cycle = 0


async def background_fetch_loop():
    global cycle
    while True:
        try:
            cycle += 1
            print(f"[scheduler] Cycle {cycle}: Fetching data...")
            fetch_result = await fetch_and_store_all()
            print(f"[scheduler] Fetch done: {fetch_result}")

            if cycle % 2 == 0:
                print("[scheduler] Building profiles...")
                profile_result = await build_customer_profiles()
                print(f"[scheduler] Profiles done: {profile_result}")

            if cycle % 6 == 0:
                print("[scheduler] Analyzing comments...")
                tenant_ids = await get_tenant_ids()
                for tid in tenant_ids:
                    await analyze_and_store_comments(tid)

            await asyncio.sleep(FETCH_INTERVAL)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[scheduler] Error: {e}")
            await asyncio.sleep(FETCH_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    try:
        await mcp_get_pool()
    except Exception:
        print("[mcp] PostgreSQL not available, MCP pool will be lazy")
    task = asyncio.create_task(background_fetch_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await mcp_close_pool()
    await close_db()

app = FastAPI(title="Customer360 API", lifespan=lifespan)
app.include_router(mcp_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    pool = get_pool()
    async with pool.acquire() as conn:
        raw_count = await conn.fetchval("SELECT COUNT(*) FROM raw_orders")
        profile_count = await conn.fetchval("SELECT COUNT(*) FROM customers")
    return {"status": "ok", "raw_orders": raw_count, "profiles": profile_count, "cycle": cycle}


@app.post("/api/fetch-data")
async def trigger_fetch():
    results = await fetch_and_store_all()
    return {"message": "Data fetch completed", "results": results}


@app.post("/api/build-profiles")
async def trigger_profiles():
    result = await build_customer_profiles()
    return {"message": "Profiles built", "result": result}


@app.post("/api/analyze-comments")
async def trigger_comment_analysis():
    tenant_ids = await get_tenant_ids()
    all_results = []
    for tid in tenant_ids:
        result = await analyze_and_store_comments(tid)
        all_results.append({"tenant_id": tid, "result": result})
    if not all_results:
        result = await analyze_and_store_comments("5573c0ef-f0b0-4477-8681-c50e97a48280")
        all_results.append({"tenant_id": "default", "result": result})
    return {"message": "Comment analysis completed", "results": all_results}


@app.post("/api/refresh-all")
async def refresh_all():
    fetch_result = await fetch_and_store_all()
    profile_result = await build_customer_profiles()
    tenant_ids = await get_tenant_ids()
    comment_results = []
    for tid in tenant_ids:
        r = await analyze_and_store_comments(tid)
        comment_results.append(r)
    return {
        "fetch": fetch_result,
        "profiles": profile_result,
        "comments": comment_results
    }


@app.get("/api/customers")
async def list_customers():
    customers = await get_all_customers()
    return {"customers": customers, "total": len(customers)}


@app.get("/api/customers/{customer_id}")
async def customer_detail(customer_id: str):
    customer = await get_customer_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@app.get("/api/alerts")
async def list_alerts():
    alerts = await get_alerts()
    return {"alerts": alerts, "total": len(alerts)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
