import os
from dotenv import load_dotenv

load_dotenv()

#HH API
EMPLOYER_ID = os.getenv('EMPLOYER_ID')
HH_CLIENT_ID = os.getenv('HH_CLIENT_ID')
HH_CLIENT_SECRET = os.getenv('HH_CLIENT_SECRET')
HH_EMAIL = os.getenv('HH_EMAIL')
HH_ACCESS_TOKEN = os.getenv('HH_ACCESS_TOKEN')
HH_REFRESH_TOKEN = os.getenv('HH_REFRESH_TOKEN')
# Optional: seconds until access token expiry when bootstrapping from env
HH_TOKEN_EXPIRES_IN = int(os.getenv("HH_TOKEN_EXPIRES_IN") or "0") or None
# If true, env tokens overwrite Redis on service start/first client init
HH_FORCE_ENV_TOKENS = os.getenv("HH_FORCE_ENV_TOKENS", "false").lower() in ("1", "true", "yes", "on")
HH_APP_NAME = os.getenv("HH_APP_NAME")
HH_APP_VERSION = os.getenv("HH_APP_VERSION")

#REDIS
REDIS_URL = (os.getenv("REDIS_SERVICE_URL") or os.getenv("REDIS_URL") or "").strip() or None

#hh-service
CLIENT_ID = os.getenv('HH_SERVICE_CLIENT_ID')
CLIENT_SECRET = os.getenv('HH_SERVICE_CLIENT_SECRET')
DB_SERVICE_URL = os.getenv("DB_SERVICE_URL")
TOKEN_URL = f"{os.getenv('DB_SERVICE_INTERNAL')}/v1/token/service"
V1 = "/v1"
DOMAIN = os.getenv("DOMAIN")
BASE_URL = os.getenv("HH_BASE_URL", f"https://hh.{DOMAIN}/v1")
HH_REDIRECT_URI = f"{BASE_URL}/hh/auth"
HH_RESUME_VIEW_LIMIT = 10
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://alt-lovat.vercel.app/dashboard")

ENV = os.getenv("ENV", "DEV")

# Отдельный флаг для мокирования ответов HH API.
# По умолчанию выключен, чтобы публикация вакансий шла на реальный api.hh.ru.
MOCK_HH = os.getenv("MOCK_HH", "false").lower() in ("1", "true", "yes", "on")

ALGORITHM = "RS256"
JWKS_URL = os.getenv("JWKS_URL")

BOT_NAME = os.getenv('BOT_NAME')

# AI Service
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL")

# Auto-reject («не подходит» on HH): small batches so we do not hit HH rate limits.
def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name) or default)
    except (TypeError, ValueError):
        return default


AUTO_REJECT_INTERVAL_MINUTES = max(1, _env_int("AUTO_REJECT_INTERVAL_MINUTES", 10))
AUTO_REJECT_BATCH_SIZE = max(1, _env_int("AUTO_REJECT_BATCH_SIZE", 5))
AUTO_REJECT_MAX_CHECKED = max(1, _env_int("AUTO_REJECT_MAX_CHECKED", 20))
AUTO_REJECT_DISCARD_DELAY_SEC = max(0.0, _env_float("AUTO_REJECT_DISCARD_DELAY_SEC", 1.2))
AUTO_REJECT_RR_KEY = "auto_reject_rr_index"

GREETING_WITH_NAME="""{name}, добрый день!
Обратили внимание на ваш опыт — он близок к тому, что сейчас ищем.
Мы выстроили процесс так, чтобы сэкономить время и вам, и нам:
вместо первичного созвона предлагаем короткое онлайн-знакомство через чат.

Это займет около 5 минут:
Подробности по вакансии и о нашей компании , мини тест и вопросы по опыту.

Ваша персональная ссылка: {url}.
Если удобнее пообщаться напрямую — просто напишите здесь.


Если удобнее пообщаться напрямую — просто напишите здесь."""

GREETING_WITHOUT_NAME="""Добрый день!
Обратили внимание на ваш опыт — он близок к тому, что сейчас ищем.
Мы выстроили процесс так, чтобы сэкономить время и вам, и нам:
вместо первичного созвона предлагаем короткое онлайн-знакомство через чат.

Это займет около 5 минут:
Подробности по вакансии и о нашей компании , мини тест и вопросы по опыту.

Ваша персональная ссылка: {url}.
Если удобнее пообщаться напрямую — просто напишите здесь.


Если удобнее пообщаться напрямую — просто напишите здесь."""


def invite_message(
        candidate_name: str,
        invite_url: str
        ):
        if isinstance(candidate_name, str):
            return GREETING_WITH_NAME.format(name=candidate_name, url=invite_url)
        else:
                return GREETING_WITHOUT_NAME.format(url=invite_url)


