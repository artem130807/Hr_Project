"""Unit tests for the HR Huey worker layer."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.worker.huey import HUEY_NAME, huey
from app.worker.runtime import run_async, worker_loop
from app.worker.schedule import interval_crontab


def test_interval_crontab_sub_hour():
    validate = interval_crontab(30)
    assert validate(datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc))
    assert validate(datetime(2026, 8, 24, 10, 30, tzinfo=timezone.utc))
    assert not validate(datetime(2026, 8, 24, 10, 15, tzinfo=timezone.utc))


def test_interval_crontab_hourly():
    validate = interval_crontab(60)
    assert validate(datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc))
    assert not validate(datetime(2026, 8, 24, 10, 30, tzinfo=timezone.utc))


def test_interval_crontab_over_hour_falls_back_to_hourly():
    validate = interval_crontab(90)
    assert validate(datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc))
    assert not validate(datetime(2026, 8, 24, 10, 30, tzinfo=timezone.utc))


def test_worker_loop_is_reused():
    loop = worker_loop()
    assert loop is worker_loop()
    assert not loop.is_closed()
    assert run_async(_coro_value(7)) == 7


async def _coro_value(n: int) -> int:
    return n


class _Lock:
    def __init__(self, acquired: bool):
        self.acquired = acquired

    async def __aenter__(self):
        return self.acquired

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_permanent_events_tick_skips_when_lock_held(monkeypatch):
    from app.worker import jobs

    monkeypatch.setattr(jobs, "DistributedLock", lambda *a, **k: _Lock(False))
    dispatch = AsyncMock()
    monkeypatch.setattr(jobs, "dispatch_due_permanent_events", dispatch)
    assert await jobs.run_permanent_events_tick() == 0
    dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_t2_call_sync_skips_when_disabled(monkeypatch):
    from app.worker import jobs

    monkeypatch.setattr(jobs, "T2_CALL_SYNC_ENABLED", False)
    session_cm = MagicMock()
    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: session_cm)
    result = await jobs.run_t2_call_sync()
    assert result["skipped_reason"] == "disabled"
    session_cm.__aenter__.assert_not_called()


@pytest.mark.asyncio
async def test_t2_call_sync_skips_when_lock_held(monkeypatch):
    from app.worker import jobs

    monkeypatch.setattr(jobs, "T2_CALL_SYNC_ENABLED", True)
    monkeypatch.setattr(jobs, "DistributedLock", lambda *a, **k: _Lock(False))
    session_cm = MagicMock()
    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: session_cm)
    result = await jobs.run_t2_call_sync()
    assert result["skipped_reason"] == "lock"
    session_cm.__aenter__.assert_not_called()


@pytest.mark.asyncio
async def test_t2_call_sync_runs_with_mocked_importer(monkeypatch):
    from app.worker import jobs

    monkeypatch.setattr(jobs, "T2_CALL_SYNC_ENABLED", True)
    monkeypatch.setattr(jobs, "DistributedLock", lambda *a, **k: _Lock(True))

    class _Session:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: _Session())
    sync = AsyncMock(return_value={"fetched": 1, "upserted": 1, "skipped": 0, "errors": 0})
    monkeypatch.setattr("app.t2.sync.sync_call_conversations", sync)
    result = await jobs.run_t2_call_sync()
    assert result["upserted"] == 1
    sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_t2_token_keepalive_skips_when_disabled(monkeypatch):
    from app.worker import jobs

    monkeypatch.setattr(jobs, "T2_TOKEN_KEEPALIVE_ENABLED", False)
    session_cm = MagicMock()
    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: session_cm)
    result = await jobs.run_t2_token_keepalive()
    assert result["skipped_reason"] == "disabled"
    session_cm.__aenter__.assert_not_called()


@pytest.mark.asyncio
async def test_t2_stt_backfill_skips_when_disabled(monkeypatch):
    from app.worker import jobs

    monkeypatch.setattr(jobs, "T2_STT_BACKFILL_ENABLED", False)
    session_cm = MagicMock()
    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: session_cm)
    result = await jobs.run_t2_stt_backfill()
    assert result["skipped_reason"] == "disabled"
    session_cm.__aenter__.assert_not_called()


@pytest.mark.asyncio
async def test_t2_stt_backfill_skips_when_lock_held(monkeypatch):
    from app.worker import jobs

    monkeypatch.setattr(jobs, "T2_STT_BACKFILL_ENABLED", True)
    monkeypatch.setattr(jobs, "DistributedLock", lambda *a, **k: _Lock(False))
    session_cm = MagicMock()
    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: session_cm)
    result = await jobs.run_t2_stt_backfill()
    assert result["skipped_reason"] == "lock"
    session_cm.__aenter__.assert_not_called()


@pytest.mark.asyncio
async def test_t2_stt_backfill_runs_with_mocked_sync(monkeypatch):
    from app.worker import jobs

    monkeypatch.setattr(jobs, "T2_STT_BACKFILL_ENABLED", True)
    monkeypatch.setattr(jobs, "DistributedLock", lambda *a, **k: _Lock(True))

    class _Session:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: _Session())
    backfill = AsyncMock(return_value={"scanned": 2, "updated": 1, "stt_missing": 1, "errors": 0})
    monkeypatch.setattr("app.t2.sync.backfill_missing_transcripts", backfill)
    result = await jobs.run_t2_stt_backfill()
    assert result["updated"] == 1
    backfill.assert_awaited_once()


@pytest.mark.asyncio
async def test_call_whisper_skips_when_disabled(monkeypatch):
    from app.worker import jobs

    monkeypatch.setattr(jobs, "CALL_WHISPER_ENABLED", False)
    session_cm = MagicMock()
    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: session_cm)
    result = await jobs.run_call_whisper_classify()
    assert result["skipped_reason"] == "disabled"
    session_cm.__aenter__.assert_not_called()


@pytest.mark.asyncio
async def test_call_whisper_skips_when_lock_held(monkeypatch):
    from app.worker import jobs

    monkeypatch.setattr(jobs, "CALL_WHISPER_ENABLED", True)
    monkeypatch.setattr(jobs, "DistributedLock", lambda *a, **k: _Lock(False))
    session_cm = MagicMock()
    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: session_cm)
    result = await jobs.run_call_whisper_classify()
    assert result["skipped_reason"] == "lock"
    session_cm.__aenter__.assert_not_called()


@pytest.mark.asyncio
async def test_call_whisper_runs_with_mocked_classifier(monkeypatch):
    from app.worker import jobs

    monkeypatch.setattr(jobs, "CALL_WHISPER_ENABLED", True)
    monkeypatch.setattr(jobs, "OPENAI_API_TOKEN", "sk-test")
    monkeypatch.setattr(jobs, "DistributedLock", lambda *a, **k: _Lock(True))

    class _Session:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: _Session())
    classify = AsyncMock(return_value={"fetched": 2, "classified": 2, "errors": 0})
    monkeypatch.setattr("app.calls.classify.classify_pending_conversations", classify)
    result = await jobs.run_call_whisper_classify()
    assert result["classified"] == 2
    classify.assert_awaited_once()


@pytest.mark.asyncio
async def test_interview_reminder_dispatch_skips_when_lock_held(monkeypatch):
    from app.worker import jobs

    monkeypatch.setattr(jobs, "DistributedLock", lambda *a, **k: _Lock(False))
    session_cm = MagicMock()
    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: session_cm)
    assert await jobs.run_interview_reminder_dispatch() == 0
    session_cm.__aenter__.assert_not_called()


@pytest.mark.asyncio
async def test_interview_reminder_purge_skips_when_lock_held(monkeypatch):
    from app.worker import jobs

    monkeypatch.setattr(jobs, "DistributedLock", lambda *a, **k: _Lock(False))
    session_cm = MagicMock()
    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: session_cm)
    assert await jobs.run_interview_reminder_purge() == 0
    session_cm.__aenter__.assert_not_called()


@pytest.mark.asyncio
async def test_status_update_skips_without_clients(monkeypatch):
    import sys
    import types

    from app.worker import jobs

    fake = types.ModuleType("app.dependencies")
    fake.get_hh_client = AsyncMock(return_value=None)
    fake.get_ai_client = AsyncMock(return_value=None)
    monkeypatch.setitem(sys.modules, "app.dependencies", fake)
    monkeypatch.setattr(jobs, "DistributedLock", lambda *a, **k: _Lock(True))
    session_cm = MagicMock()
    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: session_cm)
    await jobs.run_status_update()
    session_cm.__aenter__.assert_not_called()


@pytest.mark.asyncio
async def test_hh_job_skips_without_hh_url(monkeypatch):
    from app.worker import hh_client

    monkeypatch.setattr(hh_client.conf, "HH_SERVICE_URL", None)
    monkeypatch.setattr(hh_client.conf, "INTERNAL_HH_PROXY_TOKENS", ["secret"])
    assert await hh_client.trigger_hh_job("autosearch", timeout=1.0) is False


@pytest.mark.asyncio
async def test_hh_job_posts_internal_path(monkeypatch):
    from app.worker import hh_client

    monkeypatch.setattr(hh_client.conf, "HH_SERVICE_URL", "http://hh-service:8003")
    monkeypatch.setattr(hh_client.conf, "INTERNAL_HH_PROXY_TOKENS", ["tok"])
    monkeypatch.setattr(hh_client.conf, "INTERNAL_HH_PROXY_TOKEN", "tok")

    class _Resp:
        is_success = True
        status_code = 200
        text = "{}"

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None):
            assert url.endswith("/v1/internal/jobs/auto-reject")
            assert headers["X-Internal-Token"] == "tok"
            return _Resp()

    monkeypatch.setattr(hh_client.httpx, "AsyncClient", _Client)
    assert await hh_client.trigger_hh_job("auto-reject", timeout=5.0) is True


def test_huey_app_registers_hr_backend_jobs():
    from app.worker.app import huey as consumer_huey
    from app.worker.tasks.ai_eval_relay import tick_ai_eval_relay
    from app.worker.tasks.call_whisper import tick_call_whisper_classify
    from app.worker.tasks.complete_overdue_events import tick_complete_overdue_planner_events
    from app.worker.tasks.erp_sync import tick_erp_user_sync
    from app.worker.tasks.hh_auto_reject import tick_hh_auto_reject
    from app.worker.tasks.hh_autosearch import tick_hh_autosearch
    from app.worker.tasks.hh_token_keepalive import tick_hh_token_keepalive
    from app.worker.tasks.interview_reminders import tick_interview_reminder_dispatch
    from app.worker.tasks.interview_reminders_purge import tick_interview_reminder_purge
    from app.worker.tasks.permanent_events import tick_permanent_hr_events
    from app.worker.tasks.status_update import tick_status_update
    from app.worker.tasks.t2_call_sync import tick_t2_call_sync
    from app.worker.tasks.t2_stt_backfill import tick_t2_stt_backfill
    from app.worker.tasks.t2_token_keepalive import tick_t2_token_keepalive

    assert consumer_huey is huey
    assert huey.name == HUEY_NAME
    assert tick_complete_overdue_planner_events.huey is huey
    assert tick_permanent_hr_events.huey is huey
    assert tick_status_update.huey is huey
    assert tick_erp_user_sync.huey is huey
    assert tick_hh_autosearch.huey is huey
    assert tick_hh_auto_reject.huey is huey
    assert tick_hh_token_keepalive.huey is huey
    assert tick_t2_call_sync.huey is huey
    assert tick_t2_stt_backfill.huey is huey
    assert tick_t2_token_keepalive.huey is huey
    assert tick_call_whisper_classify.huey is huey
    assert tick_ai_eval_relay.huey is huey
    assert tick_interview_reminder_dispatch.huey is huey
    assert tick_interview_reminder_purge.huey is huey

    registry = getattr(huey._registry, "_registry", {})
    names = " ".join(str(k) for k in registry.keys())
    assert "complete_overdue" in names or "hr.planner_events.complete_overdue" in names
    assert "permanent_events" in names or "hr.permanent_events.tick" in names
    assert "status_update" in names or "hr.status_update.tick" in names
    assert "erp_users_sync" in names or "hr.erp_users_sync.tick" in names
    assert "autosearch" in names
    assert "auto_reject" in names
    assert "token_keepalive" in names
    assert "t2_call_sync" in names
    assert "t2_stt_backfill" in names
    assert "t2_token_keepalive" in names
    assert "call_whisper" in names
    assert "ai_eval" in names
    assert "interview_reminders" in names


def test_compat_huey_app_exports_same_instance():
    from app.huey_app import huey as compat
    from app.huey_instance import huey as inst
    from app.huey_tasks.permanent_events import tick_permanent_hr_events
    from app.worker.tasks.permanent_events import tick_permanent_hr_events as canonical

    assert compat is huey
    assert inst is huey
    assert tick_permanent_hr_events is canonical
