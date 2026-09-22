"""Periodic: retry STT for imported calls with empty transcript."""
from __future__ import annotations

from app.config import T2_STT_BACKFILL_INTERVAL_MINUTES
from app.worker.huey import huey
from app.worker.jobs import run_t2_stt_backfill
from app.worker.runtime import run_async
from app.worker.schedule import interval_crontab


@huey.periodic_task(
    interval_crontab(T2_STT_BACKFILL_INTERVAL_MINUTES),
    name="hr.t2_stt_backfill.tick",
)
def tick_t2_stt_backfill() -> dict:
    return run_async(run_t2_stt_backfill())
