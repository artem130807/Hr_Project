import base64
import json
import os

from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.endpoints.v1.authorization import router as auth_router
from app.endpoints.v1.bot_users import router as bot_router
from app.endpoints.v1.candidates import router as candidate_router
from app.endpoints.v1.vacancies import router as vacancy_router
from app.endpoints.v1.vacancy_filters import router as vacancy_filters_router
from app.endpoints.v1.tests import router as tests_router
from app.endpoints.v1.psych_tests import router as psych_tests_router, public_router as psych_public_router
from app.endpoints.v1.public_professional_tests import (
    router as public_prof_tests_router,
    public_router as public_prof_public_router,
)
from app.endpoints.v1.admins import router as admin_router
from app.endpoints.v1.contacts import router as contacts_router
from app.endpoints.v1.autosearch import router as autosearch_router
from app.endpoints.v1.candidate_images import router as candidate_image_router
from app.endpoints.v1.ai import router as ai_router
from app.endpoints.v1.schedule import router as schedule_router
from app.endpoints.v1.stats import router as stats_router
from app.endpoints.v1.negotiations import router as negotiations_router
from app.endpoints.v1.dictionaries import router as dictionaries_router
from app.endpoints.v1.hh_dictionaries import router as hh_dictionaries_router
from app.endpoints.v1.events import router as events_router
from app.endpoints.v1.hh_oauth import router as hh_oauth_router
from app.endpoints.v1.t2_oauth import router as t2_oauth_router
from app.endpoints.v1.call_conversations import router as call_conversations_router
from app.endpoints.v1.messages import router as messages_router
from app.endpoints.v1.hiring_request import router as hiring_reqest_router, public_router as hiring_request_public_router
from app.endpoints.v1.employees import router as employees_router
from app.endpoints.v1.contact_directory import router as contact_directory_router
from app.endpoints.v1.candidate_documents import router as candidate_documents_router, public_router as candidate_documents_public_router
from app.endpoints.v1.vnr import router as vnr_router
from app.endpoints.v1.adaptation import (
    router as adaptation_router,
    public_router as adaptation_public_router,
)
from app.endpoints.v1.approvals import router as approvals_router
from app.endpoints.v1.audit_ops import router as audit_ops_router
from app.db.database import Base, AsyncSessionLocal
from app.db.middleware import db_middleware
from app.config import async_engine, V1
from app.utils.utils import verify_external_access, _public_key
from app.startup import ensure_superuser_and_services
from app.db.v1 import events  # noqa: F401 — registers SQLAlchemy listeners
from app.db.v1.models import (  # noqa: F401 — register tables for create_all
    AuditLog,
    CandidateStageHistory,
    CandidateComment,
    Employee,
    ContactPoint,
    OrganizationDepartment,
    AdaptationRoutingDecision,
    CandidateDocs,
    CandidateDocumentInvite,
    CandidateDocumentUploadSession,
    CandidateDocumentUploadFile,
    HiringRequestInvite,
    HiringRequestHistory,
    VnrHire,
    AdaptationEnrollment,
    AdaptationCheckpoint,
    AdaptationAnswer,
    VacancyFilter,
    PsychTestResult,
    PublicTestResult,
    HrNegotiationFlag,
    HhOAuthToken,
    T2OAuthToken,
    CallConversation,
    CandidateAiEvaluation,
    OutboxMessage,
    InterviewReminder,
)
from app.scheduler.scheduler import init_scheduler
from app.app_logging import logger
from sqlalchemy import text
from app.db.v1.enums import CandidateStage, CandidateStatus


