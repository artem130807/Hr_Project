-- Additive workflow and append-only history for manager hiring requests.
ALTER TABLE employee_requests ADD COLUMN IF NOT EXISTS assigned_hr_id VARCHAR(36);
-- migrate:split
ALTER TABLE employee_requests ADD COLUMN IF NOT EXISTS assigned_hr_name VARCHAR(200);
-- migrate:split
ALTER TABLE employee_requests ADD COLUMN IF NOT EXISTS return_comment TEXT;
-- migrate:split
ALTER TABLE employee_requests ADD COLUMN IF NOT EXISTS close_reason TEXT;
-- migrate:split
ALTER TABLE employee_requests ADD COLUMN IF NOT EXISTS cancel_reason TEXT;
-- migrate:split
CREATE TABLE IF NOT EXISTS hiring_request_history (
    id SERIAL PRIMARY KEY,
    hiring_request_id INTEGER NOT NULL REFERENCES employee_requests(id) ON DELETE RESTRICT,
    event_type VARCHAR(40) NOT NULL,
    from_status VARCHAR(120),
    to_status VARCHAR(120),
    comment TEXT,
    changes JSON,
    actor_id VARCHAR(36),
    actor_name VARCHAR(200),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
-- migrate:split
CREATE INDEX IF NOT EXISTS ix_hiring_request_history_request_id
    ON hiring_request_history(hiring_request_id);
