from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.events.expiry import (
    calendar_today,
    complete_overdue_planner_events,
    should_auto_complete,
)
from app.events.recurrence import SAMARA


def test_calendar_today_uses_samara():
    # 26 Aug 2026 01:00 UTC = 05:00 Samara → still 26th
    assert calendar_today(datetime(2026, 8, 26, 1, 0, tzinfo=timezone.utc)) == date(2026, 8, 26)
    # 25 Aug 2026 21:00 UTC = 26 Aug 01:00 Samara
    assert calendar_today(datetime(2026, 8, 25, 21, 0, tzinfo=timezone.utc)) == date(2026, 8, 26)


def test_should_auto_complete_only_past_one_shot():
    today = date(2026, 8, 26)
    past = SimpleNamespace(type="interview", is_done=False, event_date=date(2026, 8, 25))
    today_ev = SimpleNamespace(type="birthday", is_done=False, event_date=date(2026, 8, 26))
    future = SimpleNamespace(type="other", is_done=False, event_date=date(2026, 8, 27))
    done = SimpleNamespace(type="interview", is_done=True, event_date=date(2026, 8, 24))
    permanent = SimpleNamespace(type="permanent", is_done=False, event_date=date(2026, 8, 20))

    assert should_auto_complete(past, today) is True
    assert should_auto_complete(today_ev, today) is False
    assert should_auto_complete(future, today) is False
    assert should_auto_complete(done, today) is False
    assert should_auto_complete(permanent, today) is False


@pytest.mark.asyncio
async def test_complete_overdue_updates_past_non_permanent_only():
    db = MagicMock()
    result = MagicMock(rowcount=3)
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()

    now = datetime(2026, 8, 26, 8, 0, tzinfo=SAMARA)
    count = await complete_overdue_planner_events(db, now=now)

    assert count == 3
    db.execute.assert_awaited_once()
    db.commit.assert_awaited_once()
    stmt = db.execute.await_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
    assert "is_done" in compiled
    assert "2026-08-26" in compiled or "2026-08-26" in str(stmt)
    assert "permanent" in compiled


@pytest.mark.asyncio
async def test_complete_overdue_skips_commit_when_nothing_changed():
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(rowcount=0))
    db.commit = AsyncMock()
    count = await complete_overdue_planner_events(
        db, now=datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    )
    assert count == 0
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_worker_job_skips_when_lock_held(monkeypatch):
    from app.worker import jobs

    class _Lock:
        async def __aenter__(self):
            return False

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(jobs, "DistributedLock", lambda *a, **k: _Lock())
    complete = AsyncMock()
    monkeypatch.setattr(jobs, "complete_overdue_planner_events", complete)
    assert await jobs.run_complete_overdue_planner_events() == 0
    complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_job_runs_when_lock_acquired(monkeypatch):
    from app.worker import jobs

    class _Lock:
        async def __aenter__(self):
            return True

        async def __aexit__(self, *args):
            return False

    class _Session:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(jobs, "DistributedLock", lambda *a, **k: _Lock())
    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: _Session())
    complete = AsyncMock(return_value=4)
    monkeypatch.setattr(jobs, "complete_overdue_planner_events", complete)
    assert await jobs.run_complete_overdue_planner_events() == 4
    complete.assert_awaited_once()