async def _ensure_pg_enum_labels(conn, type_name: str, labels: tuple[str, ...]) -> None:
    """ADD VALUE for missing PostgreSQL enum labels (create_all does not ALTER types)."""
    for value in labels:
        escaped = value.replace("'", "''")
        try:
            await conn.execute(
                text(
                    f"""
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM pg_type WHERE typname = '{type_name}')
                           AND NOT EXISTS (
                               SELECT 1
                               FROM pg_enum e
                               JOIN pg_type t ON t.oid = e.enumtypid
                               WHERE t.typname = '{type_name}' AND e.enumlabel = '{escaped}'
                           )
                        THEN
                            ALTER TYPE {type_name} ADD VALUE '{escaped}';
                        END IF;
                    END
                    $$;
                    """
                )
            )
        except Exception as exc:
            logger.warning("Add %s %r skipped: %s", type_name, value, exc)


app = FastAPI(
    title="Database Service",
    description="Service for managing candidates, vacancies, tests, and admin users.",
    version="1"
)

_cors_origins_env = os.getenv("CORS_ORIGINS")
try:
    _cors_origins = json.loads(_cors_origins_env) if _cors_origins_env else None
except (ValueError, TypeError):
    _cors_origins = None
if not _cors_origins:
    _cors_origins = [
        "https://alt-lovat.vercel.app",  # продовый фронт
        "https://hr-web.alt-cargo.tw1.ru",
        "http://hr-web.alt-cargo.tw1.ru",
        "https://hr-platform.alt-cargo.tw1.ru",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
    ]
# Optional extra origins from FRONTEND_URL (comma-separated)
_frontend_url = (os.getenv("FRONTEND_URL") or "").strip()
if _frontend_url:
    for origin in _frontend_url.split(","):
        origin = origin.strip().rstrip("/")
        if origin and origin not in _cors_origins:
            _cors_origins.append(origin)

app.add_middleware(CORSMiddleware,
               allow_origins=_cors_origins,
               allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
               allow_credentials=True,
               allow_methods=["*"],
               allow_headers=["*"],
               )

app.middleware("http")(db_middleware)

