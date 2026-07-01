import asyncio
import asyncpg
from config.settings import DATABASE_URL

pool = None

async def connect(retries=10, delay=3):
    global pool
    for attempt in range(1, retries + 1):
        try:
            pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
            print("Connected to PostgreSQL")
            return
        except Exception as e:
            print(f"PostgreSQL connection attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                await asyncio.sleep(delay)
            else:
                raise

async def close():
    global pool
    if pool:
        await pool.close()
        print("PostgreSQL connection closed")

async def init_schema():
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id TEXT PRIMARY KEY,
                phone TEXT NOT NULL,
                name TEXT DEFAULT '',
                email TEXT DEFAULT '',
                username TEXT DEFAULT '',
                total_orders INTEGER DEFAULT 0,
                total_bills INTEGER DEFAULT 0,
                total_spent NUMERIC(12,2) DEFAULT 0,
                orders JSONB DEFAULT '[]',
                bills JSONB DEFAULT '[]',
                sources TEXT[] DEFAULT '{}',
                comment_count INTEGER DEFAULT 0,
                last_activity TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);

            CREATE TABLE IF NOT EXISTS comments (
                id SERIAL PRIMARY KEY,
                customer_id TEXT REFERENCES customers(customer_id) ON DELETE CASCADE,
                tenant_id TEXT DEFAULT '',
                media_id TEXT DEFAULT '',
                username TEXT DEFAULT '',
                text TEXT DEFAULT '',
                sentiment_score NUMERIC(5,3) DEFAULT 0,
                sentiment_label TEXT DEFAULT 'neutral',
                is_negative BOOLEAN DEFAULT FALSE,
                triggered_rule TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_comments_customer ON comments(customer_id);

            CREATE TABLE IF NOT EXISTS alerts (
                id SERIAL PRIMARY KEY,
                customer_id TEXT,
                type TEXT DEFAULT '',
                message TEXT DEFAULT '',
                severity TEXT DEFAULT 'info',
                source TEXT DEFAULT '',
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_alerts_customer ON alerts(customer_id);
        """)
        print("PostgreSQL schema initialized")

def get_pool():
    return pool
