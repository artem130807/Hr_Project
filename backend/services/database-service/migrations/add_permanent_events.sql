-- Permanent HR events: recurrence + Huey dispatch bookkeeping.
ALTER TABLE events ADD COLUMN IF NOT EXISTS repeat_interval_count INTEGER;
ALTER TABLE events ADD COLUMN IF NOT EXISTS repeat_interval_unit VARCHAR(16);
ALTER TABLE events ADD COLUMN IF NOT EXISTS last_dispatched_at TIMESTAMPTZ;
ALTER TABLE events ADD COLUMN IF NOT EXISTS next_dispatch_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS ix_events_next_dispatch_at ON events (next_dispatch_at);
