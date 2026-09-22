"""Periodic: classify pending CallConversation rows with WhisperAi."""
from __future__ import annotations

from app.config import CALL_WHISPER_INTERVAL_MINUTES
from app.worker.huey import huey
from app.worker.jobs import run_call_whisper_classify
from app.worker.runtime import run_async
from app.worker.schedule import interval_crontab


@huey.periodic_task(
    interval_crontab(CALL_WHISPER_INTERVAL_MINUTES),
    name="hr.call_whisper.tick",
)
def tick_call_whisper_classify() -> dict:
    return run_async(run_call_whisper_classify())
