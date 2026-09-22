"""Async bridge for Huey's sync worker threads."""
from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def worker_loop() -> asyncio.AbstractEventLoop:
    """Reuse one event loop for the Huey process.

    The SQLAlchemy async engine is bound to a single loop. ``asyncio.run()``
    closes that loop after each tick and breaks the next job. Multiple Huey
    threads must serialize through this loop (see ``run_async``).
    """
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run ``coro`` on the process-wide worker loop.

    Huey may use several worker threads (``-w N``). asyncio loops and the
    async DB engine are not thread-safe, so callers are serialized.
    """
    with _loop_lock:
        return worker_loop().run_until_complete(coro)
