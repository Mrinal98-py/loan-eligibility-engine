-- Migration 002: Performance indexes for high-throughput candidate pre-filtering
CREATE INDEX IF NOT EXISTS idx_users_import_id ON users (import_id);
CREATE INDEX IF NOT EXISTS idx_users_matching_composite ON users (import_id, monthly_income, credit_score, age, employment_status);

CREATE INDEX IF NOT EXISTS idx_products_active ON loan_products (is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_products_matching ON loan_products (is_active, min_monthly_income, min_credit_score, min_age, max_age);

CREATE INDEX IF NOT EXISTS idx_matches_import_id ON matches (import_id);
CREATE INDEX IF NOT EXISTS idx_matches_user_id ON matches (user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_import_status ON notifications (import_id, status);
