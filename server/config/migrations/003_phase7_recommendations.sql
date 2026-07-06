ALTER TABLE recommendations
  ADD COLUMN IF NOT EXISTS recommended_action TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS expected_business_impact TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS source_model TEXT DEFAULT 'rule_engine';

CREATE INDEX IF NOT EXISTS idx_recommendations_status_priority
  ON recommendations(status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_recommendations_customer_status
  ON recommendations(customer_id, status);
CREATE INDEX IF NOT EXISTS idx_recommendations_expires
  ON recommendations(expires_at) WHERE status = 'active';
