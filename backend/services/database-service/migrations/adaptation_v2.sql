-- Full adaptation lifecycle (ADAPT01-ADAPT16). Additive and idempotent.
-- ERP identities are UUID strings; legacy installations may still use INTEGER.
ALTER TABLE IF EXISTS audit_logs
    ALTER COLUMN actor_id TYPE VARCHAR(36) USING actor_id::text;
ALTER TABLE IF EXISTS candidate_stage_history
    ALTER COLUMN actor_id TYPE VARCHAR(36) USING actor_id::text;

CREATE TABLE IF NOT EXISTS temporary_employees (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(200) NOT NULL,
    position VARCHAR(200) NOT NULL,
    department VARCHAR(200) NOT NULL,
    start_date DATE NOT NULL,
    manager_user_id VARCHAR(36),
    manager_name VARCHAR(200),
    photo_url TEXT,
    link_status VARCHAR(32) NOT NULL DEFAULT 'unlinked',
    linked_employee_id INTEGER REFERENCES employees(id),
    linked_at TIMESTAMPTZ,
    linked_by VARCHAR(36),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE adaptation_enrollments DROP CONSTRAINT IF EXISTS adaptation_enrollments_employee_id_key;
ALTER TABLE adaptation_enrollments ALTER COLUMN employee_id DROP NOT NULL;
ALTER TABLE adaptation_enrollments
    ADD COLUMN IF NOT EXISTS temporary_employee_id INTEGER REFERENCES temporary_employees(id),
    ADD COLUMN IF NOT EXISTS previous_enrollment_id INTEGER REFERENCES adaptation_enrollments(id),
    ADD COLUMN IF NOT EXISTS start_date DATE,
    ADD COLUMN IF NOT EXISTS route VARCHAR(32) NOT NULL DEFAULT 'full',
    ADD COLUMN IF NOT EXISTS manager_user_id VARCHAR(36),
    ADD COLUMN IF NOT EXISTS manager_name VARCHAR(200),
    ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS archive_reason TEXT,
    ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS finalized_by VARCHAR(36),
    ADD COLUMN IF NOT EXISTS outcome VARCHAR(32),
    ADD COLUMN IF NOT EXISTS risk VARCHAR(32),
    ADD COLUMN IF NOT EXISTS decision_comment TEXT,
    ADD COLUMN IF NOT EXISTS hiring_request_id INTEGER REFERENCES employee_requests(id),
    ADD COLUMN IF NOT EXISTS quota_credited_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS quota_credited_by VARCHAR(36);
UPDATE adaptation_enrollments ae
SET start_date = e.date_hired
FROM employees e
WHERE ae.employee_id = e.id AND ae.start_date IS NULL;
UPDATE adaptation_enrollments SET start_date = CURRENT_DATE WHERE start_date IS NULL;
ALTER TABLE adaptation_enrollments ALTER COLUMN start_date SET NOT NULL;

ALTER TABLE adaptation_checkpoints
    ADD COLUMN IF NOT EXISTS original_plan_date DATE,
    ADD COLUMN IF NOT EXISTS rescheduled_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS rescheduled_by VARCHAR(36),
    ADD COLUMN IF NOT EXISTS reschedule_reason TEXT,
    ADD COLUMN IF NOT EXISTS draft_ready_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS forced_completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS forced_completed_by VARCHAR(36),
    ADD COLUMN IF NOT EXISTS forced_reason TEXT,
    ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS finalized_by VARCHAR(36),
    ADD COLUMN IF NOT EXISTS risk_override VARCHAR(32),
    ADD COLUMN IF NOT EXISTS outcome_override VARCHAR(32),
    ADD COLUMN IF NOT EXISTS override_comment TEXT;
UPDATE adaptation_checkpoints SET original_plan_date = plan_date WHERE original_plan_date IS NULL;

ALTER TABLE adaptation_answers
    ADD COLUMN IF NOT EXISTS actor_user_id VARCHAR(36),
    ADD COLUMN IF NOT EXISTS actor_name VARCHAR(200),
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS locked BOOLEAN NOT NULL DEFAULT TRUE;

CREATE TABLE IF NOT EXISTS adaptation_answer_versions (
    id SERIAL PRIMARY KEY,
    answer_id INTEGER NOT NULL REFERENCES adaptation_answers(id),
    version INTEGER NOT NULL,
    payload JSON NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL,
    actor_user_id VARCHAR(36),
    actor_name VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_adaptation_answer_version UNIQUE(answer_id, version)
);

CREATE TABLE IF NOT EXISTS adaptation_action_records (
    id SERIAL PRIMARY KEY,
    enrollment_id INTEGER NOT NULL REFERENCES adaptation_enrollments(id),
    source_checkpoint_id INTEGER REFERENCES adaptation_checkpoints(id),
    action TEXT NOT NULL,
    owner_user_id VARCHAR(36),
    owner_name VARCHAR(200),
    due_date DATE,
    status VARCHAR(32) NOT NULL DEFAULT 'planned',
    effect TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS adaptation_participant_forms (
    id SERIAL PRIMARY KEY,
    checkpoint_id INTEGER NOT NULL REFERENCES adaptation_checkpoints(id),
    role VARCHAR(16) NOT NULL,
    participant_user_id VARCHAR(36),
    token VARCHAR(96) NOT NULL UNIQUE,
    sent_at TIMESTAMPTZ,
    submitted_at TIMESTAMPTZ,
    locked BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_adaptation_form_role UNIQUE(checkpoint_id, role)
);

CREATE TABLE IF NOT EXISTS adaptation_notification_templates (
    id SERIAL PRIMARY KEY,
    audience VARCHAR(16) NOT NULL,
    event VARCHAR(48) NOT NULL,
    text TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_adaptation_template_audience_event UNIQUE(audience, event)
);

CREATE TABLE IF NOT EXISTS adaptation_notification_deliveries (
    id SERIAL PRIMARY KEY,
    checkpoint_id INTEGER NOT NULL REFERENCES adaptation_checkpoints(id),
    role VARCHAR(16) NOT NULL,
    event VARCHAR(48) NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    sent_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_adaptation_delivery_event UNIQUE(checkpoint_id, role, event)
);

CREATE TABLE IF NOT EXISTS adaptation_report_documents (
    id SERIAL PRIMARY KEY,
    checkpoint_id INTEGER REFERENCES adaptation_checkpoints(id),
    enrollment_id INTEGER NOT NULL REFERENCES adaptation_enrollments(id),
    document_type VARCHAR(48) NOT NULL,
    format VARCHAR(8) NOT NULL,
    version INTEGER NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    content BYTEA NOT NULL,
    content_sha256 VARCHAR(64) NOT NULL,
    generation_key VARCHAR(80) UNIQUE,
    is_final BOOLEAN NOT NULL DEFAULT FALSE,
    created_by VARCHAR(36),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_adaptation_document_version UNIQUE(checkpoint_id, document_type, format, version)
);

CREATE TABLE IF NOT EXISTS adaptation_module_settings (
    id SERIAL PRIMARY KEY,
    overdue_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    overdue_time TIME NOT NULL DEFAULT '09:00',
    timezone VARCHAR(64) NOT NULL DEFAULT 'Europe/Samara',
    visible_columns JSON NOT NULL DEFAULT '[]',
    show_photo BOOLEAN NOT NULL DEFAULT TRUE,
    file_name_templates JSON NOT NULL DEFAULT '{}',
    signature_roles JSON NOT NULL DEFAULT '["HR", "Руководитель", "Директор"]',
    risk_rules JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_adaptation_enrollments_start_date ON adaptation_enrollments(start_date);
CREATE INDEX IF NOT EXISTS ix_adaptation_enrollments_active ON adaptation_enrollments(archived, closed);
CREATE INDEX IF NOT EXISTS ix_adaptation_enrollments_manager ON adaptation_enrollments(manager_user_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_adaptation_active_employee
    ON adaptation_enrollments(employee_id)
    WHERE employee_id IS NOT NULL AND closed = FALSE AND archived = FALSE;
CREATE INDEX IF NOT EXISTS ix_adaptation_action_records_enrollment ON adaptation_action_records(enrollment_id);
CREATE INDEX IF NOT EXISTS ix_adaptation_forms_checkpoint ON adaptation_participant_forms(checkpoint_id);
CREATE INDEX IF NOT EXISTS ix_adaptation_delivery_due ON adaptation_notification_deliveries(status, scheduled_at);
CREATE INDEX IF NOT EXISTS ix_adaptation_documents_enrollment ON adaptation_report_documents(enrollment_id);
