import asyncio
import asyncpg
from config.settings import DATABASE_URL, DB_POOL_MIN_SIZE, DB_POOL_MAX_SIZE, DB_POOL_MAX_INACTIVE_CONNECTION_LIFETIME

pool = None

async def connect(retries=10, delay=3):
    global pool
    for attempt in range(1, retries + 1):
        try:
            pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=DB_POOL_MIN_SIZE,
                max_size=DB_POOL_MAX_SIZE,
                max_inactive_connection_lifetime=DB_POOL_MAX_INACTIVE_CONNECTION_LIFETIME,
            )
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

        # Phase 2: Performance optimizations (backward-compatible additions)
        await conn.execute("""
            CREATE EXTENSION IF NOT EXISTS pg_trgm;

            CREATE INDEX IF NOT EXISTS idx_raw_orders_phone_source ON raw_orders(phone, source);
            CREATE INDEX IF NOT EXISTS idx_customers_phone_activity ON customers(phone, last_activity DESC);
            CREATE INDEX IF NOT EXISTS idx_comments_customer_created ON comments(customer_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_bill_tx_customer ON bill_transactions(customer_id);
            CREATE INDEX IF NOT EXISTS idx_alerts_customer_created ON alerts(customer_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_customers_name_trgm ON customers USING GIN (name gin_trgm_ops);
            CREATE INDEX IF NOT EXISTS idx_customers_email_trgm ON customers USING GIN (email gin_trgm_ops);
            CREATE INDEX IF NOT EXISTS idx_customers_phone_trgm ON customers USING GIN (phone gin_trgm_ops);

            CREATE TABLE IF NOT EXISTS customer_features (
                customer_id TEXT PRIMARY KEY REFERENCES customers(customer_id) ON DELETE CASCADE,
                feature_version INTEGER DEFAULT 1,
                lifetime_value NUMERIC(12,2) DEFAULT 0,
                purchase_frequency NUMERIC(10,4) DEFAULT 0,
                average_order_value NUMERIC(12,2) DEFAULT 0,
                churn_probability NUMERIC(5,4) DEFAULT 0,
                loyalty_score NUMERIC(5,2) DEFAULT 0,
                return_rate NUMERIC(5,4) DEFAULT 0,
                payment_health_score NUMERIC(5,2) DEFAULT 0,
                days_since_last_activity INTEGER DEFAULT 0,
                total_orders_30d INTEGER DEFAULT 0,
                total_orders_90d INTEGER DEFAULT 0,
                total_spent_30d NUMERIC(12,2) DEFAULT 0,
                total_spent_90d NUMERIC(12,2) DEFAULT 0,
                features_snapshot JSONB DEFAULT '{}',
                computed_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS recommendations (
                id SERIAL PRIMARY KEY,
                customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
                recommendation_type TEXT NOT NULL DEFAULT '',
                title TEXT DEFAULT '',
                description TEXT DEFAULT '',
                confidence NUMERIC(5,4) DEFAULT 0,
                priority TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'active',
                metadata JSONB DEFAULT '{}',
                feature_snapshot JSONB DEFAULT '{}',
                expires_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_rec_customer ON recommendations(customer_id);
            CREATE INDEX IF NOT EXISTS idx_rec_status ON recommendations(status);
            CREATE INDEX IF NOT EXISTS idx_rec_priority ON recommendations(priority);
            CREATE INDEX IF NOT EXISTS idx_rec_expires ON recommendations(expires_at);
            CREATE INDEX IF NOT EXISTS idx_rec_customer_status ON recommendations(customer_id, status);

            CREATE TABLE IF NOT EXISTS customer_segments (
                id SERIAL PRIMARY KEY,
                customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
                segment TEXT NOT NULL,
                segment_source TEXT DEFAULT 'rule',
                is_active BOOLEAN DEFAULT TRUE,
                activated_at TIMESTAMPTZ DEFAULT NOW(),
                deactivated_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(customer_id, segment)
            );
            CREATE INDEX IF NOT EXISTS idx_seg_customer ON customer_segments(customer_id);
            CREATE INDEX IF NOT EXISTS idx_seg_segment ON customer_segments(segment);
            CREATE INDEX IF NOT EXISTS idx_seg_active ON customer_segments(is_active) WHERE is_active = TRUE;

            CREATE TABLE IF NOT EXISTS dirty_phones (
                id SERIAL PRIMARY KEY,
                phone TEXT NOT NULL,
                reason TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                worker_id TEXT DEFAULT '',
                priority INTEGER DEFAULT 0,
                attempts INTEGER DEFAULT 0,
                last_error TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                claimed_at TIMESTAMPTZ,
                processed_at TIMESTAMPTZ
            );
            CREATE INDEX IF NOT EXISTS idx_dirty_status ON dirty_phones(status);
            CREATE INDEX IF NOT EXISTS idx_dirty_phone ON dirty_phones(phone);
            CREATE INDEX IF NOT EXISTS idx_dirty_pending ON dirty_phones(priority, created_at) WHERE status = 'pending';

            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                action TEXT NOT NULL,
                changed_fields TEXT[] DEFAULT '{}',
                old_values JSONB DEFAULT '{}',
                new_values JSONB DEFAULT '{}',
                performed_by TEXT DEFAULT 'system',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
            CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
            CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);

            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_dashboard_summary AS
            SELECT
                COUNT(*) AS total_customers,
                COALESCE(SUM(total_orders), 0) AS total_orders,
                COALESCE(SUM(total_bills), 0) AS total_bills,
                COALESCE(SUM(total_spent), 0) AS total_revenue,
                COALESCE(AVG(total_spent), 0) AS avg_revenue_per_customer,
                COALESCE(SUM(comment_count), 0) AS total_comments,
                COUNT(*) FILTER (WHERE array_length(sources, 1) > 1) AS multi_source_customers,
                (SELECT COUNT(*) FROM alerts WHERE severity = 'warning') AS active_alerts
            FROM customers;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_dashboard_summary ON mv_dashboard_summary((true));

            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_revenue_by_source AS
            SELECT
                unnest(sources) AS source,
                COUNT(*) AS customer_count,
                COALESCE(SUM(total_spent), 0) AS total_revenue,
                COALESCE(AVG(total_spent), 0) AS avg_revenue
            FROM customers
            GROUP BY source
            ORDER BY total_revenue DESC;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_revenue_source ON mv_revenue_by_source(source);

            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_customer_spend_buckets AS
            SELECT
                CASE
                    WHEN total_spent = 0 THEN '₹0'
                    WHEN total_spent <= 1000 THEN '₹1-1K'
                    WHEN total_spent <= 5000 THEN '₹1K-5K'
                    WHEN total_spent <= 20000 THEN '₹5K-20K'
                    WHEN total_spent <= 50000 THEN '₹20K-50K'
                    ELSE '₹50K+'
                END AS bucket,
                COUNT(*) AS customer_count,
                COALESCE(SUM(total_spent), 0) AS total_revenue
            FROM customers
            GROUP BY bucket
            ORDER BY MIN(total_spent);
        """)

        # Phase 5: Event-driven processing (backward-compatible additions)
        await conn.execute("""
            ALTER TABLE customers ADD COLUMN IF NOT EXISTS needs_analysis BOOLEAN DEFAULT FALSE;
            CREATE INDEX IF NOT EXISTS idx_cust_needs_analysis ON customers(needs_analysis);
        """)

        # Phase 7: AI Recommendation Engine (backward-compatible additions)
        await conn.execute("""
            ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS recommended_action TEXT DEFAULT '';
            ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS expected_business_impact TEXT DEFAULT '';
            ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS source_model TEXT DEFAULT '';
        """)
        print("PostgreSQL schema initialized (Phase 2 additions applied)")

def get_pool():
    return pool
