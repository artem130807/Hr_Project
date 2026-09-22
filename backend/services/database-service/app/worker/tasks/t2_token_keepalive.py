"""Periodic: refresh T2 ATS access token before it expires (24h TTL)."""
from __future__ import annotations

from huey import crontab

from app.worker.huey import huey
from app.worker.jobs import run_t2_token_keepalive
from app.worker.runtime import run_async


@huey.periodic_task(crontab(minute="3", strict=True), name="hr.t2_token_keepalive.tick")
def tick_t2_token_keepalive() -> dict:
    return run_async(run_t2_token_keepalive())
