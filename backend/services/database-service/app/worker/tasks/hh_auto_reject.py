"""Periodic HH auto-reject via hh-service HTTP job."""
from app.config import AUTO_REJECT_INTERVAL_MINUTES
from app.worker.huey import huey
from app.worker.jobs import run_hh_auto_reject
from app.worker.runtime import run_async
from app.worker.schedule import interval_crontab


@huey.periodic_task(
    interval_crontab(AUTO_REJECT_INTERVAL_MINUTES),
    name="hr.hh.auto_reject.tick",
)
def tick_hh_auto_reject() -> None:
    return run_async(run_hh_auto_reject())
