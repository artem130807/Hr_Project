"""Daily HH autosearch (03:00 UTC) via hh-service HTTP job."""
from huey import crontab

from app.worker.huey import huey
from app.worker.jobs import run_hh_autosearch
from app.worker.runtime import run_async


@huey.periodic_task(crontab(hour="3", minute="0", strict=True), name="hr.hh.autosearch.tick")
def tick_hh_autosearch() -> None:
    return run_async(run_hh_autosearch())
