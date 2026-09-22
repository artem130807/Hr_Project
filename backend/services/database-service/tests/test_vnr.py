"""VNR hire attribution: candidate → HR user, stats, resign close."""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.v1.enums import CandidateStatus, VnrHireStatus
from app.db.v1.models import VnrHire
from app.schemas.v1.candidates import CandidateStatusSchema
from app.services import vnr as vnr_svc


def _candidate(**kwargs):
    defaults = dict(
        id=3,
        full_name="Петров Пётр",
        user_id=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _vacancy(**kwargs):
    defaults = dict(id=9, name="Backend", department="it")
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _employee(**kwargs):
    defaults = dict(id=44)
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _exec_first(value):
    result = MagicMock()
    result.scalars.return_value.first.return_value = value
    return result


def _exec_scalar(value):
    result = MagicMock()
    result.scalar.return_value = value
    return result


def _exec_all(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.mark.asyncio
async def test_record_vnr_hire_creates_row_for_hr():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(return_value=_exec_first(None))

    row = await vnr_svc.record_vnr_hire(
        db,
        candidate=_candidate(),
        vacancy=_vacancy(),
        employee=_employee(),
        actor_id="hr-uuid-1",
        actor_name="Анна HR",
    )

    db.add.assert_called_once()
    created = db.add.call_args[0][0]
    assert isinstance(created, VnrHire)
    assert created.hr_user_id == "hr-uuid-1"
    assert created.hr_user_name == "Анна HR"
    assert created.candidate_id == 3
    assert created.employee_id == 44
    assert created.vacancy_id == 9
    assert created.full_name == "Петров Пётр"
    assert created.position == "Backend"
    assert created.department == "it"
    assert created.status == VnrHireStatus.in_work.value
    assert row is created
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_record_vnr_hire_skips_without_actor():
    db = AsyncMock()
    db.add = MagicMock()
    result = await vnr_svc.record_vnr_hire(
        db,
        candidate=_candidate(),
        vacancy=_vacancy(),
        employee=_employee(),
        actor_id=None,
        actor_name="бот",
    )
    assert result is None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_record_vnr_hire_is_idempotent_keeps_first_hr():
    existing = VnrHire(
        hr_user_id="hr-a",
        hr_user_name="Анна",
        candidate_id=3,
        employee_id=None,
        vacancy_id=9,
        full_name="Петров Пётр",
        department="it",
        position="Backend",
        hired_at=datetime.now(timezone.utc),
        status=VnrHireStatus.in_work.value,
    )
    db = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(return_value=_exec_first(existing))

    row = await vnr_svc.record_vnr_hire(
        db,
        candidate=_candidate(),
        vacancy=_vacancy(),
        employee=_employee(),
        actor_id="hr-b",
        actor_name="Борис",
    )

    assert row is existing
    assert existing.hr_user_id == "hr-a"
    assert existing.employee_id == 44
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_record_vnr_hire_reassigns_after_left():
    existing = VnrHire(
        hr_user_id="hr-a",
        hr_user_name="Анна",
        candidate_id=3,
        employee_id=44,
        vacancy_id=9,
        full_name="Петров Пётр",
        department="it",
        position="Backend",
        hired_at=datetime.now(timezone.utc),
        left_at=datetime.now(timezone.utc),
        status=VnrHireStatus.left.value,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_exec_first(existing))

    row = await vnr_svc.record_vnr_hire(
        db,
        candidate=_candidate(),
        vacancy=_vacancy(id=12, name="Lead"),
        employee=_employee(),
        actor_id="hr-b",
        actor_name="Борис",
    )

    assert row is existing
    assert existing.hr_user_id == "hr-b"
    assert existing.hr_user_name == "Борис"
    assert existing.status == VnrHireStatus.in_work.value
    assert existing.left_at is None
    assert existing.vacancy_id == 12
    assert existing.position == "Lead"


@pytest.mark.asyncio
async def test_mark_vnr_left_sets_status():
    existing = VnrHire(
        hr_user_id="hr-a",
        candidate_id=3,
        full_name="X",
        hired_at=datetime.now(timezone.utc),
        status=VnrHireStatus.in_work.value,
        left_at=None,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_exec_first(existing))

    row = await vnr_svc.mark_vnr_left(db, 3)
    assert row is existing
    assert existing.status == VnrHireStatus.left.value
    assert existing.left_at is not None


@pytest.mark.asyncio
async def test_mark_vnr_left_missing_row():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_exec_first(None))
    assert await vnr_svc.mark_vnr_left(db, 99) is None


@pytest.mark.asyncio
async def test_hr_vnr_stats_counts_hired_and_in_work():
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[
        _exec_scalar(6),
        _exec_scalar(4),
        _exec_scalar(26),
        _exec_scalar(5),
    ])
    stats = await vnr_svc.hr_vnr_stats(db, "hr-uuid-1")
    assert stats == {
        "hr_user_id": "hr-uuid-1",
        "hired": 6,
        "in_work": 4,
        "interviews": 26,
        "interviews_this_week": 5,
    }


