"""Huey instance for the HR backend worker process.

Do not import tasks from this module — that creates circular imports.
The consumer entry is ``app.worker.app``.
"""
from __future__ import annotations

from huey import MemoryHuey, RedisHuey

from app.app_logging import logger
from app.config import REDIS_URL

HUEY_NAME = "hr-backend"

if REDIS_URL:
    huey = RedisHuey(HUEY_NAME, url=REDIS_URL, utc=True)
else:
    logger.warning(
        "REDIS_SERVICE_URL/REDIS_URL is unset — Huey uses an in-memory queue; "
        "periodic jobs will not be shared across processes and are lost on restart"
    )
    huey = MemoryHuey(HUEY_NAME, utc=True)
