"""Huey application for HR Telegram notifications."""
from __future__ import annotations

import os

from huey import RedisHuey

_redis_url = (
    os.getenv("REDIS_URL")
    or os.getenv("REDIS_SERVICE_URL")
    or "redis://localhost:6379/0"
).strip()
huey = RedisHuey("hr-notify", url=_redis_url)

from hr_notify import tasks as _tasks  # noqa: E402,F401
