-- ERP users are identified by UUID strings. Remove legacy foreign keys to the
-- deleted local users table before changing the old INTEGER columns.
DO $$
DECLARE
    fk RECORD;
BEGIN
    FOR fk IN
        SELECT constraint_row.conname
        FROM pg_constraint constraint_row
        JOIN pg_attribute attribute_row
          ON attribute_row.attrelid = constraint_row.conrelid
         AND attribute_row.attnum = ANY(constraint_row.conkey)
        WHERE constraint_row.contype = 'f'
          AND constraint_row.conrelid = 'audit_logs'::regclass
          AND attribute_row.attname = 'actor_id'
    LOOP
        EXECUTE format('ALTER TABLE audit_logs DROP CONSTRAINT %I', fk.conname);
    END LOOP;
END
$$;
-- migrate:split
ALTER TABLE audit_logs
    ALTER COLUMN actor_id TYPE VARCHAR(36) USING actor_id::text;
-- migrate:split
DO $$
DECLARE
    fk RECORD;
BEGIN
    FOR fk IN
        SELECT constraint_row.conname
        FROM pg_constraint constraint_row
        JOIN pg_attribute attribute_row
          ON attribute_row.attrelid = constraint_row.conrelid
         AND attribute_row.attnum = ANY(constraint_row.conkey)
        WHERE constraint_row.contype = 'f'
          AND constraint_row.conrelid = 'candidate_stage_history'::regclass
          AND attribute_row.attname = 'actor_id'
    LOOP
        EXECUTE format('ALTER TABLE candidate_stage_history DROP CONSTRAINT %I', fk.conname);
    END LOOP;
END
$$;
-- migrate:split
ALTER TABLE candidate_stage_history
    ALTER COLUMN actor_id TYPE VARCHAR(36) USING actor_id::text;
-- migrate:split
DO $$
DECLARE
    fk RECORD;
BEGIN
    IF to_regclass('candidate_comments') IS NULL THEN
        RETURN;
    END IF;
    FOR fk IN
        SELECT constraint_row.conname
        FROM pg_constraint constraint_row
        JOIN pg_attribute attribute_row
          ON attribute_row.attrelid = constraint_row.conrelid
         AND attribute_row.attnum = ANY(constraint_row.conkey)
        WHERE constraint_row.contype = 'f'
          AND constraint_row.conrelid = 'candidate_comments'::regclass
          AND attribute_row.attname = 'author_id'
    LOOP
        EXECUTE format('ALTER TABLE candidate_comments DROP CONSTRAINT %I', fk.conname);
    END LOOP;
END
$$;
-- migrate:split
ALTER TABLE IF EXISTS candidate_comments
    ALTER COLUMN author_id TYPE VARCHAR(36) USING author_id::text;
