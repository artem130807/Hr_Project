"""TDD: background auto-reject by VacancyFilter (mocked HH + DB)."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture(autouse=True)
def _fast_auto_reject(monkeypatch):
    monkeypatch.setattr("app.config.AUTO_REJECT_DISCARD_DELAY_SEC", 0.0)
    monkeypatch.setattr("app.tasks.auto_reject_filtered.conf.AUTO_REJECT_DISCARD_DELAY_SEC", 0.0)


def _vacancy(**kw):
    base = {
        "id": 10,
        "name": "Логист",
        "hh_vacancy_id": "hh-100",
        "filter_id": 7,
    }
    base.update(kw)
    return base


def _filter(**kw):
    base = {
        "id": 7,
        "city": "Москва",
        "age_from": 25,
        "age_to": 40,
        "experience": "between1And3",
        "work_format": "remote",
    }
    base.update(kw)
    return base


def _neg(nid, resume_id="r1", viewed=False, **resume_extra):
    resume = {
        "id": resume_id,
        "age": 30,
        "area": {"name": "Москва"},
        "total_experience": {"months": 24},
        "work_format": [{"id": "REMOTE"}],
    }
    resume.update(resume_extra)
    return {
        "id": nid,
        "viewed_by_opponent": viewed,
        "has_updates": False,
        "employer_state": {"id": "response"},
        "resume": resume,
        "actions": [
            {
                "id": "discard",
                "enabled": True,
                "method": "PUT",
                "url": f"https://api.hh.ru/negotiations/discard/{nid}",
            }
        ],
    }


@pytest.mark.asyncio
async def test_skips_vacancies_without_filter_or_hh():
    from app.tasks.auto_reject_filtered import auto_reject_filtered

    db = MagicMock()
    db.get = AsyncMock(
        return_value=[
            _vacancy(filter_id=None),
            _vacancy(hh_vacancy_id=None, filter_id=1),
        ]
    )
    hh = MagicMock()
    hh.get_negotiations_meta = AsyncMock()
    hh.discard_negotiation = AsyncMock()

    summary = await auto_reject_filtered(db, hh)

    assert summary["vacancies_processed"] == 0
    assert summary["rejected"] == 0
    hh.get_negotiations_meta.assert_not_awaited()
    hh.discard_negotiation.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejects_unviewed_mismatch_keeps_match():
    from app.tasks.auto_reject_filtered import auto_reject_filtered

    match = _neg("n-ok", resume_id="ok")
    mismatch = _neg(
        "n-bad",
        resume_id="bad",
        area={"name": "Казань"},
        work_format=[{"id": "ON_SITE"}],
    )
    # already viewed — skip
    viewed = _neg("n-seen", resume_id="seen", viewed=True, area={"name": "Казань"})

    db = MagicMock()

    async def db_get(path, **kwargs):
        if path == "/vacancies/published":
            return [_vacancy()]
        if path == "/vacancy-filters/7":
            return _filter()
        raise AssertionError(path)

    db.get = AsyncMock(side_effect=db_get)

    hh = MagicMock()
    hh.get_negotiations_meta = AsyncMock(
        return_value={
            "collections": [
                {
                    "id": "response",
                    "name": "Неразобранные",
                    "url": "https://api.hh.ru/negotiations/response?vacancy_id=hh-100",
                    "counters": {"total": 3},
                }
            ]
        }
    )
    hh.list_negotiations_collection = AsyncMock(
        return_value={"items": [match, mismatch, viewed], "pages": 1, "found": 3}
    )
    hh.discard_negotiation = AsyncMock(return_value={"status": "discarded"})
    hh.get_resume = AsyncMock(side_effect=lambda rid: {
        "ok": match["resume"],
        "bad": mismatch["resume"],
        "seen": viewed["resume"],
    }[rid])

    summary = await auto_reject_filtered(db, hh, discard_message="Отказ по фильтру")

    assert summary["vacancies_processed"] == 1
    assert summary["checked"] == 2  # unviewed only
    assert summary["matched"] == 1
    assert summary["rejected"] == 1
    hh.discard_negotiation.assert_awaited_once()
    call_kwargs = hh.discard_negotiation.await_args
    assert call_kwargs.args[0] == "n-bad"
    assert call_kwargs.kwargs.get("message") == "Отказ по фильтру"
    assert isinstance(call_kwargs.kwargs.get("topic"), dict)


@pytest.mark.asyncio
async def test_uses_embedded_resume_when_full_enough():
    """If negotiation already embeds age/area/experience, skip extra GET resume."""
    from app.tasks.auto_reject_filtered import auto_reject_filtered

    bad = _neg("n1", area={"name": "Казань"})

    db = MagicMock()

    async def db_get(path, **kwargs):
        if path == "/vacancies/published":
            return [_vacancy()]
        if path == "/vacancy-filters/7":
            return _filter(city="Москва", age_from=None, age_to=None, experience=None, work_format=None)
        raise AssertionError(path)

    db.get = AsyncMock(side_effect=db_get)
    hh = MagicMock()
    hh.get_negotiations_meta = AsyncMock(
        return_value={
            "collections": [
                {"id": "response", "url": "/negotiations/response", "counters": {"total": 1}}
            ]
        }
    )
    hh.list_negotiations_collection = AsyncMock(return_value={"items": [bad], "pages": 1})
    hh.discard_negotiation = AsyncMock(return_value=None)
    hh.get_resume = AsyncMock()

    await auto_reject_filtered(db, hh)

    hh.get_resume.assert_not_awaited()
    hh.discard_negotiation.assert_awaited_once()


@pytest.mark.asyncio
async def test_continues_on_discard_error():
    from app.tasks.auto_reject_filtered import auto_reject_filtered
    from fastapi import HTTPException

    a = _neg("a", area={"name": "Казань"})
    b = _neg("b", area={"name": "Казань"})

    db = MagicMock()

    async def db_get(path, **kwargs):
        if path == "/vacancies/published":
            return [_vacancy()]
        if path == "/vacancy-filters/7":
            return _filter(city="Москва", age_from=None, age_to=None, experience=None, work_format=None)
        raise AssertionError(path)

    db.get = AsyncMock(side_effect=db_get)
    hh = MagicMock()
    hh.get_negotiations_meta = AsyncMock(
        return_value={"collections": [{"id": "response", "url": "/negotiations/response"}]}
    )
    hh.list_negotiations_collection = AsyncMock(return_value={"items": [a, b], "pages": 1})
    hh.discard_negotiation = AsyncMock(
        side_effect=[HTTPException(409, "no action"), None]
    )
    hh.get_resume = AsyncMock()

    summary = await auto_reject_filtered(db, hh)

    assert summary["rejected"] == 1
    assert summary["errors"] == 1
    assert hh.discard_negotiation.await_count == 2


@pytest.mark.asyncio
async def test_manual_run_includes_viewed_responses():
    from app.tasks.auto_reject_filtered import auto_reject_filtered

    viewed_bad = _neg("v1", viewed=True, area={"name": "Казань"})

    db = MagicMock()

    async def db_get(path, **kwargs):
        if path == "/vacancy/10":
            return _vacancy()
        if path == "/vacancy-filters/7":
            return _filter(
                city="Москва",
                age_from=None,
                age_to=None,
                experience=None,
                work_format=None,
            )
        raise AssertionError(path)

    db.get = AsyncMock(side_effect=db_get)
    hh = MagicMock()
    hh.get_negotiations_meta = AsyncMock(
        return_value={"collections": [{"id": "response", "url": "/negotiations/response"}]}
    )
    hh.list_negotiations_collection = AsyncMock(
        return_value={"items": [viewed_bad], "pages": 1}
    )
    hh.discard_negotiation = AsyncMock(return_value=None)
    hh.get_resume = AsyncMock()

    skipped = await auto_reject_filtered(db, hh, vacancy_id=10, include_viewed=False)
    assert skipped["checked"] == 0
    assert skipped["skipped_viewed"] == 1
    assert hh.discard_negotiation.await_count == 0

    summary = await auto_reject_filtered(db, hh, vacancy_id=10, include_viewed=True)
    assert summary["checked"] == 1
    assert summary["rejected"] == 1
    assert summary["include_viewed"] is True
    hh.discard_negotiation.assert_awaited()


@pytest.mark.asyncio
async def test_batch_size_caps_rejects_across_vacancies():
    from unittest.mock import patch
    from app.tasks.auto_reject_filtered import auto_reject_filtered

    bad_a = _neg("a", area={"name": "Казань"})
    bad_b = _neg("b", area={"name": "Казань"})

    db = MagicMock()

    async def db_get(path, **kwargs):
        if path == "/vacancies/published":
            return [
                _vacancy(id=1, hh_vacancy_id="h1"),
                _vacancy(id=2, hh_vacancy_id="h2"),
            ]
        if path == "/vacancy-filters/7":
            return _filter(
                city="Москва",
                age_from=None,
                age_to=None,
                experience=None,
                work_format=None,
            )
        raise AssertionError(path)

    db.get = AsyncMock(side_effect=db_get)
    hh = MagicMock()
    hh.get_negotiations_meta = AsyncMock(
        return_value={"collections": [{"id": "response", "url": "/negotiations/response"}]}
    )
    hh.list_negotiations_collection = AsyncMock(
        side_effect=[
            {"items": [bad_a], "pages": 1},
            {"items": [bad_b], "pages": 1},
        ]
    )
    hh.discard_negotiation = AsyncMock(return_value=None)
    hh.get_resume = AsyncMock()

    with patch(
        "app.tasks.auto_reject_filtered._rotate_start_index",
        new=AsyncMock(return_value=0),
    ):
        summary = await auto_reject_filtered(
            db, hh, batch_size=1, max_checked=50, discard_delay=0
        )

    assert summary["rejected"] == 1
    assert summary["batch_capped"] is True
    assert hh.discard_negotiation.await_count == 1