@pytest.mark.asyncio
async def test_list_vnr_hires_filters_by_hr_and_active():
    rows = [MagicMock(id=1)]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_exec_all(rows))
    out = await vnr_svc.list_vnr_hires(db, hr_user_id="hr-1", active_only=True)
    assert out == rows
    db.execute.assert_awaited()


@pytest.mark.asyncio
async def test_hire_endpoint_records_vnr_for_actor():
    from app.db.v1.enums import CandidateStage, Departments
    from app.endpoints.v1 import candidates as mod

    candidate = MagicMock()
    candidate.id = 3
    candidate.user_id = None
    candidate.full_name = "Петров"
    candidate.phone_number = "79991112233"
    candidate.gender = None
    candidate.marital_status = None
    candidate.hobbies = []
    candidate.personal_characteristics = ""
    candidate.birth_date = None
    candidate.age = None
    candidate.stage = CandidateStage.employment
    candidate.employee = None

    relation = MagicMock()
    relation.vacancy_id = 9
    relation.status = CandidateStatus.interview
    relation.is_active = True

    vacancy = MagicMock()
    vacancy.id = 9
    vacancy.name = "Dev"
    vacancy.department = Departments.it
    vacancy.hiring_request_id = None

    db = AsyncMock()

    async def _get(model, pk):
        name = getattr(model, "__name__", "")
        if name == "Candidate":
            return candidate
        if name == "Vacancy":
            return vacancy
        return None

    db.get = AsyncMock(side_effect=_get)
    rel_result = MagicMock()
    rel_result.scalars.return_value.first.return_value = relation
    empty_emp = MagicMock()
    empty_emp.scalars.return_value.first.return_value = None
    db.execute = AsyncMock(side_effect=[rel_result, empty_emp])
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch("app.utils.audit.record_stage_change", new_callable=AsyncMock), patch(
        "app.utils.audit.write_audit", new_callable=AsyncMock
    ), patch("app.services.vnr.record_vnr_hire", new_callable=AsyncMock) as rec:
        result = await mod.hire_candidate_endpoint(3, db, actor=("hr-1", "Анна"))

    rec.assert_awaited()
    kwargs = rec.await_args.kwargs
    assert kwargs["actor_id"] == "hr-1"
    assert kwargs["actor_name"] == "Анна"
    assert kwargs["candidate"] is candidate
    assert kwargs["vacancy"] is vacancy
    assert candidate.stage == CandidateStage.hired
    assert relation.status == CandidateStatus.started_work
    assert result is candidate


