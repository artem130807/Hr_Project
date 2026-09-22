-- Replace local panel-user foreign keys with ERP UUID strings.
-- Review rows whose erp_user_id is NULL before running: referenced IDs cannot
-- be translated to ERP UUIDs and will remain as their legacy numeric strings.

BEGIN;

CREATE TEMP TABLE _web_admin_user_erp_map ON COMMIT DROP AS
SELECT id AS local_id, erp_user_id, department, negotations_processing
FROM web_admin_panel_users;

-- Drop every FK that targets the local panel-user table. Constraint names may
-- differ between installations, so discover them from the PostgreSQL catalog.
DO $$
DECLARE
    fk RECORD;
BEGIN
    FOR fk IN
        SELECT conrelid::regclass AS table_name, conname
        FROM pg_constraint
        WHERE contype = 'f'
          AND confrelid = 'web_admin_panel_users'::regclass
    LOOP
        EXECUTE format(
            'ALTER TABLE %s DROP CONSTRAINT %I',
            fk.table_name,
            fk.conname
        );
    END LOOP;
END
$$;

ALTER TABLE department_candidate_images
    ALTER COLUMN lead_id TYPE VARCHAR(36) USING lead_id::text,
    ADD COLUMN department departments NULL;
ALTER TABLE company_contacts
    ALTER COLUMN hr_id TYPE VARCHAR(36) USING hr_id::text;
ALTER TABLE approvals
    ALTER COLUMN approver_id TYPE VARCHAR(36) USING approver_id::text;
ALTER TABLE hr_availability
    ALTER COLUMN hr_id TYPE VARCHAR(36) USING hr_id::text;
ALTER TABLE audit_logs
    ALTER COLUMN actor_id TYPE VARCHAR(36) USING actor_id::text;
ALTER TABLE candidate_stage_history
    ALTER COLUMN actor_id TYPE VARCHAR(36) USING actor_id::text;
ALTER TABLE candidate_comments
    ALTER COLUMN author_id TYPE VARCHAR(36) USING author_id::text;
ALTER TABLE tokens
    ALTER COLUMN entity_id TYPE VARCHAR(64) USING entity_id::text;

UPDATE department_candidate_images image
SET lead_id = mapping.erp_user_id,
    department = mapping.department
FROM _web_admin_user_erp_map mapping
WHERE image.lead_id = mapping.local_id::text
  AND mapping.erp_user_id IS NOT NULL;

UPDATE company_contacts contact
SET hr_id = mapping.erp_user_id
FROM _web_admin_user_erp_map mapping
WHERE contact.hr_id = mapping.local_id::text
  AND mapping.erp_user_id IS NOT NULL;

UPDATE approvals approval
SET approver_id = mapping.erp_user_id
FROM _web_admin_user_erp_map mapping
WHERE approval.approver_id = mapping.local_id::text
  AND mapping.erp_user_id IS NOT NULL;

UPDATE hr_availability availability
SET hr_id = mapping.erp_user_id
FROM _web_admin_user_erp_map mapping
WHERE availability.hr_id = mapping.local_id::text
  AND mapping.erp_user_id IS NOT NULL;

UPDATE audit_logs audit
SET actor_id = mapping.erp_user_id
FROM _web_admin_user_erp_map mapping
WHERE audit.actor_id = mapping.local_id::text
  AND mapping.erp_user_id IS NOT NULL;

UPDATE candidate_stage_history history
SET actor_id = mapping.erp_user_id
FROM _web_admin_user_erp_map mapping
WHERE history.actor_id = mapping.local_id::text
  AND mapping.erp_user_id IS NOT NULL;

UPDATE candidate_comments comment
SET author_id = mapping.erp_user_id
FROM _web_admin_user_erp_map mapping
WHERE comment.author_id = mapping.local_id::text
  AND mapping.erp_user_id IS NOT NULL;

CREATE TABLE hr_negotiation_flags (
    erp_user_id VARCHAR(36) PRIMARY KEY,
    negotations_processing BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
);

INSERT INTO hr_negotiation_flags (erp_user_id, negotations_processing)
SELECT erp_user_id, COALESCE(negotations_processing, FALSE)
FROM _web_admin_user_erp_map
WHERE erp_user_id IS NOT NULL
ON CONFLICT (erp_user_id) DO UPDATE
SET negotations_processing = EXCLUDED.negotations_processing;

DROP TABLE refresh_tokens;
DROP TABLE web_admin_panel_users;

COMMIT;
