"""Periodic: publish candidate-evaluate outbox and consume AI results."""
from __future__ import annotations

from app.worker.huey import huey
from app.worker.jobs import run_ai_eval_relay
from app.worker.runtime import run_async
from app.worker.schedule import interval_crontab


@huey.periodic_task(interval_crontab(1), name="hr.ai_eval.relay")
def tick_ai_eval_relay() -> dict:
    return run_async(run_ai_eval_relay())
