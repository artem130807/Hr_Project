"""Every-minute adapter for the idempotent adaptation notification schedule."""
from huey import crontab

from app.worker.huey import huey
from app.worker.jobs import run_adaptation_notification_tick
from app.worker.runtime import run_async


@huey.periodic_task(crontab(minute="*", strict=True), name="hr.adaptation.notifications.tick")
def tick_adaptation_notifications():
    return run_async(run_adaptation_notification_tick())
