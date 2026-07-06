# API Documentation

## Base URL

Development: `http://localhost:8000`
Production: `https://your-domain.com`

## Response Format

All API responses follow a consistent format:

```json
{
  "success": true,
  "data": { ... },
  "total": 100,
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 100
  }
}
```

Error responses:
```json
{
  "success": false,
  "error": {
    "code": "error_code",
    "detail": "Human-readable message"
  }
}
```

## Health Endpoints

### GET /health
Full health check validating database, Redis, and MCP connectivity.
- Status: 200 (healthy) or 503 (degraded)
- Response includes uptime and version

### GET /health/live
Lightweight liveness probe.
- Status: 200
- Response: `{"status": "alive"}`

### GET /health/ready
Readiness probe checking database and Redis.
- Status: 200 (ready) or 503 (not ready)

## Metrics Endpoint

### GET /metrics
Prometheus-compatible metrics format (text/plain).

## Authentication Endpoints

### POST /api/auth/login
Authenticate with username and password.
```json
{
  "username": "admin",
  "password": "your_password"
}
```
Returns access_token, refresh_token, expires_in.

### POST /api/auth/refresh
Refresh an expired access token.
```json
{
  "refresh_token": "eyJ..."
}
```

### GET /api/auth/me
Get current user info (requires auth).

### GET /api/auth/status
Check authentication configuration status.

## Customer Endpoints

### GET /api/customers
List customers with pagination, sorting, and search.
- Query params: `limit`, `offset`, `sort`, `order` (ASC/DESC), `search`

### GET /api/customers/{customer_id}
Get customer detail by ID.

### GET /api/customers/{customer_id}/profile
Get enriched customer profile.

### GET /api/customers/{customer_id}/timeline
Get customer activity timeline.

### GET /api/customers/{customer_id}/analytics
Get customer analytics data.

### GET /api/customers/{customer_id}/recommendations
Get customer-specific recommendations.

## Alert Endpoints

### GET /api/alerts
List alerts with optional filters.
- Query params: `limit`, `offset`, `severity`, `alert_type`

## Recommendation Endpoints

### GET /api/recommendations
List all active recommendations.
- Query params: `status`, `priority`, `limit`, `offset`, `sort_by`, `sort_order`, `search`, `date_from`, `date_to`, `category`

### GET /api/recommendations/high-priority
Get high-priority recommendations.
- Query params: `limit`

### POST /api/recommendations/process
Trigger recommendation batch processing.
- Body: `{"batch_size": 10}`

## Dashboard Endpoints

### GET /api/dashboard/summary
Get dashboard summary data.

## Cache Endpoints

### GET /api/cache/metrics
Get Redis cache hit/miss metrics.

## Data Management Endpoints

### POST /api/fetch-data
Trigger manual data fetch from all sources.

### POST /api/build-profiles
Trigger customer profile building.

### POST /api/analyze-comments
Trigger comment analysis and sentiment detection.

### POST /api/refresh-all
Trigger full refresh: fetch → profiles → comments.

## AI Endpoints

### POST /api/ai/chat
Chat with the AI business assistant.
- Body: `{"message": "string", "customer_id?": "string"}`

### POST /api/business/insights
Generate business insights for a customer.

### POST /api/business/recommendations
Get AI-powered recommendations.

### GET /api/customers/{customer_id}/insights
Get AI insights for a specific customer.

## MCP Endpoints

### GET /mcp/health
Check MCP server health.

### GET /mcp/key-info
Get MCP API key information (requires auth).

### POST /mcp
SSE and JSON-RPC endpoint for MCP communication.
