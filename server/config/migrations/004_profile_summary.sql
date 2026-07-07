-- ============================================================
-- Phase 8: AI-Powered Profile Summarization
-- Migration 004
-- ============================================================
-- Applied at: 2026-07-07
-- Description:
--   - Adds profile_summary column to customers table
--   - Enables AI-generated natural language summaries
-- ============================================================

ALTER TABLE customers ADD COLUMN IF NOT EXISTS profile_summary TEXT DEFAULT '';

-- ============================================================
-- Rollback:
--   ALTER TABLE customers DROP COLUMN IF EXISTS profile_summary;
-- ============================================================
