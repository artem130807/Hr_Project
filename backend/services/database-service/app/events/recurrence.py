"""Recurrence math for permanent HR calendar events.

The first notification is published synchronously as ``hr.event.created``
(same path as one-shot events). Huey later republishes when ``next_dispatch_at``
is due.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from dateutil.relativedelta import relativedelta

PERMANENT_TYPE = "permanent"
REPEAT_UNITS = ("day", "week", "month", "year")
SAMARA = timezone(timedelta(hours=4))

_UNIT_DELTAS = {
    "day": lambda n: relativedelta(days=n),
    "week": lambda n: relativedelta(weeks=n),
    "month": lambda n: relativedelta(months=n),
    "year": lambda n: relativedelta(years=n),
}


def is_permanent(event: Any) -> bool:
    return str(getattr(event, "type", "") or "").strip().lower() == PERMANENT_TYPE


def normalize_repeat(count: Optional[int], unit: Optional[str]) -> tuple[int, str]:
    raw_unit = str(unit or "").strip().lower()
    if raw_unit not in REPEAT_UNITS:
        raise ValueError("Некорректный интервал постоянного события")
    n = int(count or 1)
    if n < 1 or n > 365:
        raise ValueError("Интервал должен быть от 1 до 365")
    return n, raw_unit


def add_interval(moment: datetime, count: int, unit: str) -> datetime:
    n, unit = normalize_repeat(count, unit)
    return moment + _UNIT_DELTAS[unit](n)


def first_notify_at(
    event_date: date,
    remind_before: Optional[int] = 0,
    remind_at_time: Optional[time] = None,
) -> datetime:
    """Same rule as message-service ComputeNotifyAt (Samara clock / UTC midnight)."""
    days = 0 if remind_before is None else max(0, int(remind_before))
    day = event_date - timedelta(days=days)
    if remind_at_time is None:
        return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    local = datetime.combine(day, remind_at_time, tzinfo=SAMARA)
    return local.astimezone(timezone.utc)


def next_dispatch_after_initial(event: Any) -> datetime:
    count, unit = normalize_repeat(
        getattr(event, "repeat_interval_count", None),
        getattr(event, "repeat_interval_unit", None),
    )
    anchor = first_notify_at(
        event.event_date,
        getattr(event, "remind_before", 0),
        getattr(event, "remind_at_time", None),
    )
    return add_interval(anchor, count, unit)


def advance_to_future(due: datetime, count: int, unit: str, now: datetime) -> datetime:
    """Skip missed slots so a downtime does not dump a burst of notifies."""
    nxt = add_interval(due, count, unit)
    guard = 0
    while nxt <= now and guard < 1000:
        nxt = add_interval(nxt, count, unit)
        guard += 1
    return nxt


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
