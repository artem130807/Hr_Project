"""Backward-compatible consumer path: ``huey_consumer app.huey_app.huey``."""
from app.worker.app import huey

__all__ = ["huey"]
