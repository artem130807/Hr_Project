-- Additive schema for HR lifecycle features (also applied on database-service startup).
-- Safe to re-run.

ALTER TABLE employees ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE employees ALTER COLUMN gender DROP NOT NULL;
ALTER TABLE employees ALTER COLUMN phone_number TYPE VARCHAR(20);
ALTER TABLE employees ALTER COLUMN phone_number DROP NOT NULL;
ALTER TABLE employees ALTER COLUMN marital_status DROP NOT NULL;
ALTER TABLE employees ALTER COLUMN personal_characteristics DROP NOT NULL;
ALTER TABLE employees ALTER COLUMN birth_date DROP NOT NULL;
ALTER TABLE employees ALTER COLUMN age DROP NOT NULL;
ALTER TABLE employees ALTER COLUMN service_length DROP NOT NULL;
ALTER TABLE employees ALTER COLUMN hobbies DROP NOT NULL;
ALTER TABLE company_contacts ALTER COLUMN hr_id DROP NOT NULL;

-- New tables are created via SQLAlchemy create_all:
--   audit_logs, candidate_stage_history, candidate_comments
