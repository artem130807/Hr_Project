-- Soft deletion for HR employees. Business and adaptation history stays linked.
ALTER TABLE employees ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
-- migrate:split
CREATE INDEX IF NOT EXISTS ix_employees_archived_at ON employees(archived_at);
