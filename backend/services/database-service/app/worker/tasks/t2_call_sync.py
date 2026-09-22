"""Periodic: import T2 ATS recordings and STT transcripts."""
from __future__ import annotations

from app.config import T2_CALL_SYNC_INTERVAL_MINUTES
from app.worker.huey import huey
from app.worker.jobs import run_t2_call_sync
from app.worker.runtime import run_async
from app.worker.schedule import interval_crontab


@huey.periodic_task(
    interval_crontab(T2_CALL_SYNC_INTERVAL_MINUTES),
    name="hr.t2_call_sync.tick",
)
def tick_t2_call_sync() -> dict:
    return run_async(run_t2_call_sync())
