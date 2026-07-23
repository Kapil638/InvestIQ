-- InvestIQ: Row Level Security policies for report_embeddings
-- Run in Supabase SQL Editor after 006_report_embeddings.sql
--
-- The backend uses SUPABASE_ANON_KEY. Without these policies, inserts fail with:
--   "new row violates row-level security policy for table report_embeddings" (42501)

ALTER TABLE report_embeddings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "investiq_anon_select" ON report_embeddings;
DROP POLICY IF EXISTS "investiq_anon_insert" ON report_embeddings;
DROP POLICY IF EXISTS "investiq_anon_delete" ON report_embeddings;

-- MVP / development: allow the anon key used by the FastAPI backend.
-- Tighten these policies if this ever moves beyond a single-owner gate.
CREATE POLICY "investiq_anon_select"
    ON report_embeddings
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "investiq_anon_insert"
    ON report_embeddings
    FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY "investiq_anon_delete"
    ON report_embeddings
    FOR DELETE
    TO anon
    USING (true);

-- RLS covers table access, but the similarity-search RPC function is a
-- separate grantable object - the anon role can't call it without this.
GRANT EXECUTE ON FUNCTION match_report_embeddings(vector, VARCHAR, INT) TO anon;
