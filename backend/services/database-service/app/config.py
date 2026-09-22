import base64
import json
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.db.v1.enums import AdminRoles

load_dotenv()

DB_NAME = os.getenv('POSTGRES_DB')
DB_USER = os.getenv('POSTGRES_USER')
DB_HOST = os.getenv('POSTGRES_HOST')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD')
DB_PORT = os.getenv('POSTGRES_PORT')
DB_SCHEMA = os.getenv('POSTGRES_SCHEMA', 'public')

DATABASE_URL = f'postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
DB_SERVICE_URL = os.getenv('DB_SERVICE_URL')
REDIS_URL = (
    os.getenv("REDIS_SERVICE_URL") or os.getenv("REDIS_URL") or ""
).strip() or None

# Private S3-compatible storage for candidate employment documents.
S3_ENDPOINT_URL = (os.getenv("S3_ENDPOINT_URL") or "").strip() or None
S3_REGION = (os.getenv("S3_REGION") or "ru-1").strip()
S3_BUCKET = (os.getenv("S3_BUCKET") or "").strip()
S3_ACCESS_KEY_ID = (os.getenv("S3_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID") or "").strip()
S3_SECRET_ACCESS_KEY = (os.getenv("S3_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip()
S3_PRESIGNED_TTL_SECONDS = max(60, min(3600, int(os.getenv("S3_PRESIGNED_TTL_SECONDS", "900"))))
CANDIDATE_DOCS_TOKEN_TTL_HOURS = max(1, min(720, int(os.getenv("CANDIDATE_DOCS_TOKEN_TTL_HOURS", "168"))))
CANDIDATE_DOCS_DRAFT_TTL_HOURS = max(1, min(168, int(os.getenv("CANDIDATE_DOCS_DRAFT_TTL_HOURS", "72"))))
HIRING_REQUEST_INVITE_TTL_HOURS = max(1, min(720, int(os.getenv("HIRING_REQUEST_INVITE_TTL_HOURS", "168"))))

async_engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DB_ECHO", "false").lower() in ("1", "true", "yes", "on"),
    connect_args={"server_settings": {"search_path": DB_SCHEMA}},
)

AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)


ALGORITHM = "RS256"
INVITE_TOKEN_EXPIRE_MINUTES = 4320
ACCESS_TOKEN_EXPIRES = int(os.getenv("ACCESS_TOKEN_EXPIRES", 30))  # user JWT minutes
# Opaque refresh token TTL (default 14 days). Shorter access + long refresh is the standard pattern.
REFRESH_TOKEN_EXPIRES = int(os.getenv("REFRESH_TOKEN_EXPIRES", 20160))  # in minutes
# Service-to-service JWTs (no refresh) — keep longer; TokenManagers still renew on expiry.
SERVICE_TOKEN_EXPIRES = int(os.getenv("SERVICE_TOKEN_EXPIRES", 4320))  # in minutes

SUPERUSER_NAME = os.getenv('SUPERUSER_NAME')
SUPERUSER_PASSWORD = os.getenv('SUPERUSER_PASSWORD')
SUPERUSER_ROLE = AdminRoles.dev


V1 = '/v1'

BOT_NAME = os.getenv('BOT_NAME')

CLIENT_ID = os.getenv("DB_CLIENT_ID")
CLIENT_SECRET = os.getenv("DB_CLIENT_SECRET")

raw_clients = os.getenv("SERVICE_CLIENTS", "")
SERVICE_CLIENTS = []
if raw_clients:
    for index, raw_entry in enumerate(raw_clients.split(","), start=1):
        entry = raw_entry.strip()
        if not entry:
            continue
        if ":" not in entry:
            raise ValueError(
                f"Invalid SERVICE_CLIENTS entry #{index}: '{entry}'. "
                "Expected format 'client_id:secret' separated by commas."
            )
        client_id, secret = entry.split(":", 1)
        client_id = client_id.strip()
        secret = secret.strip()
        if not client_id:
            raise ValueError(
                f"Invalid SERVICE_CLIENTS entry #{index}: empty client_id in '{entry}'."
            )
        SERVICE_CLIENTS.append({"id": client_id, "secret": secret})
        if client_id == CLIENT_ID:
            CLIENT_SECRET = secret


