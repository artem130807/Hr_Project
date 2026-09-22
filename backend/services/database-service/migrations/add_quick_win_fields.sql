-- Additive fields for the 2026-09 hiring workflow quick-win package.
-- Safe to run repeatedly on PostgreSQL.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'candidatestatus') THEN
        ALTER TYPE candidatestatus ADD VALUE IF NOT EXISTS 'оффер принят';
    END IF;
END
$$;

ALTER TABLE employee_requests
    ADD COLUMN IF NOT EXISTS work_address VARCHAR(500),
    ADD COLUMN IF NOT EXISTS background_search BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE vacancies
    ADD COLUMN IF NOT EXISTS work_address VARCHAR(500),
    ADD COLUMN IF NOT EXISTS is_internal_hidden BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE candidates
    ADD COLUMN IF NOT EXISTS next_contact_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS next_contact_owner_id VARCHAR(36),
    ADD COLUMN IF NOT EXISTS next_contact_owner_name VARCHAR(200);

CREATE INDEX IF NOT EXISTS ix_candidates_next_contact_at
    ON candidates (next_contact_at);
