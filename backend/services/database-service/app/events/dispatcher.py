"""Collect due permanent events and republish them to message-service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app_logging import logger
from app.db.v1.models import Event
from app.events.publisher import publish_hr_calendar_event
from app.events.recurrence import (
    PERMANENT_TYPE,
    advance_to_future,
    aware_utc,
    normalize_repeat,
)

PublishFn = Callable[..., Awaitable[bool]]


async def dispatch_due_permanent_events(
    db: AsyncSession,
    *,
    now: Optional[datetime] = None,
    publish: Optional[PublishFn] = None,
) -> int:
    moment = aware_utc(now or datetime.now(timezone.utc))
    publish_fn = publish or publish_hr_calendar_event

    stmt = (
        select(Event)
        .where(
            Event.type == PERMANENT_TYPE,
            Event.is_done.is_(False),
            Event.next_dispatch_at.is_not(None),
            Event.next_dispatch_at <= moment,
        )
        .order_by(Event.next_dispatch_at.asc())
        .with_for_update(skip_locked=True)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    sent = 0
    for event in rows:
        due = aware_utc(event.next_dispatch_at)
        try:
            ok = await publish_fn(
                event,
                occurrence="recurring",
                event_date=due.date(),
                remind_before=0,
            )
        except Exception as exc:
            logger.exception("permanent event %s publish failed: %s", event.id, exc)
            continue
        if not ok:
            logger.warning("permanent event %s not published (broker skipped)", event.id)
            continue
        count, unit = normalize_repeat(event.repeat_interval_count, event.repeat_interval_unit)
        event.last_dispatched_at = moment
        event.next_dispatch_at = advance_to_future(due, count, unit, moment)
        sent += 1
    if sent:
        await db.commit()
    return sent
