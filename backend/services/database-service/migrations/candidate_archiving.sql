-- Soft deletion for candidates. Recruitment, testing and hiring history remains linked.
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
-- migrate:split
CREATE INDEX IF NOT EXISTS ix_candidates_archived_at ON candidates(archived_at);
