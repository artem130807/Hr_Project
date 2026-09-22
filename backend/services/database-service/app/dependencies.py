import asyncio
from typing import Optional

import app.config as conf
from app.app_logging import logger
from app.clients.api_client import APICLient
from app.utils.auth_token_manager import TokenManager


_hh_client: Optional[APICLient] = None

_token_manager = TokenManager(
    token_url=conf.TOKEN_URL,
    client_id=conf.CLIENT_ID,
    client_secret=conf.CLIENT_SECRET
)


def get_service_token_manager() -> TokenManager:
    return _token_manager

_ai_client: Optional[APICLient] = None

_bot_client: Optional[APICLient] = None


async def get_hh_client() -> Optional[APICLient]:
    global _hh_client
    if not conf.HH_SERVICE_URL:
        return None
    if _hh_client is None:
        _hh_client = APICLient(
            base_url=conf.HH_SERVICE_URL,
            token_manager=_token_manager,
            timeout=30.0,
        )
    return _hh_client


async def get_ai_client() -> Optional[APICLient]:
    global _ai_client
    if not conf.AI_SERVICE_URL:
        return None
    if _ai_client is None:
        if not conf.INTERNAL_HH_PROXY_TOKEN:
            logger.warning(
                "AI_SERVICE_URL is set but INTERNAL_PROXY_SECRET / DB_CLIENT_SECRET is empty; "
                "HR→AI calls may fail JWT validation across pods"
            )
        _ai_client = APICLient(
            base_url=conf.AI_SERVICE_URL,
            token_manager=_token_manager,
            timeout=120.0,
            internal_token=conf.INTERNAL_HH_PROXY_TOKEN,
        )
    return _ai_client


async def get_bot_client() -> Optional[APICLient]:
    global _bot_client
    if not conf.BOT_SSERVICE_URL:
        return None
    if _bot_client is None:
        _bot_client = APICLient(
            base_url=conf.BOT_SSERVICE_URL,
            token_manager=_token_manager
        )
    return _bot_client
