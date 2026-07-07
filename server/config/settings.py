import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://customer360:customer360@localhost:5432/customer360")

API_KEYS = {
    "gowhats": {
        "url": "https://bot.gowhats.in/api/admin/orders",
        "key": os.getenv("GOWHATS_API_KEY", ""),
        "timeout": 300,
        "per_request_timeout": 60
    },
    "instaxbot": {
        "url": "https://app.instaxbot.com/api/f3engineapiroute/orders",
        "key": os.getenv("INSTAXBOT_API_KEY", ""),
        "timeout": 300,
        "per_request_timeout": 60
    },
    "f3": {
        "url": "https://f3engine.com/api/external/orders",
        "key": os.getenv("F3_API_KEY", ""),
        "timeout": 60,
        "per_request_timeout": 60
    },
    "bill": {
        "url": "https://billzzy.com/api/admin/all-data",
        "key": os.getenv("BILLZZY_API_KEY", ""),
        "timeout": 600,
        "per_request_timeout": 120
    }
}

COMMENT_RULES_URL = "https://app.instaxbot.com/api/commentAutomationroute/rules"
COMMENT_RULES_BY_MEDIA_URL = "https://app.instaxbot.com/api/commentAutomationroute/rules-by-media"

SENTIMENT_THRESHOLD = -0.3

# Connection pool configuration
DB_POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "2"))
DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "20"))
DB_POOL_MAX_INACTIVE_CONNECTION_LIFETIME = float(os.getenv("DB_POOL_MAX_INACTIVE_CONNECTION_LIFETIME", "300.0"))

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Cache TTL values (seconds) — configurable via env vars
DASHBOARD_TTL = int(os.getenv("CACHE_DASHBOARD_TTL", "120"))
CUSTOMER_PROFILE_TTL = int(os.getenv("CACHE_CUSTOMER_PROFILE_TTL", "300"))
CUSTOMER_LIST_TTL = int(os.getenv("CACHE_CUSTOMER_LIST_TTL", "300"))
SEARCH_TTL = int(os.getenv("CACHE_SEARCH_TTL", "120"))
ALERTS_TTL = int(os.getenv("CACHE_ALERTS_TTL", "60"))
RECOMMENDATION_TTL = int(os.getenv("CACHE_RECOMMENDATION_TTL", "300"))

# Background worker configuration
WORKER_BATCH_SIZE = int(os.getenv("WORKER_BATCH_SIZE", "10"))
WORKER_CYCLE_INTERVAL = int(os.getenv("WORKER_CYCLE_INTERVAL", "4"))  # cycles between recommendation runs

# Authentication configuration
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Redis AUTH password
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
