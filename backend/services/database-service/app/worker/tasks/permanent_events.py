"""Periodic: republish due permanent HR events to RabbitMQ."""
from __future__ import annotations

from huey import crontab

from app.worker.huey import huey
from app.worker.jobs import run_permanent_events_tick
from app.worker.runtime import run_async


@huey.periodic_task(crontab(minute="*", strict=True), name="hr.permanent_events.tick")
def tick_permanent_hr_events() -> int:
    return run_async(run_permanent_events_tick())
