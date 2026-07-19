-- InvestIQ Phase 5b: Row Level Security policies for research_reports
-- Run in Supabase SQL Editor after 001_research_reports.sql
--
-- The backend uses SUPABASE_ANON_KEY. Without these policies, inserts fail with:
--   "new row violates row-level security policy for table research_reports" (42501)

ALTER TABLE research_reports ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "investiq_anon_select" ON research_reports;
DROP POLICY IF EXISTS "investiq_anon_insert" ON research_reports;
DROP POLICY IF EXISTS "investiq_anon_delete" ON research_reports;

-- MVP / development: allow the anon key used by the FastAPI backend.
-- Tighten these policies when you add authenticated users.
CREATE POLICY "investiq_anon_select"
    ON research_reports
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "investiq_anon_insert"
    ON research_reports
    FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY "investiq_anon_delete"
    ON research_reports
    FOR DELETE
    TO anon
    USING (true);