HH_SERVICE_URL = os.getenv("HH_SERVICE_INTERNAL") or os.getenv("HH_SERVICE_URL")
# Optional: build HH OAuth authorize URL in-process (no hh-service roundtrip).
# Must match hh-service HH_CLIENT_ID / HH_REDIRECT_URI exactly.
HH_CLIENT_ID = (os.getenv("HH_CLIENT_ID") or "").strip() or None
HH_REDIRECT_URI = (os.getenv("HH_REDIRECT_URI") or "").strip() or None
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL")
BOT_SSERVICE_URL = os.getenv("BOT_SERVICE_INTERNAL")
# Shared secrets for database-service → hh-service publish proxy (try all)
def _unique_secrets(*values):
    out = []
    for value in values:
        if not value:
            continue
        text = str(value).strip()
        if text and text not in out:
            out.append(text)
    return out


INTERNAL_HH_PROXY_TOKENS = _unique_secrets(
    os.getenv("INTERNAL_PROXY_SECRET"),
    os.getenv("HH_SERVICE_CLIENT_SECRET"),
    os.getenv("DB_CLIENT_SECRET"),
    CLIENT_SECRET,
)
INTERNAL_HH_PROXY_TOKEN = INTERNAL_HH_PROXY_TOKENS[0] if INTERNAL_HH_PROXY_TOKENS else None
# Prefer host without /v1 (same pattern as hh-service TOKEN_URL)
_DB_INTERNAL = (os.getenv("DB_SERVICE_INTERNAL") or "").rstrip("/")
if _DB_INTERNAL:
    TOKEN_URL = f"{_DB_INTERNAL}/v1/token/service"
else:
    # DB_SERVICE_URL may already include /v1 — do not double it
    _db = (DB_SERVICE_URL or "").rstrip("/")
    TOKEN_URL = f"{_db}/token/service" if _db.endswith("/v1") else f"{_db}/v1/token/service"


status_update_cron_minutes = int(os.getenv("STATUS_UPDATE_CRON_MINUTES", 30))  # every 30 minutes by default
time_to_consider_candidate_not_completed_tests = int(os.getenv("TIME_TO_CONSIDER_CANDIDATE_NOT_COMPLETED_TESTS", 1440))  # in minutes
# Same default as hh-service: how often hr-worker asks HH to auto-reject.
AUTO_REJECT_INTERVAL_MINUTES = max(1, int(os.getenv("AUTO_REJECT_INTERVAL_MINUTES", "10") or 10))

# --- ERP user sync (background job inside database-service) ---
ERP_BASE = (os.getenv("ERP_BASE") or "").rstrip("/")
ERP_USERS_PATH = os.getenv("ERP_USERS_PATH", "/api/v2/users/")
ERP_BEARER_TOKEN = os.getenv("ERP_BEARER_TOKEN") or os.getenv("ERP_API_TOKEN") or ""
ERP_API_KEY = os.getenv("ERP_API_KEY") or ""
ERP_API_KEY_HEADER = os.getenv("ERP_API_KEY_HEADER", "X-API-Key")
ERP_HTTP_TIMEOUT = float(os.getenv("ERP_HTTP_TIMEOUT", "30"))
ERP_SYNC_INTERVAL_MINUTES = int(os.getenv("ERP_SYNC_INTERVAL_MINUTES", "60"))
ERP_SYNC_STARTUP_DELAY_SECONDS = int(os.getenv("ERP_SYNC_STARTUP_DELAY_SECONDS", "45"))
ERP_SYNC_BATCH_SIZE = int(os.getenv("ERP_SYNC_BATCH_SIZE", "100"))
# Legacy local-user sync is obsolete (users come from ERP live).
ERP_SYNC_ENABLED = (os.getenv("ERP_SYNC_ENABLED", "false").lower() in ("1", "true", "yes", "on"))
ERP_DEFAULT_ROLE = (os.getenv("ERP_DEFAULT_ROLE") or "dev").strip().lower()
ERP_SKIP_UNMAPPED_ROLES = (
    os.getenv("ERP_SKIP_UNMAPPED_ROLES", "false").lower() in ("1", "true", "yes", "on")
)
_raw_role_map = os.getenv(
    "ERP_ROLE_MAP",
    (
        '{"superadmin":"superadmin","Админ":"admin","Менеджер":"manager",'
        '"Руководитель":"leader","Руководитель отдела":"dept_leader",'
        '"Старший менеджер":"senior_manager","HR":"hr","Кадры":"hr",'
        '"Кадровик":"hr","Lead":"lead","Owner":"owner",'
        '"Разработчик":"dev","Dev":"dev","Art":"art"}'
    ),
)
try:
    ERP_ROLE_MAP = {
        str(k).strip().lower(): str(v).strip().lower()
        for k, v in json.loads(_raw_role_map).items()
    }
