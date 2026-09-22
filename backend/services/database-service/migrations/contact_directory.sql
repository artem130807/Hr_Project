-- Employee/department contact directory and adaptation routing policy.
CREATE TABLE IF NOT EXISTS organization_departments (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL UNIQUE,
    lead_user_id VARCHAR(36),
    lead_name VARCHAR(200),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- migrate:split

CREATE TABLE IF NOT EXISTS contact_points (
    id SERIAL PRIMARY KEY,
    contact_type VARCHAR(24) NOT NULL CHECK (contact_type IN ('telegram','phone','email')),
    value VARCHAR(320) NOT NULL,
    normalized_value VARCHAR(320) NOT NULL,
    usage_type VARCHAR(24) NOT NULL CHECK (usage_type IN ('personal','work_personal','shared')),
    owner_type VARCHAR(24) NOT NULL CHECK (owner_type IN ('employee','department')),
    employee_id INTEGER REFERENCES employees(id) ON DELETE CASCADE,
    department_id INTEGER REFERENCES organization_departments(id) ON DELETE CASCADE,
    label VARCHAR(200),
    priority INTEGER NOT NULL DEFAULT 100,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    allow_adaptation BOOLEAN NOT NULL DEFAULT FALSE,
    telegram_chat_id VARCHAR(64),
    telegram_username VARCHAR(64),
    verified_at TIMESTAMPTZ,
    created_by VARCHAR(36),
    updated_by VARCHAR(36),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_contact_one_owner CHECK (
        (owner_type='employee' AND employee_id IS NOT NULL AND department_id IS NULL) OR
        (owner_type='department' AND department_id IS NOT NULL AND employee_id IS NULL)
    ),
    CONSTRAINT ck_department_contact_shared CHECK (owner_type <> 'department' OR usage_type='shared'),
    CONSTRAINT ck_contact_primary_employee CHECK (NOT is_primary OR owner_type='employee'),
    CONSTRAINT ck_contact_adaptation_target CHECK (
        NOT allow_adaptation OR (owner_type='employee' AND contact_type='telegram' AND usage_type <> 'shared')
    )
);
-- Make the migration safe after an earlier preview version of this table.
-- migrate:split
ALTER TABLE contact_points DROP CONSTRAINT IF EXISTS uq_contact_owner_value;
-- migrate:split
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_contact_primary_employee') THEN
        ALTER TABLE contact_points ADD CONSTRAINT ck_contact_primary_employee
            CHECK (NOT is_primary OR owner_type='employee');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_contact_adaptation_target') THEN
        ALTER TABLE contact_points ADD CONSTRAINT ck_contact_adaptation_target
            CHECK (NOT allow_adaptation OR (owner_type='employee' AND contact_type='telegram' AND usage_type <> 'shared'));
    END IF;
END $$;
-- migrate:split
CREATE INDEX IF NOT EXISTS ix_contact_lookup ON contact_points(contact_type, normalized_value);
-- migrate:split
CREATE INDEX IF NOT EXISTS ix_contact_employee_active ON contact_points(employee_id, is_active);
-- migrate:split
CREATE INDEX IF NOT EXISTS ix_contact_department_active ON contact_points(department_id, is_active);
-- migrate:split
CREATE UNIQUE INDEX IF NOT EXISTS uq_contact_personal_active
    ON contact_points(contact_type, normalized_value)
    WHERE is_active=TRUE AND usage_type <> 'shared';
-- migrate:split
CREATE UNIQUE INDEX IF NOT EXISTS uq_contact_department_active_value
    ON contact_points(department_id, contact_type, normalized_value)
    WHERE is_active=TRUE AND owner_type='department';
-- migrate:split
CREATE UNIQUE INDEX IF NOT EXISTS uq_contact_employee_primary
    ON contact_points(employee_id, contact_type, usage_type)
    WHERE employee_id IS NOT NULL AND is_primary=TRUE AND is_active=TRUE;

-- migrate:split
ALTER TABLE adaptation_enrollments
    ADD COLUMN IF NOT EXISTS responsible_hr_user_id VARCHAR(36),
    ADD COLUMN IF NOT EXISTS responsible_hr_name VARCHAR(200),
    ADD COLUMN IF NOT EXISTS allow_personal_telegram_fallback BOOLEAN;

-- migrate:split
ALTER TABLE adaptation_module_settings
    ADD COLUMN IF NOT EXISTS allow_personal_telegram_fallback BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS fallback_role VARCHAR(32) NOT NULL DEFAULT 'hr',
    ADD COLUMN IF NOT EXISTS manual_share_confirmation_hours INTEGER NOT NULL DEFAULT 24;

-- migrate:split
CREATE TABLE IF NOT EXISTS adaptation_routing_decisions (
    id SERIAL PRIMARY KEY,
    enrollment_id INTEGER NOT NULL REFERENCES adaptation_enrollments(id),
    checkpoint_id INTEGER REFERENCES adaptation_checkpoints(id),
    employee_id INTEGER REFERENCES employees(id),
    selected_contact_id INTEGER REFERENCES contact_points(id),
    resolved_recipient_type VARCHAR(32) NOT NULL,
    resolved_recipient_user_id VARCHAR(36),
    reason VARCHAR(64) NOT NULL,
    policy_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'resolved',
    decided_by VARCHAR(36),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- migrate:split
CREATE INDEX IF NOT EXISTS ix_adaptation_routing_enrollment ON adaptation_routing_decisions(enrollment_id, created_at DESC);
