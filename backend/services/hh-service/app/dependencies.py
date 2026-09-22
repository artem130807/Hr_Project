import asyncio
import json
from datetime import datetime

from redis.asyncio import Redis as AsyncRedis

from app.clients.hh.simple_hh_client import SimpleHHClient, HHTokenManager
import app.config as conf
from app.app_logging import logger
from app.clients.db_client import APICLient as DBClient
from app.utils.auth_token_manager import TokenManager


_hh_client: SimpleHHClient | None = None
_lock = asyncio.Lock()  # на случай конкурентных запросов при старте

_db_client: DBClient | None = None
_ai_client: DBClient | None = None
_redis_client: AsyncRedis | None = None


async def get_redis_client() -> AsyncRedis:
    global _redis_client
    if _redis_client is None:
        if not conf.REDIS_URL:
            raise RuntimeError("REDIS_SERVICE_URL is not configured")
        _redis_client = AsyncRedis.from_url(conf.REDIS_URL, decode_responses=True)
    return _redis_client


async def get_hh_client() -> SimpleHHClient:
    global _hh_client

    if _hh_client:
        return _hh_client

    # Чтобы избежать гонок при одновременном первом вызове
    async with _lock:
        if not _hh_client:
            redis = await get_redis_client()

            # Загружаем сохранённые токены из Redis (кэш)
            token_data = await HHTokenManager.load_from_redis(redis)

            db = None
            try:
                db = await get_db_client()
            except Exception as e:
                logger.warning("HH tokens: database-service unavailable, Redis-only mode: %s", e)

            if not token_data.get("access_token") and db is not None:
                db_data = await HHTokenManager.load_from_db(db)
                if db_data.get("access_token"):
                    logger.info("HH tokens restored from PostgreSQL (Redis was empty)")
                    token_data = db_data
                    try:
                        await redis.set(HHTokenManager.REDIS_KEY, json.dumps(token_data))
                    except Exception as e:
                        logger.warning("Failed to warm Redis cache from PostgreSQL: %s", e)

            env_access = (conf.HH_ACCESS_TOKEN or "").strip() or None
            env_refresh = (conf.HH_REFRESH_TOKEN or "").strip() or None
            if HHTokenManager.is_placeholder_token(env_access) or HHTokenManager.is_placeholder_token(env_refresh):
                logger.warning(
                    "Ignoring placeholder HH_ACCESS_TOKEN/HH_REFRESH_TOKEN from env "
                    "(empty the secret and complete HH OAuth)"
                )
                env_access = None
                env_refresh = None
            use_env = bool(env_access) and (
                conf.HH_FORCE_ENV_TOKENS
                or not token_data.get("access_token")
            )

            access_token = env_access if use_env else token_data.get("access_token")
            refresh_token = env_refresh if use_env else token_data.get("refresh_token")
            expires_in = conf.HH_TOKEN_EXPIRES_IN if use_env else None

            _hh_client = SimpleHHClient(
                client_id=conf.HH_CLIENT_ID,
                client_secret=conf.HH_CLIENT_SECRET,
                employer_id=conf.EMPLOYER_ID,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in,
                redis_client=redis,
                db_client=db,
            )

            # Восстанавливаем точное время истечения токена из Redis/PG (если не из env)
            if not use_env:
                token_expires_str = token_data.get("token_expires")
                if token_expires_str:
                    try:
                        _hh_client.token_manager.token_expires = datetime.fromisoformat(token_expires_str)
                    except Exception:
                        pass
            elif access_token:
                # Persist env bootstrap so restarts without FORCE still work until refresh
                try:
                    await _hh_client.token_manager._save_tokens()
                except Exception:
                    pass

    return _hh_client



async def get_db_client() -> DBClient:
    global _db_client
    if _db_client is None:
        token_manager = TokenManager(
            token_url=conf.TOKEN_URL,
            client_id=conf.CLIENT_ID,
            client_secret=conf.CLIENT_SECRET
        )
        _db_client = DBClient(
            base_url=conf.DB_SERVICE_URL,
            token_manager=token_manager
        )
    return _db_client


async def get_ai_client() -> DBClient:
    global _ai_client
    if _ai_client is None:
        token_manager = TokenManager(
            token_url=conf.TOKEN_URL,
            client_id=conf.CLIENT_ID,
            client_secret=conf.CLIENT_SECRET
        )
        _ai_client = DBClient(
            base_url=conf.AI_SERVICE_URL,
            token_manager=token_manager
        )
    return _ai_client