except (ValueError, TypeError):
    ERP_ROLE_MAP = {}

# --- ERP centralized auth (required for panel users; tokens live in erp-backend) ---
_erp_auth_raw = os.getenv("ERP_AUTH_ENABLED", "true")
ERP_AUTH_ENABLED = _erp_auth_raw.lower() in ("1", "true", "yes", "on")
ERP_AUTH_TOKEN_PATH = os.getenv("ERP_AUTH_TOKEN_PATH", "/auth/token")
ERP_AUTH_REFRESH_PATH = os.getenv("ERP_AUTH_REFRESH_PATH", "/auth/refresh")
ERP_AUTH_LOGOUT_PATH = os.getenv("ERP_AUTH_LOGOUT_PATH", "/auth/logout")
ERP_AUTH_ME_PATH = os.getenv("ERP_AUTH_ME_PATH", "/users/me")
# Must match erp-backend HS256 secret (env SECRET_JWT there → SECRET_AUTH_JWT in code).
ERP_JWT_SECRET = (
    os.getenv("ERP_JWT_SECRET")
    or os.getenv("SECRET_AUTH_JWT")
    or os.getenv("SECRET_JWT")
    or ""
)
ERP_JWT_ALGORITHM = os.getenv("ERP_JWT_ALGORITHM", "HS256")

# HR calls UI: only conversations where caller or operator matches these numbers.
# Both spellings below canonicalize to the same RU mobile. Set CALLS_ALLOWED_PHONES=* to show all.
CALLS_ALLOWED_PHONES = os.getenv(
    "CALLS_ALLOWED_PHONES",
    "+7 902 001 37 28,+7 902 001 3728",
)

