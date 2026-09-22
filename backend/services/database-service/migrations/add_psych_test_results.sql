-- Standalone psychological questionnaire results (no candidate FK).
-- Also created via SQLAlchemy create_all on service startup.

CREATE TABLE IF NOT EXISTS psych_test_results (
    id SERIAL PRIMARY KEY,
    instrument_id VARCHAR(100) NOT NULL,
    instrument_version VARCHAR(20),
    full_name VARCHAR(200) NOT NULL,
    position VARCHAR(200) NOT NULL,
    taken_at DATE NOT NULL,
    birth_date DATE,
    chs INTEGER,
    chm INTEGER,
    answers JSON NOT NULL,
    scores JSON NOT NULL,
    quality_status VARCHAR(50),
    leading_disc VARCHAR(120),
    leading_paei VARCHAR(120),
    leading_work10 VARCHAR(120),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_psych_test_results_instrument_id ON psych_test_results (instrument_id);
CREATE INDEX IF NOT EXISTS ix_psych_test_results_quality_status ON psych_test_results (quality_status);
