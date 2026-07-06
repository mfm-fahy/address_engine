# Troubleshooting Guide

## Common Issues

### Backend won't start

**Symptoms**: `docker compose up` fails, container exits immediately.

**Checks**:
1. Is PostgreSQL reachable? `docker compose logs postgres`
2. Is Redis reachable? `docker compose logs redis`
3. Check environment variables: `docker compose run backend env`
4. Verify .env file exists and has required keys

**Solutions**:
```bash
# Wait for PostgreSQL to finish initializing (first start takes 10-30s)
docker compose logs -f postgres

# Test connectivity
docker compose exec backend python -c "import asyncpg; print('ok')"

# Reset and retry
docker compose down -v && docker compose up -d
```

### Database connection errors

**Symptoms**: `connection refused` or `database does not exist`.

**Solutions**:
```bash
# Verify PostgreSQL is running
docker compose ps postgres

# Check connection string
docker compose exec postgres psql -U customer360 -c "SELECT 1"

# Recreate database if corrupted
docker compose exec postgres psql -U customer360 -c "DROP DATABASE customer360;"
docker compose exec postgres psql -U customer360 -c "CREATE DATABASE customer360;"
docker compose restart backend
```

### Redis connection errors

**Symptoms**: Cache disabled, slow responses.

**Solutions**:
```bash
# Check Redis health
docker compose exec redis redis-cli ping
# Should return: PONG

# If Redis password is set, use:
docker compose exec redis redis-cli -a yourpassword ping

# Restart Redis
docker compose restart redis
```

### API returns 500 errors

**Symptoms**: All or some API endpoints return 500.

**Solutions**:
1. Check backend logs: `docker compose logs --tail=50 backend`
2. Verify database schema: `docker compose exec postgres psql -U customer360 -c "\dt"`
3. Check for unhandled exceptions in the logs
4. The LoggingMiddleware catches all unhandled exceptions and returns sanitized 500 responses

### Authentication issues

**Symptoms**: 401 Unauthorized or 403 Forbidden errors.

**Solutions**:
```bash
# Check if auth is enabled
curl http://localhost:8000/api/auth/status

# Auth is disabled by default (AUTH_ENABLED=false)
# To enable, set in .env:
# AUTH_ENABLED=true
# JWT_SECRET_KEY=<your-secret>
# AUTH_ADMIN_USERNAME=admin
# AUTH_ADMIN_PASSWORD=<strong-password>
```

### Scheduler not running

**Symptoms**: No data being fetched, stale dashboard data.

**Solutions**:
1. Check logs: `docker compose logs --tail=50 backend | grep scheduler`
2. The scheduler runs on a 5-second cycle by default
3. Verify background_fetch_loop is running in the lifespan

### MCP server issues

**Symptoms**: AI assistant cannot access tools.

**Solutions**:
1. Check MCP health: `curl http://localhost:8000/mcp/health`
2. Verify API key: `curl http://localhost:8000/mcp/key-info`
3. Test MCP resources: `curl http://localhost:8000/mcp -d '{"jsonrpc":"2.0","id":1,"method":"resources/list"}'`

## Performance Issues

### Slow API responses (Database)

**Symptoms**: Non-cached endpoints take > 200ms.

**Solutions**:
1. Check for missing indexes
2. Monitor query performance via PostgreSQL slow query log
3. Increase DB_POOL_MAX_SIZE if under heavy load

### Low cache hit ratio

**Symptoms**: Cache hit ratio < 50%.

**Solutions**:
1. Increase TTL values in settings.py
2. Verify Redis connectivity
3. Check cache invalidation patterns

## Container Issues

### Out of memory

**Symptoms**: Containers restarting unexpectedly.

**Solutions**:
1. Check resource limits in docker-compose.yml
2. Increase memory limits:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 1G
   ```
3. Monitor with: `docker stats`

### Disk space

**Symptoms**: PostgreSQL stops, backup failures.

**Solutions**:
1. Clean old Docker images: `docker image prune -a`
2. Clean old backups
3. Check Docker disk usage: `docker system df`
