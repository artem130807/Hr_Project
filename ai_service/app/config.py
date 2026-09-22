import os

from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
DB_SERVICE_URL = os.getenv("DB_SERVICE_URL")

DOMAIN = os.getenv("DOMAIN", "istendlay.ru")
API_VERSION = "v1"
v1 = "/v1"

# DB_SERVICE_URL / DB_SERVICE_BASE_URL from env win (in-cluster). Else public DOMAIN.
if not DB_SERVICE_URL:
    DB_SERVICE_URL = f"https://db.{DOMAIN}/{API_VERSION}"
DB_SERVICE_BASE_URL = (os.getenv("DB_SERVICE_BASE_URL") or DB_SERVICE_URL).rstrip("/")
if DB_SERVICE_BASE_URL.endswith("/v1"):
    TOKEN_URL = os.getenv("TOKEN_URL") or f"{DB_SERVICE_BASE_URL}/token/service"
else:
    TOKEN_URL = os.getenv("TOKEN_URL") or f"{DB_SERVICE_BASE_URL}/v1/token/service"

OPENAI_API_TOKEN = os.getenv("OPENAI_API_TOKEN")

JWKS_URL = os.getenv("JWKS_URL")
ALGORITHM = "RS256"

RABBITMQ_URL = (os.getenv("RABBITMQ_URL") or "").strip()
RABBITMQ_QUEUE_CANDIDATE_EVALUATE_REQUEST = (
    os.getenv("RABBITMQ_QUEUE_CANDIDATE_EVALUATE_REQUEST") or "hr.candidate.evaluate.requested"
).strip()
RABBITMQ_QUEUE_CANDIDATE_EVALUATE_RESULT = (
    os.getenv("RABBITMQ_QUEUE_CANDIDATE_EVALUATE_RESULT") or "hr.candidate.evaluate.completed"
).strip()
AI_EVALUATE_CONSUMER_ENABLED = os.getenv("AI_EVALUATE_CONSUMER_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
AI_OUTBOX_POLL_SECONDS = max(1.0, float(os.getenv("AI_OUTBOX_POLL_SECONDS", "2") or 2))
AI_DATABASE_URL = (os.getenv("AI_DATABASE_URL") or "sqlite+aiosqlite:///./ai_outbox.db").strip()
AI_GENERATE_TIMEOUT_SECONDS = max(15.0, float(os.getenv("AI_GENERATE_TIMEOUT_SECONDS", "90") or 90))
MIN_VACANCY_DESCRIPTION_CHARS = 200

# Outbound proxy for external APIs (OpenAI) — same scheme as opened-monitor-bot / bot-service
DEFAULT_TELEGRAM_PROXY_HOST = "singbox-proxy.infrastructure.svc.cluster.local"
DEFAULT_TELEGRAM_HTTP_PROXY_PORT = 8080
DEFAULT_TELEGRAM_SOCKS5_PROXY_PORT = 1080

TELEGRAM_PROXY_ENABLED = os.getenv("TELEGRAM_PROXY_ENABLED", "true").lower() in (
    "1", "true", "yes", "on",
)
TELEGRAM_PROXY_URL = (os.getenv("TELEGRAM_PROXY_URL") or os.getenv("TELEGRAM_PROXY") or "").strip()
TELEGRAM_PROXY_TYPE = (os.getenv("TELEGRAM_PROXY_TYPE") or "http").strip().lower() or "http"


def get_telegram_proxy_url() -> str | None:
    """
    Resolve outbound proxy URL (OpenAI via singbox in cluster).
    Same env/defaults as opened-monitor-bot and HR bot-service.
    """
    if not TELEGRAM_PROXY_ENABLED:
        return None
    if TELEGRAM_PROXY_URL:
        return TELEGRAM_PROXY_URL
    if TELEGRAM_PROXY_TYPE == "http":
        return f"http://{DEFAULT_TELEGRAM_PROXY_HOST}:{DEFAULT_TELEGRAM_HTTP_PROXY_PORT}"
    if TELEGRAM_PROXY_TYPE == "socks5":
        return f"socks5://{DEFAULT_TELEGRAM_PROXY_HOST}:{DEFAULT_TELEGRAM_SOCKS5_PROXY_PORT}"
    raise ValueError(f"Unsupported TELEGRAM_PROXY_TYPE: {TELEGRAM_PROXY_TYPE}")


# Alias for clarity inside AI service
get_outbound_proxy_url = get_telegram_proxy_url
