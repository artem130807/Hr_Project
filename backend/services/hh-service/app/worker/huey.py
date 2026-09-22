"""Huey instance for the HH worker process. Do not import tasks here."""
from __future__ import annotations

from huey import MemoryHuey, RedisHuey

from app.app_logging import logger
from app.config import REDIS_URL

HUEY_NAME = "hr-hh"

_redis = (REDIS_URL or "").strip()
if _redis:
    huey = RedisHuey(HUEY_NAME, url=_redis, utc=True)
else:
    logger.warning(
        "REDIS_SERVICE_URL/REDIS_URL is unset — Huey uses an in-memory queue; "
        "HH jobs will not be shared across processes"
    )
    huey = MemoryHuey(HUEY_NAME, utc=True)
