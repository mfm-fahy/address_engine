-- ============================================================
-- Phase 5: Data Ingestion Pipeline & Event-Driven Processing
-- Migration 002
-- ============================================================
-- Applied at: 2026-07-06
-- Description:
--   - Adds needs_analysis flag to customers table
--   - Enables event-driven processing workflow
-- ============================================================

-- Step 1: Add needs_analysis column (idempotent)
ALTER TABLE customers ADD COLUMN IF NOT EXISTS needs_analysis BOOLEAN DEFAULT FALSE;

-- Step 2: Index for efficient querying of pending analysis customers
CREATE INDEX IF NOT EXISTS idx_cust_needs_analysis ON customers(needs_analysis);

-- ============================================================
-- Rollback:
--   DROP INDEX IF EXISTS idx_cust_needs_analysis;
--   ALTER TABLE customers DROP COLUMN IF EXISTS needs_analysis;
-- ============================================================
