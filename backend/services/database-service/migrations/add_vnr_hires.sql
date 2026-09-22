-- VNR placements: hired candidates attributed to the HR who set status ВНР.
-- Safe to re-run. create_all also creates this table on new DBs.

CREATE TABLE IF NOT EXISTS vnr_hires (
    id SERIAL PRIMARY KEY,
    hr_user_id VARCHAR(36) NOT NULL,
    hr_user_name VARCHAR(200),
    candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    employee_id INTEGER REFERENCES employees(id),
    vacancy_id INTEGER REFERENCES vacancies(id),
    full_name VARCHAR NOT NULL,
    department VARCHAR,
    position VARCHAR,
    hired_at TIMESTAMPTZ NOT NULL,
    left_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL DEFAULT 'in_work',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_vnr_hires_candidate_id ON vnr_hires (candidate_id);
CREATE INDEX IF NOT EXISTS ix_vnr_hires_hr_user_id ON vnr_hires (hr_user_id);
CREATE INDEX IF NOT EXISTS ix_vnr_hires_hr_status ON vnr_hires (hr_user_id, status);
CREATE INDEX IF NOT EXISTS ix_vnr_hires_status ON vnr_hires (status);
