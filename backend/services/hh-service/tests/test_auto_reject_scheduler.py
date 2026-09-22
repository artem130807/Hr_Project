"""Scheduler + process_vacancy_responses coverage with mocks."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def _fast_auto_reject(monkeypatch):
    monkeypatch.setattr("app.config.AUTO_REJECT_DISCARD_DELAY_SEC", 0.0)
    monkeypatch.setattr("app.tasks.auto_reject_filtered.conf.AUTO_REJECT_DISCARD_DELAY_SEC", 0.0)


@pytest.mark.asyncio
async def test_process_vacancy_responses_rejects_mismatch_only():
    from app.tasks.auto_reject_filtered import process_vacancy_responses

    match = {
        "id": "n-ok",
        "viewed_by_opponent": False,
        "resume": {
            "id": "r1",
            "age": 30,
            "area": {"name": "Москва"},
            "total_experience": {"months": 24},
            "work_format": [{"id": "REMOTE"}],
        },
    }
    mismatch = {
        "id": "n-bad",
        "viewed_by_opponent": False,
        "resume": {
            "id": "r2",
            "age": 30,
            "area": {"name": "Казань"},
            "total_experience": {"months": 24},
            "work_format": [{"id": "REMOTE"}],
        },
    }

    hh = MagicMock()
    hh.get_negotiations_meta = AsyncMock(
        return_value={"collections": [{"id": "response", "url": "/negotiations/response"}]}
    )
    hh.list_negotiations_collection = AsyncMock(
        return_value={"items": [match, mismatch], "pages": 1}
    )
    hh.discard_negotiation = AsyncMock(return_value=None)
    hh.get_resume = AsyncMock()

    stats = await process_vacancy_responses(
        hh,
        {"id": 1, "hh_vacancy_id": "hh-1"},
        {"id": 7, "city": "Москва"},
        discard_message="reject",
    )
    assert stats["checked"] == 2
    assert stats["matched"] == 1
    assert stats["rejected"] == 1
    hh.discard_negotiation.assert_awaited_once()
    assert hh.discard_negotiation.await_args.args[0] == "n-bad"
    assert hh.discard_negotiation.await_args.kwargs.get("message") == "reject"


@pytest.mark.asyncio
async def test_process_vacancy_responses_caps_rejects():
    from app.tasks.auto_reject_filtered import process_vacancy_responses

    items = [
        {
            "id": f"n-{i}",
            "viewed_by_opponent": False,
            "resume": {
                "id": f"r{i}",
                "age": 30,
                "area": {"name": "Казань"},
                "total_experience": {"months": 24},
                "work_format": [{"id": "REMOTE"}],
            },
        }
        for i in range(8)
    ]
    hh = MagicMock()
    hh.get_negotiations_meta = AsyncMock(
        return_value={"collections": [{"id": "response", "url": "/negotiations/response"}]}
    )
    hh.list_negotiations_collection = AsyncMock(
        return_value={"items": items, "pages": 1}
    )
    hh.discard_negotiation = AsyncMock(return_value=None)

    stats = await process_vacancy_responses(
        hh,
        {"id": 1, "hh_vacancy_id": "hh-1"},
        {"id": 7, "city": "Москва"},
        discard_message="reject",
        max_rejects=5,
        discard_delay=0,
    )
    assert stats["rejected"] == 5
    assert stats["capped"] == 1
    assert hh.discard_negotiation.await_count == 5


@pytest.mark.asyncio
async def test_process_consider_action_applies_to_matches_only():
    from app.tasks.auto_reject_filtered import process_vacancy_responses

    match = {
        "id": "n-ok",
        "viewed_by_opponent": False,
        "resume": {
            "id": "r1",
            "age": 30,
            "area": {"name": "Москва"},
            "total_experience": {"months": 24},
            "work_format": [{"id": "REMOTE"}],
        },
    }
    mismatch = {
        "id": "n-bad",
        "viewed_by_opponent": False,
        "resume": {
            "id": "r2",
            "age": 30,
            "area": {"name": "Казань"},
            "total_experience": {"months": 24},
            "work_format": [{"id": "REMOTE"}],
        },
    }
    hh = MagicMock()
    hh.get_negotiations_meta = AsyncMock(
        return_value={"collections": [{"id": "response", "url": "/negotiations/response"}]}
    )
    hh.list_negotiations_collection = AsyncMock(
        return_value={"items": [match, mismatch], "pages": 1}
    )
    hh.consider_negotiation = AsyncMock(return_value=None)
    hh.discard_negotiation = AsyncMock(return_value=None)

    stats = await process_vacancy_responses(
        hh,
        {"id": 1, "hh_vacancy_id": "hh-1"},
        {"id": 7, "city": "Москва", "action": "consider"},
        discard_message="reject",
        discard_delay=0,
    )
    assert stats["matched"] == 1
    assert stats["considered"] == 1
    assert stats["rejected"] == 0
    hh.consider_negotiation.assert_awaited_once()
    assert hh.consider_negotiation.await_args.args[0] == "n-ok"
    hh.discard_negotiation.assert_not_awaited()


@pytest.mark.asyncio
async def test_auto_reject_single_vacancy_id():
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.tasks.auto_reject_filtered import auto_reject_filtered

    db = MagicMock()
    db.get = AsyncMock(
        side_effect=[
            {
                "id": 5,
                "hh_vacancy_id": "hh-5",
                "filter_id": 9,
                "name": "Логист",
            },
            {"id": 9, "city": "Москва"},
        ]
    )
    hh = MagicMock()

    with patch(
        "app.tasks.auto_reject_filtered.process_vacancy_responses",
        new=AsyncMock(
            return_value={
                "checked": 3,
                "matched": 1,
                "rejected": 2,
                "errors": 0,
                "skipped_viewed": 0,
            }
        ),
    ) as proc:
        summary = await auto_reject_filtered(db, hh, vacancy_id=5)

    assert summary["vacancy_id"] == 5
    assert summary["vacancies_processed"] == 1
    assert summary["rejected"] == 2
    proc.assert_awaited_once()
    assert db.get.await_args_list[0].args[0] == "/vacancy/5"


@pytest.mark.asyncio
async def test_auto_reject_single_vacancy_requires_hh():
    from unittest.mock import AsyncMock, MagicMock
    from fastapi import HTTPException
    from app.tasks.auto_reject_filtered import auto_reject_filtered

    db = MagicMock()
    db.get = AsyncMock(return_value={"id": 5, "filter_id": 1, "hh_vacancy_id": None})
    hh = MagicMock()

    try:
        await auto_reject_filtered(db, hh, vacancy_id=5)
        assert False, "expected HTTPException"
    except HTTPException as e:
        assert e.status_code == 400
        assert "HH" in str(e.detail)


@pytest.mark.asyncio
async def test_auto_reject_loads_filter_per_vacancy():
    from app.tasks.auto_reject_filtered import auto_reject_filtered

    db = MagicMock()

    async def db_get(path, **kwargs):
        if path == "/vacancies/published":
            return [
                {"id": 1, "hh_vacancy_id": "h1", "filter_id": 9},
                {"id": 2, "hh_vacancy_id": "h2", "filter_id": None},
            ]
        if path == "/vacancy-filters/9":
            return {"id": 9, "city": "Москва"}
        raise AssertionError(path)

    db.get = AsyncMock(side_effect=db_get)
    hh = MagicMock()
    hh.get_negotiations_meta = AsyncMock(
        return_value={"collections": [{"id": "response", "url": "/n"}]}
    )
    hh.list_negotiations_collection = AsyncMock(return_value={"items": [], "pages": 1})

    summary = await auto_reject_filtered(db, hh)
    assert summary["vacancies_processed"] == 1
    db.get.assert_any_await("/vacancy-filters/9")


def test_debug_auto_reject_route_exists():
    from main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/debug/auto-reject-filtered" in paths


def test_run_filter_route_exists():
    from app.endpoints.v1.hh_import import router

    paths = {getattr(r, "path", None) for r in router.routes}
    assert "/hh/local-vacancies/{vacancy_id}/run-filter" in paths
