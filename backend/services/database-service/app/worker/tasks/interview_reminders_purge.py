"""Periodic: delete interview reminders that were already sent (is_send)."""
from __future__ import annotations

from app.worker.huey import huey
from app.worker.jobs import run_interview_reminder_purge
from app.worker.runtime import run_async
from app.worker.schedule import interval_crontab


@huey.periodic_task(interval_crontab(15), name="hr.interview_reminders.purge")
def tick_interview_reminder_purge() -> int:
    return run_async(run_interview_reminder_purge())
