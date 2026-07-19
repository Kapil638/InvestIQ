-- InvestIQ Phase 5: research reports table for Supabase PostgreSQL
-- Run this in the Supabase SQL Editor (Dashboard → SQL → New query)

CREATE TABLE IF NOT EXISTS research_reports (
    id UUID PRIMARY KEY,
    ticker VARCHAR(16) NOT NULL,
    company_name VARCHAR(255),
    rating VARCHAR(32),
    confidence_score DECIMAL(5, 2),
    guardrails_passed BOOLEAN NOT NULL DEFAULT FALSE,
    generated_at TIMESTAMPTZ NOT NULL,
    report_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_research_reports_ticker
    ON research_reports (ticker);

CREATE INDEX IF NOT EXISTS idx_research_reports_generated_at
    ON research_reports (generated_at DESC);

CREATE INDEX IF NOT EXISTS idx_research_reports_rating
    ON research_reports (rating);

-- Optional: enable Row Level Security (adjust policies for your auth model)
-- ALTER TABLE research_reports ENABLE ROW LEVEL SECURITY;
