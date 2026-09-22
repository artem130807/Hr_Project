-- Standalone public professional (Q&A) test results (no candidate FK).
-- Also created via SQLAlchemy create_all on service startup.

CREATE TABLE IF NOT EXISTS public_test_results (
    id SERIAL PRIMARY KEY,
    test_id INTEGER NOT NULL REFERENCES tests(id),
    test_name VARCHAR(300),
    full_name VARCHAR(200) NOT NULL,
    position VARCHAR(200) NOT NULL,
    taken_at DATE NOT NULL,
    answers JSON NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_public_test_results_test_id ON public_test_results (test_id);
CREATE INDEX IF NOT EXISTS ix_public_test_results_full_name ON public_test_results (full_name);
CREATE INDEX IF NOT EXISTS ix_public_test_results_position ON public_test_results (position);