app.include_router(auth_router, prefix=V1, tags=['Authorization'])
app.include_router(admin_router, prefix=V1, tags=['Admin Panel Users'], dependencies=[Depends(verify_external_access)])
app.include_router(bot_router, prefix=V1, tags=['Telegram'], dependencies=[Depends(verify_external_access)])
app.include_router(messages_router, prefix=V1, tags=["Messages"], dependencies=[Depends(verify_external_access)])
app.include_router(autosearch_router, prefix=V1, tags=["Autosearch"], dependencies=[Depends(verify_external_access)])
app.include_router(candidate_image_router, prefix=V1, tags=['Candidate Images'], dependencies=[Depends(verify_external_access)])
app.include_router(candidate_router, prefix=V1, tags=['Candidates'], dependencies=[Depends(verify_external_access)])
app.include_router(vacancy_router, prefix=V1, tags=['Vacancies'], dependencies=[Depends(verify_external_access)])
app.include_router(vacancy_filters_router, prefix=V1, tags=['Vacancy Filters'], dependencies=[Depends(verify_external_access)])
app.include_router(hiring_reqest_router, prefix=V1, tags=['Hiring Requests'], dependencies=[Depends(verify_external_access)])
app.include_router(hiring_request_public_router, prefix=V1, tags=['Hiring Requests Public'])
app.include_router(employees_router, prefix=V1, tags=['Employees'], dependencies=[Depends(verify_external_access)])
app.include_router(contact_directory_router, prefix=V1, tags=['Contact Directory'], dependencies=[Depends(verify_external_access)])
app.include_router(candidate_documents_router, prefix=V1, tags=['Candidate Documents'], dependencies=[Depends(verify_external_access)])
app.include_router(candidate_documents_public_router, prefix=V1, tags=['Candidate Documents Public'])
app.include_router(vnr_router, prefix=V1, tags=['VNR Hires'], dependencies=[Depends(verify_external_access)])
app.include_router(adaptation_router, prefix=V1, tags=['Adaptation'], dependencies=[Depends(verify_external_access)])
app.include_router(adaptation_public_router, prefix=V1, tags=['Adaptation Public'])
app.include_router(approvals_router, prefix=V1, tags=['Approvals'], dependencies=[Depends(verify_external_access)])
app.include_router(audit_ops_router, prefix=V1, tags=['Audit'], dependencies=[Depends(verify_external_access)])
app.include_router(tests_router, prefix=V1, tags=["Tests"], dependencies=[Depends(verify_external_access)])
app.include_router(psych_tests_router, prefix=V1, tags=["Psych Tests"], dependencies=[Depends(verify_external_access)])
app.include_router(psych_public_router, prefix=V1, tags=["Psych Tests Public"])
app.include_router(public_prof_tests_router, prefix=V1, tags=["Public Professional Test Results"], dependencies=[Depends(verify_external_access)])
app.include_router(public_prof_public_router, prefix=V1, tags=["Professional Tests Public"])
app.include_router(negotiations_router, prefix=V1, tags=['Negotiations'], dependencies=[Depends(verify_external_access)])
app.include_router(schedule_router, prefix=V1, tags=['Schedule, Availability'], dependencies=[Depends(verify_external_access)])
app.include_router(ai_router, prefix=V1, tags=['AI-related'], dependencies=[Depends(verify_external_access)])
app.include_router(contacts_router, prefix=V1, tags=['Company Contacts'], dependencies=[Depends(verify_external_access)])
app.include_router(stats_router, prefix=V1, tags=['Analytics'], dependencies=[Depends(verify_external_access)])
app.include_router(dictionaries_router, prefix=V1, tags=['Dictionaries'], dependencies=[Depends(verify_external_access)])
app.include_router(hh_dictionaries_router, prefix=V1, tags=['HH Dictionaries'], dependencies=[Depends(verify_external_access)])
app.include_router(events_router, prefix=V1, tags=['Events'], dependencies=[Depends(verify_external_access)])
app.include_router(
    hh_oauth_router,
    prefix=V1,
    tags=['HH OAuth Tokens'],
    dependencies=[Depends(verify_external_access)],
)
app.include_router(
    t2_oauth_router,
    prefix=V1,
    tags=['T2 OAuth Tokens'],
    dependencies=[Depends(verify_external_access)],
)
app.include_router(
    call_conversations_router,
    prefix=V1,
    tags=['Call Conversations'],
    dependencies=[Depends(verify_external_access)],
)



