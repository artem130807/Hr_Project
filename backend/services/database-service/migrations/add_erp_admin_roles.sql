-- Expand web_admin_panel_users.role enum with ERP roles.
-- Also applied on database-service startup (see main.py).

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'adminroles') THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'adminroles' AND e.enumlabel = 'superadmin'
        ) THEN
            ALTER TYPE adminroles ADD VALUE 'superadmin';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'adminroles' AND e.enumlabel = 'admin'
        ) THEN
            ALTER TYPE adminroles ADD VALUE 'admin';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'adminroles' AND e.enumlabel = 'manager'
        ) THEN
            ALTER TYPE adminroles ADD VALUE 'manager';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'adminroles' AND e.enumlabel = 'leader'
        ) THEN
            ALTER TYPE adminroles ADD VALUE 'leader';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'adminroles' AND e.enumlabel = 'dept_leader'
        ) THEN
            ALTER TYPE adminroles ADD VALUE 'dept_leader';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'adminroles' AND e.enumlabel = 'senior_manager'
        ) THEN
            ALTER TYPE adminroles ADD VALUE 'senior_manager';
        END IF;
    END IF;
END
$$;
