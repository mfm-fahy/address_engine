import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "customer360")
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