def _int_to_base64url(n: int) -> str:
    byte_length = (n.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(n.to_bytes(byte_length, "big")).rstrip(b"=").decode()


@app.get("/.well-known/jwks.json", include_in_schema=False)
async def jwks():
    pub_numbers = _public_key.public_numbers()
    return {
        "keys": [{
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": "1",
            "n": _int_to_base64url(pub_numbers.n),
            "e": _int_to_base64url(pub_numbers.e),
        }]
    }


@app.on_event("startup")
async def startup_event():
    async with async_engine.begin() as conn:
        logger.info("\n\nStarted creating tables")
        await conn.run_sync(Base.metadata.create_all)
        # Additive schema fixes for existing DBs (create_all does not ALTER columns).
        # Risky type changes (FK-backed int → varchar) are best-effort: full migration is
        # migrations/drop_web_admin_panel_users.sql
        for stmt in (
            "ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS planned_close_date DATE",
            "ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS is_template BOOLEAN NOT NULL DEFAULT false",
            "ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS hiring_request_id INTEGER",
            "ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS filter_id INTEGER",
            "CREATE INDEX IF NOT EXISTS ix_vacancies_filter_id ON vacancies (filter_id)",
            "ALTER TABLE employee_requests ADD COLUMN IF NOT EXISTS planned_close_date DATE",
            "ALTER TABLE employee_requests ADD COLUMN IF NOT EXISTS status_changed_at TIMESTAMPTZ",
            "ALTER TABLE employee_requests ADD COLUMN IF NOT EXISTS linked_vacancy_id INTEGER",
            "ALTER TABLE employee_requests ADD COLUMN IF NOT EXISTS initiator_name VARCHAR",
            "ALTER TABLE employees ALTER COLUMN user_id DROP NOT NULL",
            "ALTER TABLE employees ALTER COLUMN gender DROP NOT NULL",
            "ALTER TABLE employees ALTER COLUMN phone_number TYPE VARCHAR(20)",
            "ALTER TABLE employees ALTER COLUMN phone_number DROP NOT NULL",
            "ALTER TABLE employees ALTER COLUMN marital_status DROP NOT NULL",
            "ALTER TABLE employees ALTER COLUMN personal_characteristics DROP NOT NULL",
            "ALTER TABLE employees ALTER COLUMN birth_date DROP NOT NULL",
            "ALTER TABLE employees ALTER COLUMN age DROP NOT NULL",
            "ALTER TABLE employees ALTER COLUMN service_length DROP NOT NULL",
            "ALTER TABLE employees ALTER COLUMN hobbies DROP NOT NULL",
            "ALTER TABLE hh_oauth_tokens ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE department_candidate_images ADD COLUMN IF NOT EXISTS department VARCHAR",
            "ALTER TABLE department_candidate_images ALTER COLUMN lead_id DROP NOT NULL",
            "ALTER TABLE department_candidate_images DROP CONSTRAINT IF EXISTS department_candidate_images_lead_id_key",
            "DROP INDEX IF EXISTS department_candidate_images_lead_id_key",
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_department_candidate_images_department
            ON department_candidate_images (department)
            WHERE department IS NOT NULL
            """,
            "ALTER TABLE tests ADD COLUMN IF NOT EXISTS duration_minutes INTEGER",
            "ALTER TABLE test_questions ADD COLUMN IF NOT EXISTS options JSONB",
            "ALTER TABLE test_questions ADD COLUMN IF NOT EXISTS correct_option_index INTEGER",
            "ALTER TABLE public_test_results ADD COLUMN IF NOT EXISTS score INTEGER",
            "ALTER TABLE public_test_results ADD COLUMN IF NOT EXISTS max_score INTEGER",
            "ALTER TABLE public_test_results ADD COLUMN IF NOT EXISTS timed_out BOOLEAN NOT NULL DEFAULT false",
            "ALTER TABLE public_test_results ADD COLUMN IF NOT EXISTS integrity JSONB",
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS telegram_user VARCHAR",
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS note TEXT",
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS remind_at_time TIME",
            "ALTER TABLE vacancy_filters ADD COLUMN IF NOT EXISTS action VARCHAR(32) NOT NULL DEFAULT 'discard'",
            "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS telegram_username VARCHAR(64)",
            "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS email VARCHAR(254)",
            "ALTER TABLE approvals ADD COLUMN IF NOT EXISTS approver_name VARCHAR(200)",
            "ALTER TABLE approvals ALTER COLUMN new_status TYPE VARCHAR(200) USING new_status::text",
            # ERP identities are UUID strings. Older production schemas used
            # INTEGER here and rejected adaptation audit INSERTs.
            "ALTER TABLE audit_logs ALTER COLUMN actor_id TYPE VARCHAR(36) USING actor_id::text",
            "ALTER TABLE candidate_stage_history ALTER COLUMN actor_id TYPE VARCHAR(36) USING actor_id::text",
            "ALTER TABLE psych_test_results ADD COLUMN IF NOT EXISTS birth_date DATE",
            "ALTER TABLE psych_test_results ADD COLUMN IF NOT EXISTS chs INTEGER",
            "ALTER TABLE psych_test_results ADD COLUMN IF NOT EXISTS chm INTEGER",
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS repeat_interval_count INTEGER",
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS repeat_interval_unit VARCHAR(16)",
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS last_dispatched_at TIMESTAMPTZ",
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS next_dispatch_at TIMESTAMPTZ",
            "CREATE INDEX IF NOT EXISTS ix_events_next_dispatch_at ON events (next_dispatch_at)",
            """
            CREATE TABLE IF NOT EXISTS hr_negotiation_flags (
                erp_user_id VARCHAR(36) PRIMARY KEY,
                negotations_processing BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "ALTER TABLE employees ADD COLUMN IF NOT EXISTS erp_user_id VARCHAR(36)",
            "ALTER TABLE employees ALTER COLUMN erp_user_id TYPE VARCHAR(36) USING erp_user_id::text",
            # Adaptation enroll writes free-form ERP role labels into department.
            # Prod may still have PostgreSQL enum `departments` → 500 on enroll.
            "ALTER TABLE employees ALTER COLUMN department TYPE VARCHAR USING department::text",
            """
            CREATE TABLE IF NOT EXISTS adaptation_enrollments (
                id SERIAL PRIMARY KEY,
                employee_id INTEGER NOT NULL UNIQUE REFERENCES employees(id),
                include_control_2m BOOLEAN NOT NULL DEFAULT false,
                closed BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS adaptation_checkpoints (
                id SERIAL PRIMARY KEY,
                enrollment_id INTEGER NOT NULL REFERENCES adaptation_enrollments(id),
                kind VARCHAR(32) NOT NULL,
                plan_date DATE NOT NULL,
                fact_date DATE,
                closed BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS adaptation_answers (
                id SERIAL PRIMARY KEY,
                checkpoint_id INTEGER NOT NULL REFERENCES adaptation_checkpoints(id),
                role VARCHAR(16) NOT NULL,
                payload JSON NOT NULL,
                submitted_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT uq_adaptation_answer_role UNIQUE (checkpoint_id, role)
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_adaptation_enrollments_employee_id ON adaptation_enrollments (employee_id)",
            "CREATE INDEX IF NOT EXISTS ix_adaptation_checkpoints_enrollment_id ON adaptation_checkpoints (enrollment_id)",
            "CREATE INDEX IF NOT EXISTS ix_adaptation_checkpoints_kind ON adaptation_checkpoints (kind)",
            "CREATE INDEX IF NOT EXISTS ix_adaptation_checkpoints_plan_date ON adaptation_checkpoints (plan_date)",
            "CREATE INDEX IF NOT EXISTS ix_adaptation_answers_checkpoint_id ON adaptation_answers (checkpoint_id)",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS include_control_2m BOOLEAN NOT NULL DEFAULT false",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS series_key VARCHAR(64)",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS recurrence_rule JSON",
            "CREATE INDEX IF NOT EXISTS ix_adaptation_series ON adaptation_checkpoints (enrollment_id, series_key)",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS closed BOOLEAN NOT NULL DEFAULT false",
            "ALTER TABLE adaptation_enrollments DROP CONSTRAINT IF EXISTS adaptation_enrollments_employee_id_key",
            "ALTER TABLE adaptation_enrollments ALTER COLUMN employee_id DROP NOT NULL",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS temporary_employee_id INTEGER REFERENCES temporary_employees(id)",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS previous_enrollment_id INTEGER REFERENCES adaptation_enrollments(id)",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS start_date DATE",
            "UPDATE adaptation_enrollments ae SET start_date=e.date_hired FROM employees e WHERE ae.employee_id=e.id AND ae.start_date IS NULL",
            "UPDATE adaptation_enrollments SET start_date=CURRENT_DATE WHERE start_date IS NULL",
            "ALTER TABLE adaptation_enrollments ALTER COLUMN start_date SET NOT NULL",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS route VARCHAR(32) NOT NULL DEFAULT 'full'",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS manager_user_id VARCHAR(36)",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS manager_name VARCHAR(200)",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT false",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS archive_reason TEXT",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMPTZ",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS finalized_by VARCHAR(36)",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS outcome VARCHAR(32)",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS risk VARCHAR(32)",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS decision_comment TEXT",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS hiring_request_id INTEGER REFERENCES employee_requests(id)",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS quota_credited_at TIMESTAMPTZ",
            "ALTER TABLE adaptation_enrollments ADD COLUMN IF NOT EXISTS quota_credited_by VARCHAR(36)",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS fact_date DATE",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS closed BOOLEAN NOT NULL DEFAULT false",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS original_plan_date DATE",
            "UPDATE adaptation_checkpoints SET original_plan_date=plan_date WHERE original_plan_date IS NULL",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS rescheduled_at TIMESTAMPTZ",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS rescheduled_by VARCHAR(36)",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS reschedule_reason TEXT",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS draft_ready_at TIMESTAMPTZ",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS forced_completed_at TIMESTAMPTZ",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS forced_completed_by VARCHAR(36)",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS forced_reason TEXT",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMPTZ",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS finalized_by VARCHAR(36)",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS risk_override VARCHAR(32)",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS outcome_override VARCHAR(32)",
            "ALTER TABLE adaptation_checkpoints ADD COLUMN IF NOT EXISTS override_comment TEXT",
            "ALTER TABLE adaptation_answers ADD COLUMN IF NOT EXISTS actor_user_id VARCHAR(36)",
            "ALTER TABLE adaptation_answers ADD COLUMN IF NOT EXISTS actor_name VARCHAR(200)",
            "ALTER TABLE adaptation_answers ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE adaptation_answers ADD COLUMN IF NOT EXISTS locked BOOLEAN NOT NULL DEFAULT true",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_adaptation_active_employee ON adaptation_enrollments(employee_id) WHERE employee_id IS NOT NULL AND closed = false AND archived = false",
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_employees_erp_user_id
            ON employees (erp_user_id)
            WHERE erp_user_id IS NOT NULL
            """,
            """
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
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_vnr_hires_candidate_id ON vnr_hires (candidate_id)",
            "CREATE INDEX IF NOT EXISTS ix_vnr_hires_hr_user_id ON vnr_hires (hr_user_id)",
            "CREATE INDEX IF NOT EXISTS ix_vnr_hires_hr_status ON vnr_hires (hr_user_id, status)",
            "CREATE INDEX IF NOT EXISTS ix_vnr_hires_status ON vnr_hires (status)",
            """
            CREATE TABLE IF NOT EXISTS interview_reminders (
                id SERIAL PRIMARY KEY,
                candidate_id INTEGER NOT NULL REFERENCES candidates(id),
                vacancy_id INTEGER REFERENCES vacancies(id),
                interview_date DATE,
                interview_time TIME,
                remind_at TIMESTAMPTZ NOT NULL,
                message TEXT NOT NULL,
                is_send BOOLEAN NOT NULL DEFAULT false,
                sent_at TIMESTAMPTZ,
                last_error TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_interview_reminders_candidate_id ON interview_reminders (candidate_id)",
            "CREATE INDEX IF NOT EXISTS ix_interview_reminders_due ON interview_reminders (is_send, remind_at)",
            "ALTER TABLE employee_requests ADD COLUMN IF NOT EXISTS work_address VARCHAR(500)",
            "ALTER TABLE employee_requests ADD COLUMN IF NOT EXISTS background_search BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS work_address VARCHAR(500)",
            "ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS is_internal_hidden BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS next_contact_at TIMESTAMPTZ",
            "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS next_contact_owner_id VARCHAR(36)",
            "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS next_contact_owner_name VARCHAR(200)",
            "CREATE INDEX IF NOT EXISTS ix_candidates_next_contact_at ON candidates (next_contact_at)",
        ):
            try:
                # Keep one incompatible legacy DDL statement from aborting all
                # subsequent additive fixes in the PostgreSQL transaction.
                async with conn.begin_nested():
                    await conn.execute(text(stmt))
            except Exception as exc:
                logger.warning(f"Startup schema stmt skipped: {exc}")

        # Expand hiringrequeststatus enum (ignore if type/value already exists)
        for value in (
            "создана",
            "на анализе",
            "утверждена",
            "опубликована",
            "возвращена на уточнение",
            "закрыта",
            "отменена",
            "завершена",
        ):
            # values are fixed literals from code — safe to inline
            await conn.execute(
                text(
                    f"""
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'hiringrequeststatus')
                           AND NOT EXISTS (
                               SELECT 1
                               FROM pg_enum e
                               JOIN pg_type t ON t.oid = e.enumtypid
                               WHERE t.typname = 'hiringrequeststatus' AND e.enumlabel = '{value}'
                           )
                        THEN
                            ALTER TYPE hiringrequeststatus ADD VALUE '{value}';
                        END IF;
                    END
                    $$;
                    """
                )
            )

        # Expand adminroles enum with ERP roles (create_all does not ALTER enums)
        for value in (
            "superadmin",
            "admin",
            "manager",
            "leader",
            "dept_leader",
            "senior_manager",
        ):
            await conn.execute(
                text(
                    f"""
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'adminroles')
                           AND NOT EXISTS (
                               SELECT 1
                               FROM pg_enum e
                               JOIN pg_type t ON t.oid = e.enumtypid
                               WHERE t.typname = 'adminroles' AND e.enumlabel = '{value}'
                           )
                        THEN
                            ALTER TYPE adminroles ADD VALUE '{value}';
                        END IF;
                    END
                    $$;
                    """
                )
            )

        # Replace legacy candidate statuses with the hiring funnel enum
        try:
            migration_sql = (
                Path(__file__).resolve().parent / "migrations" / "replace_candidate_statuses.sql"
            )
            if migration_sql.is_file():
                await conn.execute(text(migration_sql.read_text(encoding="utf-8")))
                logger.info("Candidate status enum migration applied")
        except Exception as exc:
            logger.warning(f"Candidate status migration skipped: {exc}")

        try:
            await conn.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'candidatestatus')
                           AND NOT EXISTS (
                               SELECT 1
                               FROM pg_enum e
                               JOIN pg_type t ON t.oid = e.enumtypid
                               WHERE t.typname = 'candidatestatus' AND e.enumlabel = 'подумать'
                           )
                        THEN
                            ALTER TYPE candidatestatus ADD VALUE 'подумать';
                        END IF;
                    END
                    $$;
                    """
                )
            )
        except Exception as exc:
            logger.warning(f"Add candidatestatus 'подумать' skipped: {exc}")

        # Contact directory and adaptation routing additions. This file is
        # idempotent and is required for existing databases because
        # metadata.create_all() does not add columns to existing tables.
        try:
            contact_directory_sql = (
                Path(__file__).resolve().parent / "migrations" / "contact_directory.sql"
            )
            if contact_directory_sql.is_file():
                migration_source = contact_directory_sql.read_text(encoding="utf-8")
                for migration_stmt in migration_source.split("-- migrate:split"):
                    if not migration_stmt.strip():
                        continue
                    async with conn.begin_nested():
                        await conn.execute(text(migration_stmt))
                logger.info("Contact directory migration applied")
        except Exception as exc:
            logger.error(f"Contact directory migration failed: {exc}")
            raise

        try:
            employee_archiving_sql = (
                Path(__file__).resolve().parent / "migrations" / "employee_archiving.sql"
            )
            if employee_archiving_sql.is_file():
                for migration_stmt in employee_archiving_sql.read_text(encoding="utf-8").split("-- migrate:split"):
                    if migration_stmt.strip():
                        async with conn.begin_nested():
                            await conn.execute(text(migration_stmt))
                logger.info("Employee archiving migration applied")
        except Exception as exc:
            logger.error(f"Employee archiving migration failed: {exc}")
            raise

        try:
            candidate_archiving_sql = (
                Path(__file__).resolve().parent / "migrations" / "candidate_archiving.sql"
            )
            if candidate_archiving_sql.is_file():
                for migration_stmt in candidate_archiving_sql.read_text(encoding="utf-8").split("-- migrate:split"):
                    if migration_stmt.strip():
                        async with conn.begin_nested():
                            await conn.execute(text(migration_stmt))
                logger.info("Candidate archiving migration applied")
        except Exception as exc:
            logger.error(f"Candidate archiving migration failed: {exc}")
            raise

        try:
            erp_actor_ids_sql = (
                Path(__file__).resolve().parent / "migrations" / "erp_actor_ids.sql"
            )
            if erp_actor_ids_sql.is_file():
                for migration_stmt in erp_actor_ids_sql.read_text(encoding="utf-8").split("-- migrate:split"):
                    if migration_stmt.strip():
                        async with conn.begin_nested():
                            await conn.execute(text(migration_stmt))
                logger.info("ERP actor id migration applied")
        except Exception as exc:
            logger.error(f"ERP actor id migration failed: {exc}")
            raise

        try:
            candidate_docs_sql = (
                Path(__file__).resolve().parent / "migrations" / "candidate_documents.sql"
            )
            if candidate_docs_sql.is_file():
                migration_source = candidate_docs_sql.read_text(encoding="utf-8")
                for migration_stmt in migration_source.split("-- migrate:split"):
                    if not migration_stmt.strip():
                        continue
                    async with conn.begin_nested():
                        await conn.execute(text(migration_stmt))
                logger.info("Candidate documents migration applied")
        except Exception as exc:
            logger.error(f"Candidate documents migration failed: {exc}")
            raise

        try:
            hiring_request_invites_sql = (
                Path(__file__).resolve().parent / "migrations" / "hiring_request_invites.sql"
            )
            if hiring_request_invites_sql.is_file():
                migration_source = hiring_request_invites_sql.read_text(encoding="utf-8")
                for migration_stmt in migration_source.split("-- migrate:split"):
                    if not migration_stmt.strip():
                        continue
                    async with conn.begin_nested():
                        await conn.execute(text(migration_stmt))
                logger.info("Hiring request invites migration applied")
        except Exception as exc:
            logger.error(f"Hiring request invites migration failed: {exc}")
            raise

        try:
            workflow_sql = Path(__file__).resolve().parent / "migrations" / "hiring_request_workflow.sql"
            if workflow_sql.is_file():
                for migration_stmt in workflow_sql.read_text(encoding="utf-8").split("-- migrate:split"):
                    if migration_stmt.strip():
                        async with conn.begin_nested():
                            await conn.execute(text(migration_stmt))
                logger.info("Hiring request workflow migration applied")
        except Exception as exc:
            logger.error(f"Hiring request workflow migration failed: {exc}")
            raise

        # ВНР / hired: create_all never ALTERs existing enums; missing labels → 500 on /hire
        await _ensure_pg_enum_labels(
            conn,
            "candidatestatus",
            tuple(member.value for member in CandidateStatus),
        )
        await _ensure_pg_enum_labels(
            conn,
            "candidatestage",
            tuple(member.name for member in CandidateStage)
            + tuple(member.value for member in CandidateStage),
        )

        # hr_availability.hr_id: INTEGER → VARCHAR(36) for ERP UUIDs
        try:
            hr_id_sql = (
                Path(__file__).resolve().parent / "migrations" / "fix_hr_availability_hr_id.sql"
            )
            if hr_id_sql.is_file():
                await conn.execute(text(hr_id_sql.read_text(encoding="utf-8")))
                logger.info("hr_availability.hr_id migration applied")
        except Exception as exc:
            logger.warning(f"hr_availability.hr_id migration skipped: {exc}")

        logger.info("\nFinished creating tables")
    
    async with AsyncSessionLocal() as db:
        await ensure_superuser_and_services(db)

    # Background jobs run in the Huey worker process (app.worker), not here.
    init_scheduler()


if __name__=="__main__":
    uvicorn.run(
        "main:app", 
        host='0.0.0.0', 
        port=8000
        )


