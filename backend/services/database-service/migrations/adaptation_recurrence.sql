-- Apply before deploying code using recurrence metadata.
ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS series_key VARCHAR(64);
ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS recurrence_rule JSON;
CREATE INDEX IF NOT EXISTS ix_adaptation_series
ON adaptation_checkpoints (enrollment_id, series_key);
