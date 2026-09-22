"""Periodic: mark stale in-progress candidates and request AI evaluation."""
from __future__ import annotations

from app.config import status_update_cron_minutes
from app.worker.huey import huey
from app.worker.jobs import run_status_update
from app.worker.runtime import run_async
from app.worker.schedule import interval_crontab


@huey.periodic_task(
    interval_crontab(status_update_cron_minutes),
    name="hr.status_update.tick",
)
def tick_status_update() -> None:
    return run_async(run_status_update())
