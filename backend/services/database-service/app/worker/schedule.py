"""Crontab helpers for interval-based Huey periodic tasks."""
from __future__ import annotations

from huey import crontab


def interval_crontab(minutes: int):
    """Map an interval in minutes to a Huey crontab.

    Huey periodic tasks are cron-based, not APScheduler IntervalTrigger.
    ``strict=True`` so an invalid expression fails at import, not silently.
    """
    minutes = max(1, int(minutes or 1))
    if minutes % 60 == 0:
        hours = minutes // 60
        if hours <= 1:
            return crontab(minute="0", strict=True)
        return crontab(minute="0", hour=f"*/{hours}", strict=True)
    if minutes >= 60:
        # Cron minutes only go 0–59; fall back to top of each hour.
        return crontab(minute="0", strict=True)
    return crontab(minute=f"*/{minutes}", strict=True)
