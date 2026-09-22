"""Unit tests for database-service schemas, enums, and vacancy route order."""
from pydantic import ValidationError
from datetime import datetime

import pytest

from app.db.v1.enums import CandidateStatus, AdminRoles
from app.schemas.v1.admins import AdminUserRead, AdminUserCreate
from app.schemas.v1.candidate_images import (
    DepartmentCandidateImageCreate,
    CompanyCandidateImageCreate,
)
from app.schemas.v1.events import EventCreate, EventRead
from app.endpoints.v1.vacancies import router as vacancy_router


def test_admin_user_read_excludes_password_hash():
    payload = {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "role": AdminRoles.dev.value,
        "user_id": None,
        "username": "admin@example.com",
        "full_name": "Admin User",
        "department": None,
        "negotations_processing": None,
        "erp_user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 1),
        "password_hash": "$2b$12$should_not_appear",
    }
    model = AdminUserRead.model_validate(payload)
    dumped = model.model_dump()
    assert "password_hash" not in dumped
    assert dumped["username"] == "admin@example.com"
    assert dumped["id"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


def test_admin_user_create_accepts_full_name():
    data = AdminUserCreate(
        role=AdminRoles.hr,
        user_id=None,
        username="elena@example.com",
        full_name="Елена",
        plain_password="secret123",
        department="hr",
    )
    assert data.full_name == "Елена"
    assert data.plain_password == "secret123"


def test_admin_user_create_password_optional():
    data = AdminUserCreate(
        role=AdminRoles.hr,
        username="elena@example.com",
        full_name="Елена",
    )
    assert data.plain_password is None


def test_department_portrait_maps_experience_alias():
    data = DepartmentCandidateImageCreate(
        hard_skills="Python",
        experience="2 years",
        common_requirements="Remote ok",
        department="hr",
        lead_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    )
    assert data.expirience == "2 years"
    orm = data.to_orm_dict()
    assert "experience" not in orm
    assert orm["expirience"] == "2 years"
    assert orm["lead_id"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    assert str(orm["department"]) == "hr"


def test_department_portrait_requires_department():
    with pytest.raises(ValidationError):
        DepartmentCandidateImageCreate(
            hard_skills="Python",
            lead_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        )


def test_department_portrait_lead_id_optional():
    data = DepartmentCandidateImageCreate(
        department="hr",
        hard_skills="Python",
    )
    assert data.lead_id is None
    assert data.department == "hr"


def test_company_portrait_schema_fields():
    data = CompanyCandidateImageCreate(
        soft_skills="Teamwork",
        red_flags="Job hopping",
        common_requirements="Office",
    )
    dumped = data.model_dump()
    assert set(dumped.keys()) == {"soft_skills", "red_flags", "common_requirements"}


def test_event_create_schema():
    event = EventCreate(
        type="other",
        employee_name="Ivan",
        telegram_user="@ivan_hr",
        note="Произвольная заметка",
        event_date="2026-08-12",
        remind_before=3,
    )
    assert event.type == "other"
    assert event.telegram_user == "@ivan_hr"
    assert event.note == "Произвольная заметка"
    assert event.is_done is False
    assert event.remind_at_time is None


def test_candidate_status_schema_accepts_consider():
    from app.schemas.v1.candidates import CandidateStatusSchema

    data = CandidateStatusSchema(status="подумать")
    assert data.status == CandidateStatus.consider


def test_read_vacancy_rejects_short_description():
    """PUT /status used to return ReadCandidateVacancyRelation; short vacancy
    descriptions then caused FastAPI response_model 500."""
    from datetime import date

    from pydantic import ValidationError
    from app.schemas.v1.vacancies import ReadVacancy
    from app.db.v1.enums import Departments

    payload = {
        "id": 1,
        "name": "Логист",
        "vacancy_type_id": "open",
        "synonyms": ["логист"],
        "description": "коротко",
        "department": Departments.logistics.value,
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 1),
        "planned_close_date": date(2026, 9, 1),
    }
    with pytest.raises(ValidationError):
        ReadVacancy.model_validate(payload)


def test_candidate_status_has_funnel_values():
    assert CandidateStatus.applied.value == "откликнулся"
    assert CandidateStatus.test_sent.value == "тест: отправлен"
    assert CandidateStatus.interview.value == "собес"
    assert CandidateStatus.started_work.value == "ВНР"
    assert CandidateStatus.rejection.value == "отказ"
    assert CandidateStatus.consider.value == "подумать"
    assert CandidateStatus.offer_accepted.value == "оффер принят"
    assert CandidateStatus.full_documents.value == "Full documents"
    assert len(CandidateStatus) == 14


def test_quick_win_fields_are_part_of_public_schemas():
    from app.schemas.v1.candidates import CandidateUpdate
    from app.schemas.v1.hiring_request import EmployeeRequestUpdate
    from app.schemas.v1.vacancies import VacancyUpdate

    request = EmployeeRequestUpdate(
        work_address="Астрахань, ул. Ленина, 1",
        background_search=True,
    )
    vacancy = VacancyUpdate(work_address="Удалённо", is_internal_hidden=True)
    candidate = CandidateUpdate(
        next_contact_at="2026-09-11T08:00:00Z",
        next_contact_owner_id="hr-1",
        next_contact_owner_name="Анна HR",
    )

    assert request.work_address.startswith("Астрахань")
    assert request.background_search is True
    assert vacancy.is_internal_hidden is True
    assert candidate.next_contact_at.year == 2026
    assert candidate.next_contact_owner_id == "hr-1"


def test_vnr_hire_status_values():
    from app.db.v1.enums import VnrHireStatus

    assert VnrHireStatus.in_work.value == "in_work"
    assert VnrHireStatus.left.value == "left"


def test_vacancy_properties_default_hh_standard():
    from app.schemas.v1.vacancies import VacancyProperties

    props = VacancyProperties()
    dumped = props.model_dump()
    assert dumped["properties"][0]["property_type"] == "HH_STANDARD"


def test_test_update_schema_partial():
    from app.schemas.v1.tests import TestUpdate

    data = TestUpdate(name="Updated name", description=None)
    dumped = data.model_dump(exclude_unset=True)
    assert dumped["name"] == "Updated name"
    assert "test_type" not in dumped


def test_vacancy_static_routes_registered_before_id_route():
    paths = [getattr(r, "path", None) for r in vacancy_router.routes]
    paths = [p for p in paths if p]
    active_idx = paths.index("/vacancy/active/telegram/{telegram_id}")
    hh_idx = paths.index("/vacancy/hh/{hh_id}")
    id_idx = paths.index("/vacancy/{vacancy_id}")
    assert active_idx < id_idx
    assert hh_idx < id_idx


def test_offer_and_test_update_routes_exist():
    from app.endpoints.v1.messages import router as messages_router
    from app.endpoints.v1.tests import router as tests_router
    from app.endpoints.v1.psych_tests import router as psych_router, public_router as psych_public
    from app.endpoints.v1.public_professional_tests import (
        router as public_prof_router,
        public_router as public_prof_public,
    )

    msg_paths = {getattr(r, "path", None) for r in messages_router.routes}
    assert "/candidate/offer" in msg_paths
    assert "/candidate/send-offer" in msg_paths
    assert "/candidate/interview-invite" in msg_paths

    test_paths = {getattr(r, "path", None) for r in tests_router.routes}
    assert "/test/{test_id}" in test_paths
    methods = set()
    for r in tests_router.routes:
        if getattr(r, "path", None) == "/test/{test_id}":
            methods |= set(getattr(r, "methods", set()) or [])
    assert "PUT" in methods or "PATCH" in methods

    psych_paths = {getattr(r, "path", None) for r in psych_router.routes}
    assert "/psych/instruments" in psych_paths
    assert "/psych/results" in psych_paths
    assert "/psych/results/{result_id}" in psych_paths

    public_paths = {getattr(r, "path", None) for r in psych_public.routes}
    assert "/public/psych/instruments" in public_paths
    assert "/public/psych/instruments/{instrument_id}" in public_paths
    assert "/public/psych/results" in public_paths

    prof_public_paths = {getattr(r, "path", None) for r in public_prof_public.routes}
    assert "/public/tests/{test_id}" in prof_public_paths
    assert "/public/tests/results" in prof_public_paths

    prof_hr_paths = {getattr(r, "path", None) for r in public_prof_router.routes}
    assert "/public-test-results" in prof_hr_paths
    assert "/public-test-results/{result_id}" in prof_hr_paths

    # role_id accepted on candidates list endpoint
    import inspect
    from app.endpoints.v1.candidates import get_all_candidates
    params = inspect.signature(get_all_candidates).parameters
    assert "role_id" in params
    assert "vacancy_id" in params

    vac_paths = {getattr(r, "path", None) for r in vacancy_router.routes}
    assert "/vacancies/options" in vac_paths
    assert "/vacancies/published" in vac_paths


def test_vacancy_hh_proxy_routes_registered():
    by_path = {}
    for route in vacancy_router.routes:
        path = getattr(route, "path", None)
        methods = set(getattr(route, "methods", set()) or [])
        if not path:
            continue
        by_path.setdefault(path, set()).update(methods)

    assert "POST" in by_path.get("/vacancy/{vacancy_id}/hh", set())
    assert "PUT" in by_path.get("/vacancy/{vacancy_id}/hh", set())
    assert "DELETE" in by_path.get("/vacancy/{vacancy_id}/hh", set())
    assert "GET" in by_path.get("/hh/connect/link", set())
    assert "GET" in by_path.get("/hh/connect/status", set())
    assert "GET" in by_path.get("/hh/autosearch/vacancies/available", set())
    assert "GET" in by_path.get("/hh/autosearch/active", set())
    assert "POST" in by_path.get("/hh/autosearch/{vacancy_id}/activate", set())
    assert "POST" in by_path.get("/hh/autosearch/{vacancy_id}/deactivate", set())
    assert "PATCH" in by_path.get("/hh/autosearch/{vacancy_id}/invite-limit", set())
    assert "GET" in by_path.get("/hh/subscription", set())
    assert "POST" in by_path.get("/hh/negotiations/subscribe", set())


def test_hr_lifecycle_routes_registered():
    from app.endpoints.v1.hiring_request import router as hr_router
    from app.endpoints.v1.employees import router as emp_router
    from app.endpoints.v1.approvals import router as appr_router
    from app.endpoints.v1.audit_ops import router as audit_router
    from app.endpoints.v1.adaptation import router as adaptation_router

    hr_paths = {getattr(r, "path", None) for r in hr_router.routes}
    assert "/hiring-requests/{request_id}/create-vacancy" in hr_paths
    assert "/hiring-requests/{request_id}/publish-hh" in hr_paths
    assert "/hiring-requests/{request_id}" in hr_paths

    emp_paths = {getattr(r, "path", None) for r in emp_router.routes}
    assert "/employees" in emp_paths
    assert "/employees/{employee_id}" in emp_paths

    from app.endpoints.v1.vnr import router as vnr_router

    vnr_paths = {getattr(r, "path", None) for r in vnr_router.routes}
    assert "/vnr-hires" in vnr_paths
    assert "/analytics/hr-profile" in vnr_paths

    appr_paths = {getattr(r, "path", None) for r in appr_router.routes}
    assert "/approvals" in appr_paths

    audit_paths = {getattr(r, "path", None) for r in audit_router.routes}
    assert "/audit-logs" in audit_paths
    assert "/candidate/{candidate_id}/stage-history" in audit_paths
    assert "/candidate/{candidate_id}/comments" in audit_paths
    assert "/candidate/{candidate_id}/comments/{comment_id}" in audit_paths

    adapt_paths = {getattr(r, "path", None) for r in adaptation_router.routes}
    assert "/adaptation/catalog" in adapt_paths
    assert "/adaptation/checkpoints" in adapt_paths
    assert "/adaptation/checkpoints/{checkpoint_id}" in adapt_paths
    assert "/adaptation/enrollments" in adapt_paths
    assert "/adaptation/enrollments/{enrollment_id}" in adapt_paths
    assert "/adaptation/reports" in adapt_paths


def test_main_py_has_no_syntax_errors():
    import ast
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "main.py"
    ast.parse(src.read_text(encoding="utf-8"))
