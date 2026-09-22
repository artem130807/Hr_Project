"""Huey consumer entry: ``huey_consumer app.worker.app.huey``."""
from app.worker.huey import huey
from app.worker import tasks as _tasks  # noqa: F401
