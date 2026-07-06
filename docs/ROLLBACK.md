# Rollback Plan

## Rollback Triggers

Rollback should be initiated if:
1. API error rate exceeds 5% after deployment
2. Database schema migration causes data loss
3. Scheduler fails to complete cycles for more than 5 minutes
4. Dashboard fails to load critical data
5. Authentication issues prevent legitimate access
6. Performance degrades beyond acceptable thresholds

## Rollback Procedures

### Application Rollback (Docker)

```bash
# Rollback backend to previous version
docker compose stop backend
docker compose rm -f backend
docker compose up -d backend

# If using tagged images, specify previous tag
docker compose -f docker-compose.prod.yml up -d backend:previous-tag

# Verify rollback
curl http://localhost:8000/health
```

### Database Rollback

```bash
# If schema migration was applied, restore from backup
# 1. Identify the latest backup before the deployment
ls -la ./backups/

# 2. Restore the database
gunzip -c ./backups/customer360_before_deploy.sql.gz | \
  docker exec -i address-postgres-1 psql -U customer360 -d customer360

# 3. Restart backend to clear any cached state
docker compose restart backend
```

### Full System Rollback

```bash
# 1. Revert code changes
git reset --hard <previous-commit-hash>

# 2. Rebuild and redeploy
docker compose build backend
docker compose up -d

# 3. Restore database if schema changed
# (see Database Rollback above)

# 4. Verify all components
docker compose ps
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

## Rollback Verification Checklist

- [ ] Backend health check passes (`/health/live`)
- [ ] Database connectivity confirmed (`/health/ready`)
- [ ] Redis connectivity confirmed (`/health/ready`)
- [ ] All existing API endpoints respond correctly
- [ ] Dashboard loads without errors
- [ ] Scheduler is running (check `/api/health`)
- [ ] MCP server is available
- [ ] Authentication works (if enabled)
- [ ] Logs show normal operation

## Post-Rollback Actions

1. **Analyze root cause**: Review logs from the failed deployment
2. **Create fix**: Address the issue in a new branch
3. **Add tests**: Ensure the issue is covered by automated tests
4. **Deploy fix**: Follow normal deployment process with additional verification

## Communication

In case of rollback:
1. Notify the team immediately
2. Document the reason for rollback
3. Share the rollback verification results
4. Schedule root cause analysis within 24 hours
