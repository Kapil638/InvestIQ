-- InvestIQ: Row Level Security policies for app_users / webauthn_credentials
-- Run in Supabase SQL Editor after 004_users_and_credentials.sql
--
-- The backend uses SUPABASE_ANON_KEY. Without these policies, inserts fail with:
--   "new row violates row-level security policy for table app_users" (42501)

ALTER TABLE app_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE webauthn_credentials ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "investiq_anon_select" ON app_users;
DROP POLICY IF EXISTS "investiq_anon_insert" ON app_users;
DROP POLICY IF EXISTS "investiq_anon_update" ON app_users;

DROP POLICY IF EXISTS "investiq_anon_select" ON webauthn_credentials;
DROP POLICY IF EXISTS "investiq_anon_insert" ON webauthn_credentials;
DROP POLICY IF EXISTS "investiq_anon_update" ON webauthn_credentials;

-- MVP / development: allow the anon key used by the FastAPI backend.
-- Tighten these policies if this ever moves beyond a single-owner gate.
CREATE POLICY "investiq_anon_select"
    ON app_users
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "investiq_anon_insert"
    ON app_users
    FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY "investiq_anon_update"
    ON app_users
    FOR UPDATE
    TO anon
    USING (true)
    WITH CHECK (true);

CREATE POLICY "investiq_anon_select"
    ON webauthn_credentials
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "investiq_anon_insert"
    ON webauthn_credentials
    FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY "investiq_anon_update"
    ON webauthn_credentials
    FOR UPDATE
    TO anon
    USING (true)
    WITH CHECK (true);
