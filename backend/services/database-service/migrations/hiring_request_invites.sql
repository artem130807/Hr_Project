-- One-time public links for creating hiring requests.
CREATE TABLE IF NOT EXISTS hiring_request_invites (
    id SERIAL PRIMARY KEY,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_by VARCHAR(36),
    created_by_name VARCHAR(200),
    hiring_request_id INTEGER UNIQUE REFERENCES employee_requests(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- migrate:split
CREATE INDEX IF NOT EXISTS ix_hiring_request_invites_expires_at ON hiring_request_invites(expires_at);
-- migrate:split
CREATE INDEX IF NOT EXISTS ix_hiring_request_invites_hiring_request_id ON hiring_request_invites(hiring_request_id);
