"""Hourly HH OAuth keepalive via hh-service HTTP job."""
from huey import crontab

from app.worker.huey import huey
from app.worker.jobs import run_hh_token_keepalive
from app.worker.runtime import run_async


@huey.periodic_task(crontab(minute="0", strict=True), name="hr.hh.token_keepalive.tick")
def tick_hh_token_keepalive() -> None:
    return run_async(run_hh_token_keepalive())
