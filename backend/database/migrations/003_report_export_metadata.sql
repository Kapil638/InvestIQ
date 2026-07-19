-- Report PDF export and Google Drive metadata
-- Run in Supabase SQL Editor when upgrading existing deployments.

ALTER TABLE research_reports
    ADD COLUMN IF NOT EXISTS pdf_generated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS google_drive_file_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS google_drive_url TEXT,
    ADD COLUMN IF NOT EXISTS google_drive_saved_at TIMESTAMPTZ;
