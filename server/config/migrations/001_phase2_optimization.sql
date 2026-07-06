-- Phase 2: PostgreSQL Optimization & Data Layer Foundation
-- All changes are backward-compatible (new tables, indexes, extensions, views only)
-- No existing tables, columns, or constraints are modified

-- ============================================================
-- 1. pg_trgm Extension (for efficient ILIKE search)
-- ============================================================
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- 2. New Indexes on Existing Tables
-- ============================================================

-- Composite index for profile builder GROUP BY + source filter
CREATE INDEX IF NOT EXISTS idx_raw_orders_phone_source
    ON raw_orders(phone, source);

-- Composite index for dashboard sort (most recent first)
CREATE INDEX IF NOT EXISTS idx_customers_phone_activity
    ON customers(phone, last_activity DESC);

-- Composite index for customer comment retrieval
CREATE INDEX IF NOT EXISTS idx_comments_customer_created
    ON comments(customer_id, created_at DESC);

-- Index for profile builder Billzzy transaction join by customer_id
CREATE INDEX IF NOT EXISTS idx_bill_tx_customer
    ON bill_transactions(customer_id);

-- Composite index for customer alert retrieval
CREATE INDEX IF NOT EXISTS idx_alerts_customer_created
    ON alerts(customer_id, created_at DESC);

-- GIN trigram indexes for ILIKE search on customers
CREATE INDEX IF NOT EXISTS idx_customers_name_trgm
    ON customers USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_customers_email_trgm
    ON customers USING GIN (email gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_customers_phone_trgm
    ON customers USING GIN (phone gin_trgm_ops);

-- ============================================================
-- 3. Customer Features Table (for AI feature vectors)
-- ============================================================
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

-- ============================================================
-- 4. Recommendations Table (for AI recommendation storage)
-- ============================================================
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

-- ============================================================
-- 5. Customer Segments Table (for deterministic segment membership)
-- ============================================================
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

-- ============================================================
-- 6. Dirty Phones Queue (for incremental processing)
-- ============================================================
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

-- ============================================================
-- 7. Audit Log Table (for change tracking)
-- ============================================================
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

-- ============================================================
-- 8. Materialized Views for Analytics Performance
-- ============================================================

-- Dashboard summary (single row aggregate)
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

-- Revenue by source
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

-- Customer spend distribution buckets
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
