-- Migration: add image storage to candidate_test_results
-- Date: 2026-04-14

BEGIN;

-- 1. Добавить новые колонки в candidate_test_results
ALTER TABLE candidate_test_results
    ADD COLUMN IF NOT EXISTS image_data BYTEA,
    ADD COLUMN IF NOT EXISTS image_content_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS has_image BOOLEAN NOT NULL DEFAULT FALSE;

-- 2. Добавить новое значение в enum TestResultsType
-- (PostgreSQL не поддерживает IF NOT EXISTS для ALTER TYPE ADD VALUE до версии 14,
--  поэтому оборачиваем в проверку)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        WHERE enumlabel = 'скриншот'
          AND enumtypid = (
              SELECT oid FROM pg_type WHERE typname = 'testresultstype'
          )
    ) THEN
        ALTER TYPE testresultstype ADD VALUE 'скриншот';
    END IF;
END
$$;

COMMIT;
