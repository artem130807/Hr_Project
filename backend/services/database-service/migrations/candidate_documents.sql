-- Private candidate employment-document packages and one-time public invites.
CREATE TABLE IF NOT EXISTS candidate_document_invites (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_by VARCHAR(36),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- migrate:split
CREATE INDEX IF NOT EXISTS ix_candidate_document_invites_candidate_id ON candidate_document_invites(candidate_id);
-- migrate:split
CREATE INDEX IF NOT EXISTS ix_candidate_document_invites_expires_at ON candidate_document_invites(expires_at);
-- migrate:split
CREATE UNIQUE INDEX IF NOT EXISTS uq_candidate_document_invites_open
ON candidate_document_invites(candidate_id)
WHERE used_at IS NULL AND revoked_at IS NULL;
-- migrate:split
CREATE TABLE IF NOT EXISTS candidate_docs (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER NOT NULL UNIQUE REFERENCES candidates(id) ON DELETE CASCADE,
    s3_prefix VARCHAR(500) NOT NULL,
    manifest JSONB NOT NULL DEFAULT '[]'::jsonb,
    submitted_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted','complete')),
    reviewed_at TIMESTAMPTZ,
    reviewed_by VARCHAR(36),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- migrate:split
CREATE INDEX IF NOT EXISTS ix_candidate_docs_status ON candidate_docs(status);
-- migrate:split
CREATE TABLE IF NOT EXISTS candidate_document_upload_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(32) NOT NULL UNIQUE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    invite_id INTEGER NOT NULL REFERENCES candidate_document_invites(id) ON DELETE CASCADE,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    status VARCHAR(16) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','submitted','expired')),
    expires_at TIMESTAMPTZ NOT NULL,
    submitted_at TIMESTAMPTZ,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
-- migrate:split
CREATE INDEX IF NOT EXISTS ix_candidate_document_upload_sessions_candidate ON candidate_document_upload_sessions(candidate_id);
-- migrate:split
CREATE INDEX IF NOT EXISTS ix_candidate_document_upload_sessions_expires ON candidate_document_upload_sessions(status, expires_at);
-- migrate:split
CREATE TABLE IF NOT EXISTS candidate_document_upload_files (
    id SERIAL PRIMARY KEY,
    file_id VARCHAR(32) NOT NULL UNIQUE,
    session_id INTEGER NOT NULL REFERENCES candidate_document_upload_sessions(id) ON DELETE CASCADE,
    document_type VARCHAR(48) NOT NULL,
    s3_key VARCHAR(700) NOT NULL UNIQUE,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    size INTEGER NOT NULL CHECK (size > 0),
    status VARCHAR(16) NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded','submitted')),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
-- migrate:split
CREATE INDEX IF NOT EXISTS ix_candidate_document_upload_files_session ON candidate_document_upload_files(session_id);
