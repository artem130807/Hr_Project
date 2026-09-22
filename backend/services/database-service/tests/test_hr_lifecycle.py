"""Unit tests for HR lifecycle: request→vacancy, hire→employee, contacts, audit."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.v1.enums import Departments, HiringRequestStatus, CandidateStage, CandidateStatus
from app.services.hr_lifecycle import (
    build_description_from_request,
    vacancy_payload_from_request,
    employee_from_candidate,
)
from app.utils.hh_contacts import parse_phone_to_hh, contacts_from_company_contact


def _req(**kwargs):
    req = MagicMock()
    defaults = dict(
        id=10,
        position="Логист",
        department=Departments.logistics,
        purpose="Организация перевозок и контроль сроков доставки грузов по РФ.",
        features="Работа с 1С",
        reporting="Руководителю логистики",
        mandatory_requirements=["Опыт от 1 года", "Знание Excel"],
        desired_requirements=[],
        daily_tasks=["Планирование рейсов"],
        weekly_tasks=[],
        required_hard_skills=["Excel"],
        optional_hard_skills=[],
        required_soft_skills=["Коммуникабельность"],
        similar_positions=["Специалист по логистике"],
        keywords=["логист"],
        software=["1С"],
        languages=[],
        kpi_metrics=[],
        salary_from=80000,
        salary_to=120000,
        currency="RUB",
        gross=True,
        planned_close_date=None,
        age_from=25,
        work_day_description=None,
        work_address="Астрахань, ул. Ленина, 1",
        background_search=True,
    )
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(req, k, v)
    return req


def test_build_description_min_200_chars():
    text = build_description_from_request(_req(purpose="Коротко"))
    assert len(text) >= 200


def test_vacancy_payload_from_request_links_request_id():
    payload = vacancy_payload_from_request(_req())
    assert payload["name"] == "Логист"
    assert payload["hiring_request_id"] == 10
    assert payload["vacancy_type_id"] == "open"
    assert payload["professional_roles_id"] == []
    assert payload["schedule_id"] == "fullDay"
    assert payload["employment_id"] == "full"
    assert payload["salary_from"] == 80000
    assert payload["work_address"] == "Астрахань, ул. Ленина, 1"
    assert payload["is_internal_hidden"] is False
    assert "Excel" in payload["required_hard_skills"]
    assert len(payload["description"]) >= 200


def test_vacancy_hh_publish_gaps():
    from app.services.hr_lifecycle import vacancy_hh_publish_gaps

    vac = MagicMock()
    vac.professional_roles_id = []
    vac.area_id = None
    vac.description = "x" * 50
    gaps = vacancy_hh_publish_gaps(vac)
    assert any("роль" in g for g in gaps)
    assert any("area" in g or "город" in g for g in gaps)


def test_parse_phone_ru_mobile():
    phone = parse_phone_to_hh("+7 (999) 123-45-67")
    assert phone is not None
    assert phone.country == "7"
    assert phone.city == "999"
    assert phone.number == "1234567"


def test_parse_phone_rejects_short():
    assert parse_phone_to_hh("12345") is None


def test_contacts_from_company_contact():
    contact = MagicMock()
    contact.name = "Анна HR"
    contact.email = "anna@alt.ru"
    contact.phone_number = ["89991234567"]
    c = contacts_from_company_contact(contact)
    assert c.name == "Анна HR"
    assert c.email == "anna@alt.ru"
    assert c.phones[0].country == "7"


def test_contacts_from_company_contact_requires_phone():
    from fastapi import HTTPException

    contact = MagicMock()
    contact.name = "X"
    contact.email = "x@y.ru"
    contact.phone_number = ["123"]
    with pytest.raises(HTTPException) as ei:
        contacts_from_company_contact(contact)
    assert ei.value.status_code == 400


def test_employee_from_candidate_without_bot_user():
    cand = MagicMock()
    cand.id = 5
    cand.user_id = None
    cand.full_name = "Иванов Иван"
    cand.phone_number = "+79991234567"
    cand.gender = None
    cand.marital_status = None
    cand.hobbies = ["бег"]
    cand.personal_characteristics = "ответственный"
    cand.birth_date = date(1990, 1, 1)
    cand.age = 36

    vac = MagicMock()
    vac.department = Departments.it
    vac.name = "Backend"

    emp = employee_from_candidate(cand, vacancy=vac)
    assert emp.candidate_id == 5
    assert emp.user_id is None
    assert emp.full_name == "Иванов Иван"
    assert emp.position == "Backend"
    assert emp.department == Departments.it.value
    assert emp.date_hired == date.today()


@pytest.mark.asyncio
async def test_create_vacancy_from_hiring_request_links_both_sides():
    from app.endpoints.v1 import hiring_request as mod

    req = _req()
    req.linked_vacancy_id = None
    req.status = HiringRequestStatus.approved
    req.status_changed_at = None

    created = MagicMock()
    created.id = 77

    db = AsyncMock()
    db.get = AsyncMock(return_value=req)
    db.add = MagicMock()
    db.flush = AsyncMock(side_effect=lambda: setattr(created, "id", 77) or setattr(req, "_v", created))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    # When Vacancy(**payload) is constructed, we intercept via patching Vacancy
    fake_vacancy = MagicMock()
    fake_vacancy.id = 77

    with patch.object(mod, "Vacancy", return_value=fake_vacancy), patch.object(
        mod, "write_audit", new_callable=AsyncMock
    ):
        # After flush, assign id like ORM would
        async def _flush():
            fake_vacancy.id = 77

        db.flush = AsyncMock(side_effect=_flush)
        result = await mod.create_vacancy_from_hiring_request(10, db)

    assert req.linked_vacancy_id == 77
    assert result is fake_vacancy
    db.add.assert_called()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_create_vacancy_rejects_when_already_linked():
    from app.endpoints.v1 import hiring_request as mod
    from fastapi import HTTPException

    req = _req()
    req.linked_vacancy_id = 5
    req.status = HiringRequestStatus.approved

    existing = MagicMock()
    existing.id = 5

    db = AsyncMock()

    async def _get(model, pk):
        if pk == 10:
            return req
        if pk == 5:
            return existing
        return None

    db.get = AsyncMock(side_effect=_get)

    with pytest.raises(HTTPException) as ei:
        await mod.create_vacancy_from_hiring_request(10, db)
    assert ei.value.status_code == 409


@pytest.mark.asyncio
async def test_hire_creates_employee():
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
    ), patch("app.services.vnr.record_vnr_hire", new_callable=AsyncMock):
        result = await mod.hire_candidate_endpoint(3, db, actor=("hr-1", "Анна"))

    assert candidate.stage == CandidateStage.hired
    assert relation.status == CandidateStatus.started_work
    assert relation.is_active is False
    assert db.add.called
    assert result is candidate


@pytest.mark.asyncio
async def test_hire_maps_missing_enum_to_400():
    from sqlalchemy.exc import DataError
    from fastapi import HTTPException
    from app.endpoints.v1 import candidates as mod

    candidate = MagicMock()
    candidate.id = 6
    candidate.stage = CandidateStage.employment

    db = AsyncMock()
    db.get = AsyncMock(return_value=candidate)
    db.rollback = AsyncMock()
    orig = Exception('invalid input value for enum "candidatestage": "hired"')
    db.execute = AsyncMock(side_effect=DataError("SELECT 1", {}, orig))

    with pytest.raises(HTTPException) as ei:
        await mod.hire_candidate_endpoint(6, db, actor=("hr-1", "Анна"))
    assert ei.value.status_code == 400
    assert "ВНР" in ei.value.detail
    db.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_publish_hh_rejects_incomplete_vacancy():
    from app.endpoints.v1 import hiring_request as mod
    from fastapi import HTTPException

    req = _req()
    req.linked_vacancy_id = 77
    req.status = HiringRequestStatus.approved

    vacancy = MagicMock()
    vacancy.id = 77
    vacancy.hh_vacancy_id = None
    vacancy.professional_roles_id = []
    vacancy.area_id = None
    vacancy.description = "short"

    db = AsyncMock()

    async def _get(model, pk):
        if pk == 10:
            return req
        if pk == 77:
            return vacancy
        return None

    db.get = AsyncMock(side_effect=_get)

    with pytest.raises(HTTPException) as ei:
        await mod.publish_hiring_request_to_hh(10, db)
    assert ei.value.status_code == 400
    assert "роль" in str(ei.value.detail).lower() or "professional" in str(ei.value.detail).lower()


@pytest.mark.asyncio
async def test_delete_hiring_request_is_forbidden_to_preserve_business_history():
    from app.endpoints.v1 import hiring_request as mod

    req = _req()
    req.linked_vacancy_id = 77
    req.position = "Логист"

    vacancy = MagicMock()
    vacancy.id = 77
    vacancy.hiring_request_id = 10

    db = AsyncMock()
    db.get = AsyncMock(side_effect=lambda model, pk: req if pk == 10 else vacancy)
    linked_result = MagicMock()
    linked_result.scalars.return_value.all.return_value = [vacancy]
    db.execute = AsyncMock(return_value=linked_result)
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await mod.delete_hiring_request_endpoint(10, db)

    assert exc.value.status_code == 409
    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_write_audit_flushes():
    from app.utils.audit import write_audit

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    row = await write_audit(
        db,
        action="test",
        entity_type="x",
        entity_id=1,
        details="d",
    )
    db.add.assert_called_once()
    db.flush.assert_awaited()
    assert row.action == "test"


def test_archived_list_filters_by_enum_member_not_value():
    """Regression: comparing to .value broke SQLAlchemy Enum filters."""
    import inspect
    from app.endpoints.v1 import candidates as mod

    src = inspect.getsource(mod.get_archived_candidates_endpoint)
    assert "CandidateStage.archieved.value" not in src
    assert "CandidateStage.archieved" in src
    src_bl = inspect.getsource(mod.get_blacklisted_candidates_endpoint)
    assert "CandidateStage.blacklisted.value" not in src_bl
    assert "CandidateStage.blacklisted" in src_bl


def test_require_valid_phones_rejects_mixed():
    from fastapi import HTTPException
    from app.endpoints.v1.contacts import _require_valid_phones

    with pytest.raises(HTTPException) as ei:
        _require_valid_phones(["+79991234567", "123"])
    assert ei.value.status_code == 400


def test_require_valid_phones_keeps_valid_only():
    from app.endpoints.v1.contacts import _require_valid_phones

    assert _require_valid_phones(["+7 (999) 123-45-67"]) == ["+7 (999) 123-45-67"]


def test_api_process_does_not_start_apscheduler():
    import inspect
    from app.scheduler import scheduler as mod

    src = inspect.getsource(mod.init_scheduler)
    assert "scheduler.start" not in src
    assert "huey_consumer" in src
