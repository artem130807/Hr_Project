"""HH jobs are scheduled by database-service hr-worker, not a second Huey consumer."""
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_api_process_does_not_start_apscheduler():
    import inspect

    from app.scheduler import scheduler as sched_mod

    src = inspect.getsource(sched_mod.init_scheduler)
    assert "scheduler.start" not in src
    assert "hr-worker" in src
    assert "/v1/internal/jobs" in src


def test_internal_job_routes_exist():
    from app.endpoints.v1.internal_jobs import router

    paths = {getattr(r, "path", None) for r in router.routes}
    assert "/internal/jobs/autosearch" in paths
    assert "/internal/jobs/auto-reject" in paths
    assert "/internal/jobs/token-keepalive" in paths


def test_negotiation_webhook_runs_in_hh_service_process(monkeypatch):
    from app.endpoints.v1 import negotiation as mod

    run = AsyncMock()
    monkeypatch.setattr(mod, "_process_negotiation", run)
    app = FastAPI()
    app.include_router(mod.router, prefix="/v1")
    client = TestClient(app)
    payload = {"action_type": "NEW_NEGOTIATION_VACANCY", "payload": {"vacancy_id": "1"}}
    resp = client.post("/v1/hh/negotiation", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    run.assert_awaited_once_with(payload)
