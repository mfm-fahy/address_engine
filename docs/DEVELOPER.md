# Developer Setup Guide

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker Desktop (optional, for containerized development)
- PostgreSQL 16 (optional, Docker provides this)
- Redis 7 (optional, Docker provides this)

## Local Development Setup

### Backend

```bash
# Clone the repo
git clone <repo-url> && cd Address

# Create virtual environment
cd server
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-asyncio httpx

# Start PostgreSQL and Redis via Docker
docker compose up -d postgres redis

# Copy environment file
cp .env.example .env
# Edit .env with your API keys

# Run the application
python main.py
# Server starts at http://localhost:8000
```

### Frontend

```bash
cd client
npm install
npm run dev
# Dev server at http://localhost:5173
```

## Running Tests

```bash
# Run all unit tests
cd server
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_rule_engine.py -v

# Run MCP tests
python test_mcp.py

# Run API benchmark (requires running server)
python tests/api_benchmark.py --live
```

## Project Structure

```
Address/
├── client/              # React frontend
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── App.jsx     # Main app
│   │   ├── AuthContext.jsx
│   │   └── api.js       # API client
│   ├── Dockerfile
│   └── nginx.conf
├── server/              # Python backend
│   ├── ai/              # AI recommendation engine
│   ├── api/             # API re-exports
│   ├── auth/            # Authentication & RBAC
│   ├── c360_mcp/        # MCP server
│   ├── config/          # Configuration & DB
│   ├── pipeline/        # Data ingestion pipeline
│   ├── repositories/    # Database access layer
│   ├── services/        # Business logic layer
│   ├── tests/           # Automated test suite
│   ├── main.py          # FastAPI application
│   ├── api_helpers.py   # Response helpers
│   ├── models.py        # Pydantic models
│   └── monitoring.py    # Metrics & logging
├── docker-compose.yml   # Development Docker setup
├── docker-compose.prod.yml  # Production Docker setup
└── docs/                # Documentation
```

## Key Configuration Files

| File | Purpose |
|------|---------|
| `server/.env` | Environment variables |
| `server/config/settings.py` | Application settings |
| `server/pytest.ini` | Test configuration |
| `docker-compose.yml` | Service orchestration |

## Adding New API Endpoints

1. Define any new models in `server/models.py` if needed
2. Create or update the repository in `server/repositories/`
3. Create or update the service in `server/services/`
4. Add the route handler in `server/main.py`
5. Add tests in `server/tests/`

## Code Conventions

- Python: PEP 8, type hints required for all functions
- FastAPI: Use async endpoints where possible
- Database: Always use asyncpg via the repository pattern
- Caching: Use CacheManager for Redis caching
- Errors: Use HTTPException for API errors, sanitize in middleware
- Tests: One test class per component, one test method per behavior
