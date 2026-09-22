"""Auto-complete one-shot HR planner events after their calendar day has passed.

Permanent (recurring) events stay open: Huey keeps republishing them.
«Today» is Europe/Samara, same clock as notify-at for calendar events.
An event on the 26th is still pending on the 26th; the 25th and earlier are done.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.app_logging import logger
from app.db.v1.models import Event
from app.events.recurrence import PERMANENT_TYPE, SAMARA, is_permanent


def calendar_today(now: Optional[datetime] = None) -> date:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(SAMARA).date()


def should_auto_complete(event: Any, today: date) -> bool:
    if bool(getattr(event, "is_done", False)):
        return False
    if is_permanent(event):
        return False
    event_date = getattr(event, "event_date", None)
    if event_date is None:
        return False
    return event_date < today


async def complete_overdue_planner_events(
    db: AsyncSession,
    *,
    now: Optional[datetime] = None,
) -> int:
    today = calendar_today(now)
    stmt = (
        update(Event)
        .where(
            Event.is_done.is_(False),
            Event.event_date < today,
            func.lower(Event.type) != PERMANENT_TYPE,
        )
        .values(is_done=True)
        .execution_options(synchronize_session="fetch")
    )
    result = await db.execute(stmt)
    count = int(result.rowcount or 0)
    if count:
        await db.commit()
        logger.info("auto-completed %s overdue planner event(s) before %s", count, today.isoformat())
    return count
