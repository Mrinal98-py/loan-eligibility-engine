-- ==============================================================================
-- Loan Eligibility Engine - Complete Database Schema (PostgreSQL 14+)
-- ==============================================================================

-- Enable UUID generation extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Table 1: imports
-- Tracks CSV upload lifecycle: CREATED -> UPLOADED -> PROCESSING -> PROCESSED (or FAILED / PARTIAL_REJECTED)
CREATE TABLE IF NOT EXISTS imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    object_key VARCHAR(512) NOT NULL UNIQUE,
    original_filename VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'CREATED' 
        CHECK (status IN ('CREATED', 'UPLOADED', 'PROCESSING', 'PROCESSED', 'FAILED', 'PARTIAL_REJECTED')),
    file_hash VARCHAR(64),
    file_size_bytes BIGINT,
    total_rows INTEGER DEFAULT 0,
    accepted_rows INTEGER DEFAULT 0,
    rejected_rows INTEGER DEFAULT 0,
    error_summary JSONB DEFAULT '{}'::jsonb,
    matching_status VARCHAR(50) DEFAULT 'PENDING'
        CHECK (matching_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
    notification_status VARCHAR(50) DEFAULT 'PENDING'
        CHECK (notification_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    uploaded_at TIMESTAMPTZ,
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ
);

-- Table 2: users
-- Normalized user financial profiles ingested from validated CSV rows
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_user_id VARCHAR(128) NOT NULL,
    import_id UUID NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
    name VARCHAR(255),
    email VARCHAR(255) NOT NULL,
    monthly_income NUMERIC(14, 2) NOT NULL CHECK (monthly_income >= 0),
    credit_score INTEGER NOT NULL CHECK (credit_score BETWEEN 300 AND 900),
    employment_status VARCHAR(50) NOT NULL 
        CHECK (employment_status IN ('Salaried', 'Self-Employed', 'Business', 'Other')),
    age INTEGER NOT NULL CHECK (age BETWEEN 18 AND 120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_import_external_user UNIQUE (import_id, external_user_id)
);

-- Table 3: rejected_rows
-- Stores row-level rejection details without exposing sensitive logs
CREATE TABLE IF NOT EXISTS rejected_rows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_id UUID NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    external_user_id VARCHAR(128),
    rejection_reason VARCHAR(500) NOT NULL,
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 4: loan_products
-- Loan offers discovered from public bank portals with provenance
CREATE TABLE IF NOT EXISTS loan_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name VARCHAR(128) NOT NULL,
    source_url VARCHAR(512) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    product_type VARCHAR(100) NOT NULL DEFAULT 'Personal Loan',
    interest_rate_min NUMERIC(5, 2),
    interest_rate_max NUMERIC(5, 2),
    min_monthly_income NUMERIC(14, 2) DEFAULT 0,
    min_credit_score INTEGER DEFAULT 300,
    max_credit_score INTEGER,
    min_age INTEGER DEFAULT 18,
    max_age INTEGER DEFAULT 100,
    eligible_employment_statuses JSONB NOT NULL DEFAULT '["Salaried", "Self-Employed", "Business"]'::jsonb,
    eligibility_criteria_raw TEXT,
    eligibility_evidence JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    verified_at TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_source_product UNIQUE (source_url, product_name)
);

-- Table 5: matches
-- Persisted eligibility matches linking user, product, and import
CREATE TABLE IF NOT EXISTS matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES loan_products(id) ON DELETE CASCADE,
    import_id UUID NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
    rule_version VARCHAR(32) NOT NULL DEFAULT 'v1.0',
    match_score NUMERIC(5, 2) DEFAULT 100.0,
    match_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'CONFIRMED'
        CHECK (status IN ('CONFIRMED', 'INDETERMINATE', 'REJECTED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_product_import UNIQUE (user_id, product_id, import_id)
);

-- Table 6: notifications
-- Audit record of notification attempts, strictly isolating test recipients
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_id UUID NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    delivery_mode VARCHAR(20) NOT NULL DEFAULT 'test' CHECK (delivery_mode IN ('test', 'production')),
    test_recipient VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'QUEUED' 
        CHECK (status IN ('QUEUED', 'SENT', 'FAILED', 'SUPPRESSED')),
    provider_message_id VARCHAR(255),
    matched_products_count INTEGER NOT NULL DEFAULT 1,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 7: extraction_runs
-- Observability table for Workflow A crawling executions
CREATE TABLE IF NOT EXISTS extraction_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name VARCHAR(128) NOT NULL,
    source_url VARCHAR(512) NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('SUCCESS', 'PARTIAL', 'FAILED')),
    products_found INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    response_status_code INTEGER,
    duration_ms INTEGER,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Performance Indexes for Optimization Treasure Hunt & SQL Pre-Filter
CREATE INDEX IF NOT EXISTS idx_users_import_id ON users (import_id);
CREATE INDEX IF NOT EXISTS idx_users_matching_composite ON users (import_id, monthly_income, credit_score, age, employment_status);

CREATE INDEX IF NOT EXISTS idx_products_active ON loan_products (is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_products_matching ON loan_products (is_active, min_monthly_income, min_credit_score, min_age, max_age);

CREATE INDEX IF NOT EXISTS idx_matches_import_id ON matches (import_id);
CREATE INDEX IF NOT EXISTS idx_matches_user_id ON matches (user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_import_status ON notifications (import_id, status);
