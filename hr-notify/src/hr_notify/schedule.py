"""Schedule helpers for HR Telegram notifications."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone, time as dt_time
from zoneinfo import ZoneInfo

# Europe/Samara = UTC+4 (Moscow +1). Fallback FixedOffset if tzdata missing.
try:
    SAMARA_TZ = ZoneInfo("Europe/Samara")
except Exception:  # pragma: no cover
    SAMARA_TZ = timezone(timedelta(hours=4), name="Europe/Samara")


def _parse_clock(remind_at_time: str | dt_time | None) -> tuple[int, int] | None:
    if remind_at_time is None:
        return None
    if isinstance(remind_at_time, dt_time):
        return remind_at_time.hour, remind_at_time.minute
    raw = str(remind_at_time).strip()
    if not raw:
        return None
    parts = raw.split(":")
    if len(parts) < 2:
        raise ValueError(f"invalid remind_at_time: {raw!r}")
    hour = int(parts[0])
    minute = int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"invalid remind_at_time: {raw!r}")
    return hour, minute


def compute_notify_at(
    event_date: date | str,
    remind_before: int,
    remind_at_time: str | dt_time | None = None,
) -> datetime:
    """notify_at for Huey.

    Day = event_date − remind_before.
    - no time → 00:00 UTC that day (send ASAP once the day is due)
    - time set → that clock in Europe/Samara, returned as aware UTC
    """
    if isinstance(event_date, str):
        raw = event_date.strip()[:10]
        day = date.fromisoformat(raw)
    else:
        day = event_date
    # Explicit None-check: remind_before=0 must stay 0
    days = max(0, 0 if remind_before is None else int(remind_before))
    notify_day = day - timedelta(days=days)

    clock = _parse_clock(remind_at_time)
    if clock is None:
        return datetime(
            notify_day.year,
            notify_day.month,
            notify_day.day,
            tzinfo=timezone.utc,
        )

    hour, minute = clock
    local = datetime(
        notify_day.year,
        notify_day.month,
        notify_day.day,
        hour,
        minute,
        0,
        tzinfo=SAMARA_TZ,
    )
    return local.astimezone(timezone.utc)


def should_send_immediately(notify_at: datetime, *, now: datetime | None = None) -> bool:
    """True when notify_at is already due (incl. remind_before=0 + event_date=today)."""
    current = now or datetime.now(timezone.utc)
    if notify_at.tzinfo is None:
        notify_at = notify_at.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return notify_at <= current
