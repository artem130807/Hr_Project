"""Periodic: mark past one-shot HR planner events as done."""
from __future__ import annotations

from huey import crontab

from app.worker.huey import huey
from app.worker.jobs import run_complete_overdue_planner_events
from app.worker.runtime import run_async


@huey.periodic_task(crontab(minute="7", strict=True), name="hr.planner_events.complete_overdue")
def tick_complete_overdue_planner_events() -> int:
    """Hourly catch-up: any event_date before today's Samara date is completed."""
    return run_async(run_complete_overdue_planner_events())
