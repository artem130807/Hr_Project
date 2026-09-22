"""Periodic: send due candidate interview reminders via hh.ru chat."""
from __future__ import annotations

from huey import crontab

from app.worker.huey import huey
from app.worker.jobs import run_interview_reminder_dispatch
from app.worker.runtime import run_async


@huey.periodic_task(crontab(minute="*", strict=True), name="hr.interview_reminders.dispatch")
def tick_interview_reminder_dispatch() -> int:
    return run_async(run_interview_reminder_dispatch())
