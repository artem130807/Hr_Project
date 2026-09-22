-- Professional Q&A take: duration + MCQ options + result integrity/score
BEGIN;

ALTER TABLE tests
    ADD COLUMN IF NOT EXISTS duration_minutes INTEGER;

ALTER TABLE test_questions
    ADD COLUMN IF NOT EXISTS options JSONB,
    ADD COLUMN IF NOT EXISTS correct_option_index INTEGER;

ALTER TABLE public_test_results
    ADD COLUMN IF NOT EXISTS score INTEGER,
    ADD COLUMN IF NOT EXISTS max_score INTEGER,
    ADD COLUMN IF NOT EXISTS timed_out BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS integrity JSONB;

COMMIT;
