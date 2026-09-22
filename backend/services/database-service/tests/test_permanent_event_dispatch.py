from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.events.dispatcher import dispatch_due_permanent_events


@pytest.mark.asyncio
async def test_dispatch_publishes_due_permanent_event_and_advances():
    due = datetime(2026, 8, 24, 7, 0, tzinfo=timezone.utc)
    now = datetime(2026, 8, 24, 7, 1, tzinfo=timezone.utc)
    row = SimpleNamespace(
        id=5,
        type="permanent",
        is_done=False,
        next_dispatch_at=due,
        repeat_interval_count=1,
        repeat_interval_unit="month",
        event_date=date(2026, 8, 24),
        last_dispatched_at=None,
    )
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [row]))
    )
    db.commit = AsyncMock()
    publish = AsyncMock(return_value=True)

    sent = await dispatch_due_permanent_events(db, now=now, publish=publish)

    assert sent == 1
    publish.assert_awaited_once()
    assert publish.await_args.kwargs["occurrence"] == "recurring"
    assert publish.await_args.kwargs["remind_before"] == 0
    assert publish.await_args.kwargs["event_date"] == date(2026, 8, 24)
    assert row.last_dispatched_at == now
    assert row.next_dispatch_at > now
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_does_not_advance_when_publish_fails():
    due = datetime(2026, 8, 24, 7, 0, tzinfo=timezone.utc)
    row = SimpleNamespace(
        id=5,
        type="permanent",
        is_done=False,
        next_dispatch_at=due,
        repeat_interval_count=1,
        repeat_interval_unit="week",
        last_dispatched_at=None,
    )
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [row]))
    )
    db.commit = AsyncMock()
    publish = AsyncMock(return_value=False)

    sent = await dispatch_due_permanent_events(
        db, now=datetime(2026, 8, 24, 8, 0, tzinfo=timezone.utc), publish=publish
    )
    assert sent == 0
    assert row.next_dispatch_at == due
    db.commit.assert_not_called()


def test_huey_periodic_task_is_registered():
    from app.huey_instance import huey
    from app.huey_tasks import permanent_events as pe
    from app.worker.runtime import worker_loop

    assert pe.tick_permanent_hr_events.huey is huey
    assert callable(pe.tick_permanent_hr_events)
    loop = worker_loop()
    assert loop is pe._worker_loop()
    assert not loop.is_closed()
