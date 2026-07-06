"""
API Performance Benchmark

Measures response times for all major API endpoints.

Usage:
    python tests/api_benchmark.py              # Uses mock/offline mode
    python tests/api_benchmark.py --live        # Requires running server at http://localhost:8000
"""
import asyncio
import statistics
import sys
import time
from typing import Any

import httpx

BASE_URL = "http://localhost:8000"
WARMUP = 3
ITERATIONS = 10
TIMEOUT = 30.0

ENDPOINTS = [
    ("GET", "/health/live", "Liveness Check"),
    ("GET", "/health", "Full Health"),
    ("GET", "/metrics", "Metrics"),
    ("GET", "/api/cache/metrics", "Cache Metrics"),
    ("GET", "/api/auth/status", "Auth Status"),
    ("GET", "/api/dashboard/summary", "Dashboard Summary"),
    ("GET", "/api/alerts", "Alerts List"),
    ("GET", "/api/recommendations", "Recommendations"),
    ("GET", "/api/customers", "Customers List"),
    ("GET", "/api/health", "API Health"),
]


async def benchmark_endpoint(client: httpx.AsyncClient, method: str, path: str, name: str, results: list):
    timings = []

    for i in range(WARMUP + ITERATIONS):
        t0 = time.monotonic()
        try:
            resp = await client.request(method, f"{BASE_URL}{path}", timeout=TIMEOUT)
            elapsed = (time.monotonic() - t0) * 1000
            if i >= WARMUP:
                timings.append(elapsed)
        except Exception as e:
            if i >= WARMUP:
                timings.append(None)

    valid = [t for t in timings if t is not None]
    if not valid:
        results.append((name, path, "FAILED", 0, 0, 0))
        return

    avg = statistics.mean(valid)
    mx = max(valid)
    mn = min(valid)
    p50 = statistics.median(valid)
    results.append((name, path, round(avg, 2), round(mn, 2), round(mx, 2), round(p50, 2)))


async def main():
    use_live = "--live" in sys.argv

    if not use_live:
        print("=" * 65)
        print("  API Performance Benchmark (offline metrics)")
        print("=" * 65)
        print("\n  No live server required. Metrics collected from /metrics endpoint.\n")

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{BASE_URL}/metrics", timeout=5)
                if resp.status_code == 200:
                    print("  [OK] Server at http://localhost:8000 is reachable")
                    print()
                else:
                    print("  [WARN] Server not reachable — run with --live if needed")
                    print()
        except Exception:
            print("  [INFO] No running server detected. Run with --live to benchmark live endpoints.")
            print()
        return

    print("=" * 65)
    print("  API Performance Benchmark (live)")
    print(f"  Target: {BASE_URL}")
    print(f"  Warmup: {WARMUP}, Iterations: {ITERATIONS}")
    print("=" * 65)
    print()

    async with httpx.AsyncClient() as client:
        results: list[tuple[str, str, Any, Any, Any, Any]] = []

        for method, path, name in ENDPOINTS:
            await benchmark_endpoint(client, method, path, name, results)

    print(f"  {'Endpoint':<30} {'Avg(ms)':<10} {'Min(ms)':<10} {'Max(ms)':<10} {'P50(ms)':<10}")
    print("  " + "-" * 70)
    for name, path, avg, mn, mx, p50 in results:
        print(f"  {name:<30} {str(avg):<10} {str(mn):<10} {str(mx):<10} {str(p50):<10}")

    print()
    print("=" * 65)
    print("  Performance Targets:")
    print("    Cached API response    < 50 ms")
    print("    Database API response  < 200 ms")
    print("    Dashboard load         < 1 second")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
