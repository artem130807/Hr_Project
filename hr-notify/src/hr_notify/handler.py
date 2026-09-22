"""Enqueue / schedule HR Telegram notifications via Huey."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from hr_notify.schedule import should_send_immediately
from hr_notify.schemas import HrEventNotify

logger = logging.getLogger(__name__)


class HueyTaskLike(Protocol):
    """Huey TaskWrapper: call for immediate enqueue, .schedule for ETA."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...

    def schedule(self, args=None, kwargs=None, eta=None, delay=None, **options: Any) -> Any: ...


def schedule_hr_notification(
    payload: HrEventNotify,
    task: HueyTaskLike,
    *,
    now: Optional[datetime] = None,
) -> str:
    """
    Enqueue Huey task for payload.content.

    Immediate: ``task(content)`` (Huey enqueue now).
    Delayed: ``task.schedule(args=(content,), eta=notify_at)``.

    Returns mode: ``immediate`` or ``eta``.
    """
    if (payload.type or "").strip().lower() == "hiring_request":
        task(payload.content)
        logger.info(
            "hr-notify schedule mode=immediate kind=hiring_request "
            "hiring_request_id=%s actor_name=%s notify_at=%s",
            payload.hiring_request_id or payload.hr_event_id,
            payload.actor_name,
            payload.notify_at,
        )
        return "immediate"

    eta = payload.notify_at_dt()
    if eta.tzinfo is None:
        eta = eta.replace(tzinfo=timezone.utc)
    else:
        eta = eta.astimezone(timezone.utc)

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)

    if should_send_immediately(eta, now=current):
        task(payload.content)
        logger.info(
            "hr-notify schedule mode=immediate hr_event_id=%s type=%s "
            "event_date=%s remind_before=%s remind_at_time=%s "
            "notify_at=%s now=%s",
            payload.hr_event_id,
            payload.type,
            payload.event_date,
            payload.remind_before,
            payload.remind_at_time,
            eta.isoformat(),
            current.isoformat(),
        )
        return "immediate"
    # Huey (utc=True default): prefer aware UTC eta so it is not treated as localtime.
    task.schedule(args=(payload.content,), eta=eta)
    logger.info(
        "hr-notify schedule mode=eta hr_event_id=%s type=%s "
        "event_date=%s remind_before=%s remind_at_time=%s "
        "notify_at=%s now=%s (Huey fires at ETA)",
        payload.hr_event_id,
        payload.type,
        payload.event_date,
        payload.remind_before,
        payload.remind_at_time,
        eta.isoformat(),
        current.isoformat(),
    )
    return "eta"
