# Deployment Guide

## Docker Deployment

### Prerequisites
- Docker Engine 24+
- Docker Compose v2+
- 2GB+ RAM allocated to Docker

### Quick Start

```bash
# Clone and enter the project
cd Address

# Set up environment
cp server/.env.example server/.env
# Edit .env with your API keys

# Start all services
docker compose up -d

# Verify deployment
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

### Production Deployment

```bash
# Use the production compose file
docker compose -f docker-compose.prod.yml up -d

# Set production passwords
export POSTGRES_PASSWORD=$(openssl rand -hex 32)
export REDIS_PASSWORD=$(openssl rand -hex 32)

# Enable authentication
export AUTH_ENABLED=true
export JWT_SECRET_KEY=$(openssl rand -hex 64)
export AUTH_ADMIN_PASSWORD=$(openssl rand -hex 16)
```

### Service Ports

| Service  | Port  |
|----------|-------|
| Backend  | 8000  |
| Frontend | 80/443|
| PostgreSQL | 5432 |
| Redis    | 6379  |
| pgAdmin  | 5050  |

## AWS EC2 Deployment

### EC2 Configuration
- Instance type: t3.medium (minimum)
- Storage: 20GB+ gp3
- Security group:
  - HTTP (80): 0.0.0.0/0
  - HTTPS (443): 0.0.0.0/0
  - SSH (22): your-ip/32
  - Backend (8000): internal or restricted

### Reverse Proxy (Nginx)
The frontend container runs Nginx that proxies `/api/*` and `/mcp/*` requests to the backend. HTTPS is configured via SSL certificates mounted from `./ssl/`.

### Firewall Rules
```bash
# Allow only necessary ports
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Auto-Restart
All services are configured with `restart: unless-stopped` in docker-compose.

### Log Management
```bash
# View logs
docker compose logs -f backend
docker compose logs -f frontend

# Log rotation is handled by Docker by default
# For persistent logs, configure Docker's log-opts in daemon.json
```

### Monitoring Setup
```bash
# Check health
curl http://localhost:8000/health
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready

# Get metrics
curl http://localhost:8000/metrics
```

## Docker Optimization

### Current Image Size
- Base image: python:3.11-slim
- Multi-stage build reduces final image size
- Production image: <300MB

### Optimization Recommendations
1. Use `python:3.11-alpine` for smaller base images (~50MB reduction)
2. Pin all apt packages in builder stage
3. Use `.dockerignore` to exclude venv, __pycache__, .git, .env
4. Combine RUN commands to reduce layers
5. Use `--no-cache-dir` for pip installs (already configured)

### Health Checks
All services have Docker health checks configured:
- PostgreSQL: `pg_isready`
- Redis: `redis-cli ping`
- Backend: HTTP GET to `/api/health`

### Resource Limits (docker-compose.yml)
- Redis: 256MB memory, 0.5 CPU
- PostgreSQL: 512MB memory, 1.0 CPU
- Backend: 512MB memory, 1.0 CPU

## Environment Variables

### Required
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `GOWHATS_API_KEY`
- `INSTAXBOT_API_KEY`
- `F3_API_KEY`
- `BILLZZY_API_KEY`

### Optional
- `OPENROUTER_API_KEY` - for AI features
- `OPENROUTER_MODEL` - model name (default: openai/gpt-4o-mini)
- `AUTH_ENABLED` - enable JWT auth (default: false)
- `JWT_SECRET_KEY` - JWT signing key
- `REDIS_PASSWORD` - Redis auth password
- `LOG_LEVEL` - logging level (DEBUG, INFO, WARN, ERROR)