# --- T2 corporate PBX (ATS OpenAPI) ---
T2_ATS_BASE = (os.getenv("T2_ATS_BASE") or "https://ats2.t2.ru/crm/openapi").rstrip("/")
T2_ATS_TIMEOUT = float(os.getenv("T2_ATS_TIMEOUT", "30"))
# Wiki examples send the access token as Authorization without a scheme.
T2_ATS_AUTH_SCHEME = (os.getenv("T2_ATS_AUTH_SCHEME") or "").strip()
T2_CALL_SYNC_ENABLED = os.getenv("T2_CALL_SYNC_ENABLED", "true").lower() in ("1", "true", "yes", "on")
T2_CALL_SYNC_INTERVAL_MINUTES = max(1, int(os.getenv("T2_CALL_SYNC_INTERVAL_MINUTES", "15") or 15))
T2_CALL_SYNC_LOOKBACK_HOURS = max(1, int(os.getenv("T2_CALL_SYNC_LOOKBACK_HOURS", "48") or 48))
T2_CALL_SYNC_PAGE_SIZE = max(1, min(100, int(os.getenv("T2_CALL_SYNC_PAGE_SIZE", "50") or 50)))
T2_CALL_SYNC_MAX_PAGES = max(1, int(os.getenv("T2_CALL_SYNC_MAX_PAGES", "40") or 40))
T2_CALL_SYNC_MAX_RECORDS_PER_TICK = max(
    1, int(os.getenv("T2_CALL_SYNC_MAX_RECORDS_PER_TICK", "300") or 300)
)
T2_STT_BACKFILL_ENABLED = os.getenv("T2_STT_BACKFILL_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
T2_STT_BACKFILL_INTERVAL_MINUTES = max(
    1, int(os.getenv("T2_STT_BACKFILL_INTERVAL_MINUTES", "10") or 10)
)
T2_STT_BACKFILL_BATCH_SIZE = max(
    1, min(50, int(os.getenv("T2_STT_BACKFILL_BATCH_SIZE", "12") or 12))
)
T2_STT_BACKFILL_REQUEST_DELAY_SECONDS = max(
    0.0, float(os.getenv("T2_STT_BACKFILL_REQUEST_DELAY_SECONDS", "1.0") or 1.0)
)
T2_STT_BACKFILL_MAX_AGE_DAYS = max(
    1, int(os.getenv("T2_STT_BACKFILL_MAX_AGE_DAYS", "7") or 7)
)
T2_STT_BACKFILL_SCAN_MULTIPLIER = max(
    1, int(os.getenv("T2_STT_BACKFILL_SCAN_MULTIPLIER", "5") or 5)
)
T2_ATS_REFRESH_PATH = os.getenv("T2_ATS_REFRESH_PATH", "/authorization/refresh/token").strip() or "/authorization/refresh/token"
# Access lives 24h; refresh 7d. Refresh this many seconds before access expiry.
T2_ACCESS_TTL_SECONDS = max(60, int(os.getenv("T2_ACCESS_TTL_SECONDS", str(24 * 3600)) or 24 * 3600))
T2_REFRESH_SKEW_SECONDS = max(0, int(os.getenv("T2_REFRESH_SKEW_SECONDS", str(2 * 3600)) or 2 * 3600))
T2_TOKEN_KEEPALIVE_ENABLED = os.getenv("T2_TOKEN_KEEPALIVE_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# --- CallConversation WhisperAi (OpenAI chat: status + HR description) ---
OPENAI_API_TOKEN = (os.getenv("OPENAI_API_TOKEN") or os.getenv("OPENAI_API_KEY") or "").strip()
OPENAI_API_BASE = (os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1").rstrip("/")
CALL_WHISPER_ENABLED = os.getenv("CALL_WHISPER_ENABLED", "true").lower() in ("1", "true", "yes", "on")
CALL_WHISPER_INTERVAL_MINUTES = max(1, int(os.getenv("CALL_WHISPER_INTERVAL_MINUTES", "5") or 5))
CALL_WHISPER_BATCH_SIZE = max(1, min(20, int(os.getenv("CALL_WHISPER_BATCH_SIZE", "6") or 6)))
CALL_WHISPER_REQUEST_DELAY_SECONDS = max(
    0.0, float(os.getenv("CALL_WHISPER_REQUEST_DELAY_SECONDS", "1.5") or 1.5)
)
CALL_WHISPER_MODEL = (os.getenv("CALL_WHISPER_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"
CALL_WHISPER_TIMEOUT = float(os.getenv("CALL_WHISPER_TIMEOUT", "60") or 60)
CALL_WHISPER_MAX_TRANSCRIPT_CHARS = max(
    500, int(os.getenv("CALL_WHISPER_MAX_TRANSCRIPT_CHARS", "12000") or 12000)
)
CALL_WHISPER_EMPTY_AS_DROPPED_SECONDS = max(
    0, int(os.getenv("CALL_WHISPER_EMPTY_AS_DROPPED_SECONDS", "15") or 15)
)

# --- RabbitMQ (same broker/queue as erp-backend → message-service) ---
RABBITMQ_URL = (os.getenv("RABBITMQ_URL") or "").strip()
RABBITMQ_QUEUE_MESSAGE_ENTITY_CHANGED = (
    os.getenv("RABBITMQ_QUEUE_MESSAGE_ENTITY_CHANGED")
    or os.getenv("RABBITMQ_QUEUE_ENTITY_CHANGED")
    or "message.entity_changed"
).strip()
RABBITMQ_QUEUE_CANDIDATE_EVALUATE_REQUEST = (
    os.getenv("RABBITMQ_QUEUE_CANDIDATE_EVALUATE_REQUEST") or "hr.candidate.evaluate.requested"
).strip()
RABBITMQ_QUEUE_CANDIDATE_EVALUATE_RESULT = (
    os.getenv("RABBITMQ_QUEUE_CANDIDATE_EVALUATE_RESULT") or "hr.candidate.evaluate.completed"
).strip()
AI_EVAL_RELAY_ENABLED = os.getenv("AI_EVAL_RELAY_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
