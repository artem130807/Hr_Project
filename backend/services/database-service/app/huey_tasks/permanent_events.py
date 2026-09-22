"""Backward-compatible task import path."""
from app.worker.runtime import worker_loop as _worker_loop
from app.worker.tasks.permanent_events import tick_permanent_hr_events

__all__ = ["tick_permanent_hr_events", "_worker_loop"]
