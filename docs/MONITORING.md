# Monitoring Guide

## Health Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `/health` | Full health check (DB, Redis, MCP) | 200 or 503 |
| `/health/live` | Liveness probe (container health) | 200 `{"status": "alive"}` |
| `/health/ready` | Readiness probe (can serve traffic) | 200 or 503 |

## Metrics Endpoint

`GET /metrics` returns Prometheus-compatible metrics:

```
# HELP c360_uptime_seconds Application uptime
# TYPE c360_uptime_seconds gauge
c360_uptime_seconds 1234.56

# HELP c360_api_200 Counter for status 200
# TYPE c360_api_200 counter
c360_api_200 1500

# HELP c360_api_500 Counter for status 500
# TYPE c360_api_500 counter
c360_api_500 3

# HELP c360_api_GET_api_customers_duration_ms Response time
# TYPE c360_api_GET_api_customers_duration_ms gauge
c360_api_GET_api_customers_duration_ms{quantile="avg"} 45.2
```

### Prometheus Integration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'customer360'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### Grafana Dashboard Suggestions

1. **API Performance**: Request duration by endpoint (p50, p95, p99)
2. **Error Rates**: 4xx and 5xx response count over time
3. **Cache Performance**: Redis hit ratio (from `/api/cache/metrics`)
4. **System Health**: Uptime, DB/Redis/MCP connectivity
5. **Auth Events**: Login success/failure rate

## What to Monitor

### Critical
- API response times (target: cached <50ms, DB <200ms)
- Error rates (target: <1% of requests)
- Database connectivity
- Redis connectivity
- Background scheduler health (check `/api/health` for cycle count)

### Important
- Cache hit ratio (target: >80%)
- Slow requests (tracked by LoggingMiddleware, threshold: 500ms)
- OpenRouter API latency
- Recommendation generation throughput
- MCP server availability

### Informational
- Total API requests
- Active customer count
- Recommendation count by priority
- Alert volume by severity

## Logging

### Structured JSON Logging
All API requests are logged in JSON format:
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "event": "request",
  "method": "GET",
  "path": "/api/customers",
  "status": 200,
  "duration_ms": 45.2
}
```

### Log Levels
- `DEBUG`: Detailed debugging information
- `INFO`: Normal operational events
- `WARN`: Warning conditions (4xx responses, slow requests)
- `ERROR`: Error conditions (5xx responses, exceptions)

### Log Locations
- Docker: `docker compose logs -f backend`
- File (when configured): `./logs/`

### Configurable via Environment
- `LOG_LEVEL`: Set to DEBUG, INFO, WARN, or ERROR (default: INFO)

## Alerting Recommendations

### PagerDuty / OpsGenie Integration
1. Monitor `/health` endpoint — alert on 503
2. Monitor error rate > 5% in 5-minute window
3. Monitor scheduler cycle gaps > 60 seconds
4. Monitor Redis connection failures

### Health Check Monitoring
For best results, use separate probes:
- Liveness: `/health/live` every 30s
- Readiness: `/health/ready` every 30s
- Full health: `/health` every 60s (less frequently to reduce load)
