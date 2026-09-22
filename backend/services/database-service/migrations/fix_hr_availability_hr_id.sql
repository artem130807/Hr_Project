-- Fix hr_availability.hr_id: legacy INTEGER (local panel user id) → VARCHAR(36) ERP UUID.
-- Idempotent: no-op when column is already character varying / text.

DO $$
DECLARE
    col_type text;
BEGIN
    SELECT t.typname INTO col_type
    FROM pg_attribute a
    JOIN pg_class c ON c.oid = a.attrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_type t ON t.oid = a.atttypid
    WHERE c.relname = 'hr_availability'
      AND a.attname = 'hr_id'
      AND NOT a.attisdropped
      AND n.nspname = current_schema()
    LIMIT 1;

    IF col_type IS NULL THEN
        RETURN;
    END IF;

    IF col_type IN ('varchar', 'text', 'bpchar') THEN
        RETURN;
    END IF;

    -- Drop FKs on hr_availability.hr_id if any (legacy → web_admin_panel_users)
    DECLARE
        fk RECORD;
    BEGIN
        FOR fk IN
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE con.contype = 'f'
              AND rel.relname = 'hr_availability'
              AND nsp.nspname = current_schema()
              AND EXISTS (
                  SELECT 1
                  FROM unnest(con.conkey) AS colnum
                  JOIN pg_attribute att
                    ON att.attrelid = con.conrelid AND att.attnum = colnum
                  WHERE att.attname = 'hr_id'
              )
        LOOP
            EXECUTE format('ALTER TABLE hr_availability DROP CONSTRAINT %I', fk.conname);
        END LOOP;
    END;

    EXECUTE $sql$
        ALTER TABLE hr_availability
            ALTER COLUMN hr_id TYPE VARCHAR(36) USING hr_id::text
    $sql$;
END
$$;