@pytest.mark.asyncio
async def test_status_vnr_delegates_to_hire():
    from app.endpoints.v1 import candidates as mod

    relation = MagicMock()
    relation.status = CandidateStatus.interview
    relation.is_active = True

    db = AsyncMock()
    rel_result = MagicMock()
    rel_result.scalar_one_or_none.return_value = relation
    db.execute = AsyncMock(return_value=rel_result)

    with patch.object(mod, "hire_candidate_endpoint", new_callable=AsyncMock) as hire:
        out = await mod.update_candidate_status_endpoint(
            3,
            CandidateStatusSchema(status=CandidateStatus.started_work),
            db,
            actor=("hr-1", "Анна"),
        )

    hire.assert_awaited_once_with(3, db, ("hr-1", "Анна"))
    assert out == {"status": CandidateStatus.started_work}


@pytest.mark.asyncio
async def test_status_resigned_marks_vnr_left():
    from app.db.v1.enums import CandidateStage
    from app.endpoints.v1 import candidates as mod

    relation = MagicMock()
    relation.status = CandidateStatus.started_work
    relation.is_active = True

    candidate = MagicMock()
    candidate.stage = CandidateStage.hired

    db = AsyncMock()
    rel_result = MagicMock()
    rel_result.scalar_one_or_none.return_value = relation
    db.execute = AsyncMock(return_value=rel_result)
    db.get = AsyncMock(return_value=candidate)
    db.commit = AsyncMock()

    with patch("app.utils.audit.record_stage_change", new_callable=AsyncMock), patch(
        "app.utils.audit.write_audit", new_callable=AsyncMock
    ), patch("app.services.vnr.mark_vnr_left", new_callable=AsyncMock) as left:
        out = await mod.update_candidate_status_endpoint(
            3,
            CandidateStatusSchema(status=CandidateStatus.resigned),
            db,
            actor=("hr-1", "Анна"),
        )

    left.assert_awaited_once_with(db, 3)
    assert candidate.stage == CandidateStage.archieved
    assert relation.is_active is False
    assert out == {"status": CandidateStatus.resigned}


def test_interview_week_bounds_monday_sunday():
    start, end = vnr_svc.interview_week_bounds(date(2026, 8, 27))
    assert start == date(2026, 8, 24)
    assert end == date(2026, 8, 30)
    monday, sunday = vnr_svc.interview_week_bounds(date(2026, 8, 24))
    assert monday == date(2026, 8, 24)
    assert sunday == date(2026, 8, 30)


@pytest.mark.asyncio
async def test_hr_profile_stats_endpoint_uses_actor():
    from app.endpoints.v1 import vnr as ep

    db = AsyncMock()
    with patch.object(ep.vnr_svc, "hr_vnr_stats", new_callable=AsyncMock) as stats:
        stats.return_value = {
            "hr_user_id": "hr-1",
            "hired": 6,
            "in_work": 5,
            "interviews": 26,
            "interviews_this_week": 5,
        }
        out = await ep.get_hr_profile_stats(None, db, actor=("hr-1", "Анна"))

    stats.assert_awaited_once_with(db, "hr-1")
    assert out["hired"] == 6
    assert out["in_work"] == 5
    assert out["interviews"] == 26
    assert out["interviews_this_week"] == 5


@pytest.mark.asyncio
async def test_hr_profile_stats_requires_id():
    from fastapi import HTTPException
    from app.endpoints.v1 import vnr as ep

    with pytest.raises(HTTPException) as ei:
        await ep.get_hr_profile_stats(None, AsyncMock(), actor=(None, None))
    assert ei.value.status_code == 400


@pytest.mark.asyncio
async def test_list_vnr_endpoint_mine_uses_actor():
    from app.endpoints.v1 import vnr as ep

    db = AsyncMock()
    with patch.object(ep.vnr_svc, "list_vnr_hires", new_callable=AsyncMock) as lst:
        lst.return_value = []
        await ep.list_vnr_hires(None, True, True, db, actor=("hr-9", "Анна"))

    lst.assert_awaited_once()
    assert lst.await_args.kwargs["hr_user_id"] == "hr-9"
    assert lst.await_args.kwargs["active_only"] is True
