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
            CREATE TABLE IF NOT EXISTS raw_orders (
                id SERIAL PRIMARY KEY,
                source TEXT NOT NULL,
                order_id TEXT NOT NULL,
                raw_data JSONB DEFAULT '{}',
                phone TEXT DEFAULT '',
                customer_name TEXT DEFAULT '',
                customer_id TEXT DEFAULT '',
                address TEXT DEFAULT '',
                customer_total_spent NUMERIC(12,2) DEFAULT 0,
                fetched_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(source, order_id)
            );
            CREATE INDEX IF NOT EXISTS idx_raw_orders_phone ON raw_orders(phone);
            CREATE INDEX IF NOT EXISTS idx_raw_orders_source ON raw_orders(source);

            CREATE TABLE IF NOT EXISTS bill_transactions (
                id SERIAL PRIMARY KEY,
                order_id TEXT NOT NULL UNIQUE,
                phone TEXT DEFAULT '',
                org_id TEXT DEFAULT '',
                org_name TEXT DEFAULT '',
                bill_id TEXT DEFAULT '',
                bill_no TEXT DEFAULT '',
                amount NUMERIC(12,2) DEFAULT 0,
                amount_paid NUMERIC(12,2) DEFAULT 0,
                balance NUMERIC(12,2) DEFAULT 0,
                billing_mode TEXT DEFAULT '',
                status TEXT DEFAULT '',
                payment_status TEXT DEFAULT '',
                date TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                customer_id TEXT DEFAULT '',
                address TEXT DEFAULT '',
                raw_transaction JSONB DEFAULT '{}',
                fetched_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_bill_tx_phone ON bill_transactions(phone);

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
                metadata JSONB DEFAULT '{}',
                stores JSONB DEFAULT '[]',
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);

            DO $$ BEGIN
                ALTER TABLE customers ADD COLUMN IF NOT EXISTS stores JSONB DEFAULT '[]';
            EXCEPTION WHEN others THEN null;
            END $$;

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
