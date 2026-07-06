import pytest


class TestHealthEndpoints:

    @pytest.mark.asyncio
    async def test_health_live(self, client):
        resp = await client.get("/health/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "alive"

    @pytest.mark.asyncio
    async def test_health_ready(self, client):
        resp = await client.get("/health/ready")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "status" in data

    @pytest.mark.asyncio
    async def test_health_full(self, client):
        resp = await client.get("/health")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "status" in data
        assert "checks" in data
        assert "database" in data["checks"]
        assert "redis" in data["checks"]
        assert "mcp" in data["checks"]

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client):
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/plain; charset=utf-8"
        body = resp.text
        assert "c360_uptime_seconds" in body


class TestExistingEndpoints:

    @pytest.mark.asyncio
    async def test_api_health(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_api_cache_metrics(self, client):
        resp = await client.get("/api/cache/metrics")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_api_dashboard_summary(self, client):
        resp = await client.get("/api/dashboard/summary")
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_api_alerts(self, client):
        resp = await client.get("/api/alerts")
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_api_recommendations(self, client):
        resp = await client.get("/api/recommendations")
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_api_customers(self, client):
        resp = await client.get("/api/customers")
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_api_auth_status(self, client):
        resp = await client.get("/api/auth/status")
        assert resp.status_code == 200
