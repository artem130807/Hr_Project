"""Adaptation domain, reports, enroll/list service and API (mocked persistence)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.adaptation.catalog import catalog, form_for
from app.adaptation.reports import build_reports, manager_safe_report
from app.adaptation.rules import (
    KIND_CONTROL_2M,
    KIND_MONTH_2,
    KIND_WEEK_1,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_NONE,
    ROLE_EMPLOYEE,
    ROLE_HR,
    ROLE_MANAGER,
    SAMARA,
    STATUS_COLLECTING,
    STATUS_COMPLETED,
    STATUS_DATA_COLLECTED,
    STATUS_OVERDUE,
    STATUS_PLANNED,
    attention_bucket,
    compute_risk,
    compute_status,
    outcome_label,
    overdue_starts_at,
    plan_date_for,
    roles_for_kind,
)
from app.adaptation import service as svc
from app.endpoints.v1 import adaptation as ep
from app.schemas.v1.adaptation import AdaptationAnswerIn, AdaptationEnrollIn, AdaptationCheckpointRead
from app.db.v1.models import AdaptationModuleSettings


def test_plan_dates_from_hire():
    hired = date(2026, 6, 17)
    assert plan_date_for("week_1", hired) == date(2026, 6, 24)
    assert plan_date_for("month_1", hired) == date(2026, 7, 17)
    assert plan_date_for("month_2", hired) == date(2026, 8, 17)
    assert plan_date_for("control_2m", hired) == date(2026, 8, 17)
    assert plan_date_for("extra", hired, extra_on=date(2026, 8, 26)) == date(2026, 8, 26)


def test_checkpoint_response_contract_keeps_generated_form_links():
    payload = {
        "id": 1, "enrollment_id": 2, "employee_id": 3, "full_name": "Иванов",
        "kind": "week_1", "kind_label": "1 неделя", "plan_date": date(2026, 9, 10),
        "status": "planned", "status_label": "Запланирован", "risk": "none",
        "risk_label": "Не рассчитан", "risk_signals": {}, "outcome": "Не рассчитан",
        "progress": [], "form_links": [{"role": "employee", "token": "abc", "url": "https://hr.example/adaptation/forms/abc"}],
    }
    result = AdaptationCheckpointRead.model_validate(payload).model_dump()

    assert result["form_links"][0]["url"].endswith("/adaptation/forms/abc")


@pytest.mark.asyncio
async def test_archive_changes_only_requested_enrollment_and_is_idempotent():
    requested = SimpleNamespace(id=7, archived=False, archive_reason=None)
    unrelated = SimpleNamespace(id=8, archived=False, archive_reason=None)
    enrollment_result = MagicMock()
    enrollment_result.scalar_one_or_none.return_value = requested
    empty_related = MagicMock()
    empty_related.scalars.return_value.all.return_value = []
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[enrollment_result, empty_related, empty_related])
    db.flush = AsyncMock()

    archived = await svc.archive_enrollment(db, enrollment_id=7, reason="Перевод")

    assert archived is requested
    assert requested.archived is True
    assert requested.archive_reason == "Перевод"
    assert unrelated.archived is False

    # A repeated request is a successful no-op and cannot touch related rows.
    repeated_result = MagicMock()
    repeated_result.scalar_one_or_none.return_value = requested
    db.execute = AsyncMock(return_value=repeated_result)
    assert await svc.archive_enrollment(db, enrollment_id=7, reason="Повтор") is requested
    assert requested.archive_reason == "Перевод"
    assert db.execute.await_count == 1


def test_manager_not_on_week1_and_control():
    assert ROLE_MANAGER not in roles_for_kind(KIND_WEEK_1)
    assert roles_for_kind(KIND_CONTROL_2M) == (ROLE_HR,)
    assert ROLE_MANAGER in roles_for_kind(KIND_MONTH_2)


def test_weekend_plan_shifts_to_weekday():
    assert plan_date_for("month_1", date(2026, 1, 31)) == date(2026, 3, 2)
    assert plan_date_for("extra", date(2026, 1, 1), extra_on=date(2026, 8, 29)) == date(2026, 8, 31)


def test_overdue_from_0900_next_day_samara():
    plan = date(2026, 8, 23)
    start = overdue_starts_at(plan)
    assert start.tzinfo == SAMARA
    assert start.hour == 9
    assert start.date() == date(2026, 8, 24)
    before = datetime(2026, 8, 24, 8, 59, tzinfo=SAMARA)
    after = datetime(2026, 8, 24, 9, 0, tzinfo=SAMARA)
    answers = []
    assert compute_status(kind=KIND_MONTH_2, plan_date=plan, answers=answers, now=before) == STATUS_COLLECTING
    assert compute_status(kind=KIND_MONTH_2, plan_date=plan, answers=answers, now=after) == STATUS_OVERDUE


def test_status_planned_collecting_data_hr_complete():
    plan = date(2026, 8, 25)
    now = datetime(2026, 8, 24, 12, 0, tzinfo=SAMARA)
    assert compute_status(kind=KIND_MONTH_2, plan_date=plan, answers=[], now=now) == STATUS_PLANNED
    now2 = datetime(2026, 8, 25, 12, 0, tzinfo=SAMARA)
    assert compute_status(kind=KIND_MONTH_2, plan_date=plan, answers=[], now=now2) == STATUS_COLLECTING
    both = [{"role": ROLE_EMPLOYEE}, {"role": ROLE_MANAGER}]
    assert (
        compute_status(kind=KIND_MONTH_2, plan_date=plan, answers=both, now=now2)
        == STATUS_DATA_COLLECTED
    )
    all_roles = both + [{"role": ROLE_HR}]
    assert compute_status(kind=KIND_MONTH_2, plan_date=plan, answers=all_roles, now=now2) == STATUS_COMPLETED


def test_control_ready_for_hr_without_employee_overdue():
    plan = date(2026, 8, 23)
    after = datetime(2026, 8, 24, 9, 0, tzinfo=SAMARA)
    assert compute_status(kind=KIND_CONTROL_2M, plan_date=plan, answers=[], now=after) == STATUS_DATA_COLLECTED
    before = datetime(2026, 8, 22, 12, 0, tzinfo=SAMARA)
    assert compute_status(kind=KIND_CONTROL_2M, plan_date=plan, answers=[], now=before) == STATUS_PLANNED


def test_week1_data_collected_without_manager():
    plan = date(2026, 8, 18)
    now = datetime(2026, 8, 20, 12, 0, tzinfo=SAMARA)
    assert (
        compute_status(
            kind=KIND_WEEK_1,
            plan_date=plan,
            answers=[{"role": ROLE_EMPLOYEE}],
            now=now,
        )
        == STATUS_DATA_COLLECTED
    )


def test_risk_thresholds_and_missing_form():
    assert compute_risk(None, kind=KIND_MONTH_2) == RISK_NONE
    assert compute_risk({"a": 5, "b": 4, "c": 4}, kind=KIND_MONTH_2) == RISK_LOW
    assert compute_risk({"a": 3, "b": 3, "c": 3}, kind=KIND_MONTH_2) == RISK_MEDIUM
    assert compute_risk({"a": 1, "b": 2, "c": 2}, kind=KIND_MONTH_2) == RISK_HIGH
    assert compute_risk({"c2_ok": True}, kind=KIND_CONTROL_2M) == RISK_NONE
    assert compute_risk({"m1_role": 5, "m1_doubts": 5}, kind="month_1") == RISK_LOW
    cores = {"core_e1": 5, "core_e2": 5, "core_e3": 4, "core_e4": 4, "core_e5": 5}
    assert compute_risk(cores, kind="month_1") == RISK_LOW
    assert compute_risk({**cores, "core_e1": 2, "core_e2": 2}, kind="month_1") == RISK_HIGH
    assert outcome_label(RISK_NONE, kind=KIND_CONTROL_2M, employee_submitted=True) == "Без анкеты"


def test_this_week_is_planned_in_iso_week_only():
    week_start = date(2026, 8, 24)
    week_end = date(2026, 8, 30)
    assert attention_bucket(STATUS_PLANNED, date(2026, 8, 25), week_start, week_end) == "this_week"
    assert attention_bucket(STATUS_COLLECTING, date(2026, 8, 24), week_start, week_end) is None
    assert attention_bucket(STATUS_PLANNED, date(2026, 8, 10), week_start, week_end) is None
    assert attention_bucket(STATUS_OVERDUE, date(2026, 8, 23), week_start, week_end) == "overdue"


def test_catalog_has_approved_kinds():
    cat = catalog()
    assert set(cat) >= {"week_1", "month_1", "month_2", "control_2m", "extra"}
    assert form_for("week_1", ROLE_EMPLOYEE)[0]["id"] == "core_e1"
    assert form_for("control_2m", ROLE_EMPLOYEE) == []
    assert any(q["id"] == "core_m1" for q in form_for("month_1", ROLE_MANAGER))
    assert form_for("month_1", ROLE_HR)[0]["id"] == "hr_comment"


def test_catalog_month_manager_options_match_approved_questionnaire_and_are_isolated():
    first = form_for("month_1", ROLE_MANAGER)
    support = next(question for question in first if question["id"] == "mgr1_support")
    risks = next(question for question in first if question["id"] == "mgr1_risks")

    assert support["options"] == [
        "разъяснение задач",
        "обучение",
        "регулярная обратная связь",
        "наставник",
        "корректировка нагрузки",
        "дополнительные материалы или доступы",
        "поддержка не требовалась",
        "другое",
    ]
    assert support["exclusive_options"] == ["поддержка не требовалась"]
    assert risks["exclusive_options"] == ["значимых рисков нет"]

    support["options"].append("поврежденный вариант")
    second = form_for("month_1", ROLE_MANAGER)
    assert "поврежденный вариант" not in next(
        question for question in second if question["id"] == "mgr1_support"
    )["options"]


def test_catalog_forms_keep_approved_question_counts_and_stage_specific_hr_talk_texts():
    without_generated_core_explanations = lambda questions: [
        question for question in questions if not question["id"].endswith("_explain")
    ]

    assert len(without_generated_core_explanations(form_for("week_1", ROLE_EMPLOYEE))) == 24
    assert len(without_generated_core_explanations(form_for("month_1", ROLE_EMPLOYEE))) == 26
    assert len(without_generated_core_explanations(form_for("month_2", ROLE_EMPLOYEE))) == 28
    assert len(without_generated_core_explanations(form_for("month_1", ROLE_MANAGER))) == 24
    assert len(without_generated_core_explanations(form_for("month_2", ROLE_MANAGER))) == 25
    assert len(form_for("month_1", ROLE_HR)) == 1
    assert len(without_generated_core_explanations(form_for("extra", ROLE_EMPLOYEE))) == 15

    assert next(q for q in form_for("week_1", ROLE_EMPLOYEE) if q["id"] == "w_talk")["text"] == (
        "Хотели бы вы конфиденциально поговорить с HR по итогам первой недели?"
    )
    assert next(q for q in form_for("month_1", ROLE_EMPLOYEE) if q["id"] == "m1_talk")["text"] == (
        "Хотели бы вы конфиденциально поговорить с HR по итогам первого месяца?"
    )
    assert next(q for q in form_for("month_2", ROLE_EMPLOYEE) if q["id"] == "m2_talk")["text"] == (
        "Хотели бы вы конфиденциально поговорить с HR по итогам двух месяцев?"
    )


def test_catalog_uses_distinct_special_scale_values():
    employee = form_for("month_1", ROLE_EMPLOYEE)
    manager = form_for("month_1", ROLE_MANAGER)
    employee_kpi = next(question for question in employee if question["id"] == "m1_kpi")
    feedback = next(question for question in employee if question["id"] == "m1_fb_useful")
    manager_kpi = next(question for question in manager if question["id"] == "mgr1_kpi")

    assert employee_kpi["special_options"] == [
        {"value": "not_applicable", "label": "не применимо"}
    ]
    assert feedback["special_options"] == [
        {"value": "insufficient_data", "label": "недостаточно данных"}
    ]
    assert [item["value"] for item in manager_kpi["special_options"]] == [
        "not_applicable",
        "insufficient_observations",
    ]


def test_core_history_contains_employee_and_manager_series_for_conditional_explanations():
    previous = SimpleNamespace(
        id=1,
        plan_date=date(2026, 8, 1),
        answers=[
            SimpleNamespace(role=ROLE_EMPLOYEE, payload={"core_e1": 4}),
            SimpleNamespace(role=ROLE_MANAGER, payload={"core_m1": 2}),
        ],
    )
    current = SimpleNamespace(id=2, plan_date=date(2026, 9, 1), answers=[])
    enrollment = SimpleNamespace(checkpoints=[previous, current])
    previous.enrollment = enrollment
    current.enrollment = enrollment

    assert svc.core_history_from_checkpoint(current) == {"core_e1": 4, "core_m1": 2}


def test_answer_payload_is_validated_against_server_catalog():
    with pytest.raises(ValueError, match="обязательное поле"):
        svc.validate_answer_payload("month_1", ROLE_HR, {})
    assert svc.validate_answer_payload(
        "month_1", ROLE_HR, {"hr_comment": "  Итог согласован  "}
    ) == {"hr_comment": "Итог согласован"}
    with pytest.raises(ValueError, match="устарела"):
        svc.validate_answer_payload(
            "month_1", ROLE_HR, {"hr_comment": "Итог", "unknown": "field"}
        )


def test_answer_payload_rejects_mutually_exclusive_multi_choices(monkeypatch):
    monkeypatch.setattr(
        svc,
        "form_for",
        lambda _kind, _role: [{
            "id": "support",
            "text": "Какая поддержка предоставлена?",
            "type": "multi",
            "required": True,
            "options": ["обучение", "поддержка не требовалась"],
            "exclusive_options": ["поддержка не требовалась"],
        }],
    )

    with pytest.raises(ValueError, match="Взаимоисключающие варианты"):
        svc.validate_answer_payload(
            "month_1",
            ROLE_MANAGER,
            {"support": ["обучение", "поддержка не требовалась"]},
        )


def test_answer_payload_accepts_distinct_special_scale_values(monkeypatch):
    monkeypatch.setattr(
        svc,
        "form_for",
        lambda _kind, _role: [{
            "id": "score",
            "text": "Оценка",
            "type": "scale_na",
            "required": True,
            "special_options": [
                {"value": "not_applicable", "label": "не применимо"},
                {"value": "insufficient_observations", "label": "недостаточно наблюдений"},
            ],
        }],
    )

    assert svc.validate_answer_payload(
        "month_1", ROLE_MANAGER, {"score": "not_applicable"}
    ) == {"score": "not_applicable"}
    assert svc.validate_answer_payload(
        "month_1", ROLE_MANAGER, {"score": "insufficient_observations"}
    ) == {"score": "insufficient_observations"}


def test_invalid_adaptation_settings_fall_back_to_safe_defaults():
    settings = AdaptationModuleSettings()
    settings.timezone = "Invalid/Timezone"
    settings.overdue_time = None
    settings.overdue_enabled = True
    settings.risk_rules = ["broken"]

    options = svc._status_options(settings)

    assert options["timezone_name"] == "Europe/Samara"
    assert options["overdue_clock"].isoformat() == "09:00:00"
    assert options["risk_rules"] == {}


@pytest.mark.asyncio
async def test_list_skips_one_malformed_legacy_checkpoint_instead_of_returning_500():
    employee = SimpleNamespace(
        id=1, full_name="Иванов", department="hr", position="HR",
        date_hired=date(2026, 9, 1), date_fired=None, photo_url=None,
    )
    enrollment = SimpleNamespace(
        employee=employee, temporary_employee=None, checkpoints=[], archived=False,
        temporary_employee_id=None, start_date=date(2026, 9, 1), route="full",
        manager_user_id=None, manager_name=None,
    )
    malformed_answer = SimpleNamespace(payload=["not-a-pair"], role=ROLE_EMPLOYEE)
    checkpoint = SimpleNamespace(
        id=11, enrollment_id=2, kind=KIND_WEEK_1,
        plan_date=date(2026, 9, 8), fact_date=None, closed=False,
        answers=[malformed_answer], enrollment=enrollment,
    )
    enrollment.checkpoints = [checkpoint]
    checkpoint_result = MagicMock()
    checkpoint_result.scalars.return_value.unique.return_value.all.return_value = [checkpoint]
    settings_result = MagicMock()
    settings_result.scalar_one_or_none.return_value = None
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[checkpoint_result, settings_result])

    result = await svc.list_checkpoints(db, year=2026, month=9)

    assert result["items"] == []
    assert result["total"] == 0


def test_manager_safe_report_hides_employee_free_text():
    row = {
        "full_name": "Иванов",
        "kind": "month_2",
        "status": "completed",
        "risk": "low",
        "answers": [
            {"role": "employee", "payload": {"m2_issues": "хочу уволиться", "m2_fit": 2}},
            {"role": "hr", "payload": {"manager_summary": "Поддержать наставником", "hr_comment": "Только для HR", "hr_recommend": 4}},
        ],
    }
    safe = manager_safe_report(row)
    dumped = str(safe)
    assert "хочу уволиться" not in dumped
    assert safe["hr_notes"] == "Поддержать наставником"
    reports = build_reports([row])
    assert reports["probation"]["decision"] == "confirmed"


@pytest.mark.asyncio
async def test_enroll_creates_three_standard_checkpoints():
    db = MagicMock()
    employee = SimpleNamespace(id=5, date_hired=date(2026, 6, 17), date_fired=None)
    db.get = AsyncMock(return_value=employee)
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=empty)
    added = []
    db.add = added.append

    async def _flush():
        if added and getattr(added[0], "id", None) is None:
            added[0].id = 9

    db.flush = AsyncMock(side_effect=_flush)
    result = await svc.enroll_employee(db, employee_id=5)
    assert result.id == 9
    kinds = [c.kind for c in added if getattr(c, "kind", None)]
    assert kinds == ["week_1", "month_1", "month_2"]
    assert [c.plan_date for c in added if getattr(c, "kind", None)] == [
        date(2026, 6, 24),
        date(2026, 7, 17),
        date(2026, 8, 17),
    ]



@pytest.mark.asyncio
async def test_enroll_control_replaces_month_two():
    db = MagicMock()
    employee = SimpleNamespace(id=5, date_hired=date(2026, 6, 24), date_fired=None)
    db.get = AsyncMock(return_value=employee)
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=empty)
    added = []
    db.add = added.append

    async def _flush():
        if added and getattr(added[0], "id", None) is None:
            added[0].id = 3

    db.flush = AsyncMock(side_effect=_flush)
    await svc.enroll_employee(db, employee_id=5, include_control_2m=True)
    kinds = [c.kind for c in added if getattr(c, "kind", None)]
    assert kinds == ["week_1", "month_1", "control_2m"]
    assert "month_2" not in kinds


@pytest.mark.asyncio
async def test_enroll_control_route_is_hr_only_checkpoint():
    db = MagicMock()
    employee = SimpleNamespace(id=5, date_hired=date(2026, 6, 24), date_fired=None)
    db.get = AsyncMock(return_value=employee)
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=empty)
    added = []
    db.add = added.append

    async def _flush():
        if added and getattr(added[0], "id", None) is None:
            added[0].id = 3

    db.flush = AsyncMock(side_effect=_flush)
    await svc.enroll_employee(db, employee_id=5, route="control")
    kinds = [c.kind for c in added if getattr(c, "kind", None)]
    assert kinds == ["control_2m"]


@pytest.mark.asyncio
async def test_enroll_rejects_duplicate():
    db = MagicMock()
    db.get = AsyncMock(return_value=SimpleNamespace(id=1, date_hired=date(2026, 1, 1), date_fired=None))
    found = MagicMock()
    found.scalar_one_or_none.return_value = object()
    db.execute = AsyncMock(return_value=found)
    with pytest.raises(ValueError, match="уже на адаптации"):
        await svc.enroll_employee(db, employee_id=1)


@pytest.mark.asyncio
async def test_enroll_from_erp_creates_local_employee():
    db = MagicMock()
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=empty)
    added = []
    db.add = added.append
    flush_count = {"n": 0}

    async def _flush():
        flush_count["n"] += 1
        if flush_count["n"] == 1:
            added[0].id = 10
        elif len(added) > 1:
            added[1].id = 3

    db.flush = AsyncMock(side_effect=_flush)
    raw = {
        "id": "erp-1",
        "name": "Иванов",
        "email": "i@ex.com",
        "is_active": True,
        "role": {"name": "Менеджер"},
        "create_dt": "2026-01-15",
    }
    with patch.object(svc.ErpClient, "list_users", new=AsyncMock(return_value=[raw])):
        enrollment = await svc.enroll_employee(db, erp_user_id="erp-1")
    emp = added[0]
    assert emp.erp_user_id == "erp-1"
    assert emp.full_name == "Иванов"
    assert emp.department == "Менеджер"
    assert emp.date_hired == date(2026, 1, 15)
    assert enrollment.employee_id == 10
    assert any(getattr(obj, "kind", None) == "week_1" for obj in added)


def test_serialize_progress_muted_manager_on_week1():
    emp = SimpleNamespace(
        id=1,
        full_name="Карпеева",
        department="Ресторан",
        position="Менеджер",
        date_hired=date(2026, 8, 18),
    )
    cp = SimpleNamespace(
        id=3,
        enrollment_id=2,
        kind=KIND_WEEK_1,
        plan_date=date(2026, 8, 25),
        fact_date=None,
        closed=False,
        answers=[],
    )
    row = svc.serialize_checkpoint(cp, emp, now=datetime(2026, 8, 24, 12, tzinfo=SAMARA))
    states = {d["role"]: d["state"] for d in row["progress"]}
    assert states[ROLE_MANAGER] == "muted"
    assert row["status"] == STATUS_PLANNED


@pytest.mark.asyncio
async def test_submit_answer_rejects_muted_manager():
    db = MagicMock()
    enrollment = SimpleNamespace(closed=False, archived=False, checkpoints=[])
    cp = SimpleNamespace(
        id=1, kind=KIND_WEEK_1, answers=[], fact_date=None,
        plan_date=date(2026, 9, 10),
        closed=False, finalized_at=None, forced_completed_at=None,
        enrollment=enrollment,
    )
    enrollment.checkpoints = [cp]
    result = MagicMock()
    result.scalar_one_or_none.return_value = cp
    db.execute = AsyncMock(return_value=result)
    with pytest.raises(ValueError, match="не участвует"):
        await svc.submit_answer(db, checkpoint_id=1, role=ROLE_MANAGER, payload={})
    db.get.assert_not_called()


@pytest.mark.asyncio
async def test_submit_answer_locks_employee_resubmit():
    db = MagicMock()
    existing = SimpleNamespace(role=ROLE_EMPLOYEE, payload={"core_e1": 4}, submitted_at=None)
    enrollment = SimpleNamespace(closed=False, archived=False, checkpoints=[])
    cp = SimpleNamespace(
        id=1, kind=KIND_WEEK_1, answers=[existing], fact_date=None,
        closed=False, finalized_at=None, forced_completed_at=None,
        enrollment=enrollment,
    )
    enrollment.checkpoints = [cp]
    result = MagicMock()
    result.scalar_one_or_none.return_value = cp
    db.execute = AsyncMock(return_value=result)
    with pytest.raises(ValueError, match="заблокированы"):
        await svc.submit_answer(db, checkpoint_id=1, role=ROLE_EMPLOYEE, payload={"core_e1": 1})


@pytest.mark.asyncio
async def test_submit_answer_uses_explicit_refresh_instead_of_identity_map_get():
    db = MagicMock()
    enrollment = SimpleNamespace(closed=False, archived=False, checkpoints=[])
    cp = SimpleNamespace(
        id=1, kind=KIND_WEEK_1, answers=[], fact_date=None,
        plan_date=date(2026, 9, 10),
        closed=False, finalized_at=None, forced_completed_at=None,
        enrollment=enrollment,
    )
    enrollment.checkpoints = [cp]
    checkpoint_result = MagicMock()
    checkpoint_result.scalar_one_or_none.return_value = cp
    form = SimpleNamespace(submitted_at=None, locked=False)
    form_result = MagicMock()
    form_result.scalar_one_or_none.return_value = form
    db.execute = AsyncMock(side_effect=[checkpoint_result, form_result])
    added = []
    db.add = added.append

    async def flush():
        for item in added:
            if item.__class__.__name__ == "AdaptationAnswer" and item.id is None:
                item.id = 77

    db.flush = AsyncMock(side_effect=flush)
    db.get = AsyncMock(side_effect=AssertionError("identity-map get must not be used"))

    answer = await svc.submit_answer(
        db,
        checkpoint_id=1,
        role=ROLE_HR,
        payload={"hr_comment": "Проверено"},
    )

    assert answer.id == 77
    assert answer.payload == {"hr_comment": "Проверено"}
    assert form.submitted_at is not None
    db.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_extra_checkpoint_creates_participant_links():
    enrollment = SimpleNamespace(
        id=4, closed=False, archived=False, manager_user_id="manager-1"
    )
    db = MagicMock()
    db.get = AsyncMock(return_value=enrollment)
    added = []
    db.add = added.append

    async def flush():
        for item in added:
            if item.__class__.__name__ == "AdaptationCheckpoint" and item.id is None:
                item.id = 12

    db.flush = AsyncMock(side_effect=flush)

    await svc.add_extra_checkpoint(
        db, enrollment_id=4, plan_date=date(2026, 10, 1), kind="extra"
    )

    forms = [item for item in added if item.__class__.__name__ == "AdaptationParticipantForm"]
    assert {item.role for item in forms} == set(roles_for_kind("extra"))


@pytest.mark.asyncio
async def test_endpoint_catalog():
    payload = await ep.get_catalog()
    assert "week_1" in payload


@pytest.mark.asyncio
async def test_endpoint_enroll_maps_errors():
    db = MagicMock()
    with patch.object(ep.svc, "enroll_employee", side_effect=LookupError("Employee not found")):
        with pytest.raises(HTTPException) as exc:
            await ep.enroll_adaptation(AdaptationEnrollIn(employee_id=99), db, {"user_id": "test-hr", "role": "hr"})
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_endpoint_answer_commits(monkeypatch):
    db = MagicMock()
    db.commit = AsyncMock()
    detail = {"id": 1, "status": "collecting"}

    async def _submit(*args, **kwargs):
        return SimpleNamespace(id=4)

    async def _detail(db, cid):
        return detail

    monkeypatch.setattr(ep.svc, "submit_answer", _submit)
    monkeypatch.setattr(ep.svc, "get_checkpoint_detail", _detail)
    monkeypatch.setattr(ep, "write_audit", AsyncMock())
    out = await ep.submit_adaptation_answer(
        1, AdaptationAnswerIn(role="employee", payload={"m2_fit": 4}), db, {"user_id": "test-hr", "role": "hr"}
    )
    assert out["id"] == 1
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_employee_talk_hr_answer_publishes_after_commit(monkeypatch):
    db = MagicMock()
    db.commit = AsyncMock()
    detail = {"id": 8, "full_name": "Иванов", "status": "collecting"}
    publish = AsyncMock()

    monkeypatch.setattr(ep.svc, "submit_answer", AsyncMock())
    monkeypatch.setattr(ep.svc, "get_checkpoint_detail", AsyncMock(return_value=detail))
    monkeypatch.setattr(ep, "write_audit", AsyncMock())
    monkeypatch.setattr(ep, "publish_adaptation_talk_hr", publish)

    out = await ep.submit_adaptation_answer(
        8,
        AdaptationAnswerIn(
            role="employee",
            payload={"talk_hr": "да", "talk_hr_topic": "нагрузка"},
        ),
        db,
        {"user_id": "test-hr", "role": "hr"},
    )

    assert out == detail
    db.commit.assert_awaited_once()
    publish.assert_awaited_once()
    sent = publish.await_args.args[0]
    assert sent["id"] == 8
    assert sent["talk_hr_topic"] == "нагрузка"


@pytest.mark.asyncio
async def test_talk_hr_not_published_for_hr_form(monkeypatch):
    db = MagicMock()
    db.commit = AsyncMock()
    publish = AsyncMock()
    monkeypatch.setattr(ep.svc, "submit_answer", AsyncMock())
    monkeypatch.setattr(ep.svc, "get_checkpoint_detail", AsyncMock(return_value={"id": 8}))
    monkeypatch.setattr(ep, "write_audit", AsyncMock())
    monkeypatch.setattr(ep, "publish_adaptation_talk_hr", publish)

    await ep.submit_adaptation_answer(
        8,
        AdaptationAnswerIn(role="hr", payload={"talk_hr": "да"}),
        db,
        {"user_id": "test-hr", "role": "hr"},
    )
    publish.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("draft_fails", [False, True])
async def test_public_answer_does_not_access_expired_form_after_commit(monkeypatch, draft_fails):
    state = {"committed": False}
    enrollment = SimpleNamespace(closed=False, archived=False)
    checkpoint = SimpleNamespace(
        forced_completed_at=None,
        closed=False,
        enrollment=enrollment,
    )

    class ExpiringForm:
        def __getattribute__(self, name):
            if name in {
                "revoked_at", "locked", "checkpoint", "checkpoint_id",
                "role", "participant_user_id",
            } and state["committed"]:
                raise AssertionError(f"expired ORM attribute accessed after commit: {name}")
            return object.__getattribute__(self, name)

    form = ExpiringForm()
    form.revoked_at = None
    form.locked = False
    form.checkpoint = checkpoint
    form.checkpoint_id = 42
    form.role = "employee"
    form.participant_user_id = "erp-user-42"
    result = MagicMock()
    result.scalar_one_or_none.return_value = form
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    savepoints = []
    @asynccontextmanager
    async def nested_transaction():
        savepoints.append("begin")
        try:
            yield
        except Exception:
            savepoints.append("rollback")
            raise

    db.begin_nested = MagicMock(side_effect=nested_transaction)
    monkeypatch.setattr(ep, "_ensure_automatic_draft", AsyncMock(
        side_effect=RuntimeError("draft failure") if draft_fails else None
    ))

    async def commit():
        state["committed"] = True

    db.commit = AsyncMock(side_effect=commit)
    monkeypatch.setattr(ep.svc, "submit_answer", AsyncMock())
    monkeypatch.setattr(
        ep.svc,
        "get_checkpoint_detail",
        AsyncMock(return_value={"id": 42, "status": "data_collected"}),
    )

    response = await ep.submit_public_adaptation_form(
        "token", {"payload": {"core_e1": 5}}, db
    )

    assert response == {"submitted": True, "locked": True}
    assert savepoints == (["begin", "rollback"] if draft_fails else ["begin"])
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_force_complete_survives_legacy_audit_schema(monkeypatch):
    @asynccontextmanager
    async def nested_transaction():
        yield

    db = MagicMock()
    db.begin_nested = MagicMock(side_effect=nested_transaction)
    db.commit = AsyncMock()
    monkeypatch.setattr(
        ep.svc,
        "force_complete_checkpoint",
        AsyncMock(return_value=SimpleNamespace(id=7, fact_date=date(2026, 9, 10))),
    )
    monkeypatch.setattr(
        ep,
        "_write_audit",
        AsyncMock(side_effect=RuntimeError("actor_id is integer")),
    )

    response = await ep.force_complete_adaptation_checkpoint(
        7,
        ep.AdaptationForceCompleteIn(reason="Формы недоступны"),
        db,
        {"user_id": "uuid-user", "role": "hr"},
    )

    assert response["status"] == "forced_completed"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_enroll_without_hire_date_uses_today():
    db = MagicMock()
    employee = SimpleNamespace(id=5, date_hired=None, date_fired=None)
    db.get = AsyncMock(return_value=employee)
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=empty)
    added = []
    db.add = added.append

    async def _flush():
        if added and getattr(added[0], "id", None) is None:
            added[0].id = 9

    db.flush = AsyncMock(side_effect=_flush)
    result = await svc.enroll_employee(db, employee_id=5)
    assert result.id == 9
    plans = [c.plan_date for c in added if getattr(c, "kind", None)]
    assert all(isinstance(d, date) for d in plans)
    assert len(plans) == 3


def test_serialize_allows_missing_department():
    emp = SimpleNamespace(
        id=1,
        full_name="Петров",
        department=None,
        position=None,
        date_hired=None,
    )
    cp = SimpleNamespace(
        id=3,
        enrollment_id=2,
        kind=KIND_WEEK_1,
        plan_date=date(2026, 8, 25),
        fact_date=None,
        closed=False,
        answers=[],
    )
    row = svc.serialize_checkpoint(cp, emp, now=datetime(2026, 8, 24, 12, tzinfo=SAMARA))
    assert row["department"] == ""
    assert row["position"] == ""
    assert row["full_name"] == "Петров"


@pytest.mark.asyncio
async def test_enroll_from_erp_without_hr_role_map():
    db = MagicMock()
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=empty)
    added = []
    db.add = added.append
    flush_count = {"n": 0}

    async def _flush():
        flush_count["n"] += 1
        if flush_count["n"] == 1:
            added[0].id = 10
        elif len(added) > 1:
            added[1].id = 3

    db.flush = AsyncMock(side_effect=_flush)
    raw = {
        "id": "erp-99",
        "name": "Сидоров",
        "email": "s@ex.com",
        "is_active": True,
        "role": {"name": "Кладовщик"},
        "create_dt": "2026-02-01",
    }
    with patch.object(svc.ErpClient, "list_users", new=AsyncMock(return_value=[raw])):
        with patch.object(svc, "map_erp_user", return_value=None):
            enrollment = await svc.enroll_employee(db, erp_user_id="erp-99")
    emp = added[0]
    assert emp.full_name == "Сидоров"
    assert emp.hobbies is None
    assert enrollment.employee_id == 10


def test_safe_department_keeps_known_enum_and_free_text():
    assert svc._safe_department("IT") == "IT"
    assert svc._safe_department("логистический") == "логистический"
    assert svc._safe_department("Менеджер") == "Менеджер"
    assert svc._safe_department("") == "hr"


@pytest.mark.asyncio
async def test_endpoint_enroll_maps_db_error():
    db = MagicMock()
    with patch.object(ep.svc, "enroll_employee", side_effect=RuntimeError("enum departments")):
        with pytest.raises(HTTPException) as exc:
            await ep.enroll_adaptation(AdaptationEnrollIn(erp_user_id="abc"), db, {"user_id": "test-hr", "role": "hr"})
    assert exc.value.status_code == 500
    assert "адаптации" in exc.value.detail
    assert "enum departments" not in exc.value.detail


@pytest.mark.asyncio
async def test_endpoint_enroll_returns_take_links(monkeypatch):
    db = MagicMock()
    db.commit = AsyncMock()
    enrollment = SimpleNamespace(id=12, employee_id=5)
    monkeypatch.setattr(ep.svc, "enroll_employee", AsyncMock(return_value=enrollment))
    monkeypatch.setattr(ep, "write_audit", AsyncMock())
    monkeypatch.setattr(
        ep.svc,
        "take_links_for_enrollment",
        AsyncMock(return_value={
            "enrollment_id": 12,
            "employee_id": 5,
            "full_name": "Иванов Иван",
            "route": "full",
            "links": [{
                "role": "employee",
                "token": "emp-token",
                "path": "/adaptation/forms/emp-token",
                "kind_label": "1 неделя",
                "plan_date": date(2026, 9, 16),
            }],
        }),
    )
    out = await ep.enroll_adaptation(AdaptationEnrollIn(employee_id=5), db, {"user_id": "test-hr", "role": "hr"})
    assert out["id"] == 12
    assert out["employee_id"] == 5
    assert out["take_links"][0]["token"] == "emp-token"
    assert out["take_links"][0]["path"] == "/adaptation/forms/emp-token"


@pytest.mark.asyncio
async def test_public_form_returns_employee_id():
    enrollment = SimpleNamespace(
        id=3, employee_id=55, temporary_employee_id=None, closed=False, archived=False,
        employee=SimpleNamespace(full_name="Петров Пётр"),
        temporary_employee=None,
    )
    checkpoint = SimpleNamespace(
        id=8, kind=KIND_WEEK_1, plan_date=date(2026, 9, 16),
        closed=False, forced_completed_at=None, enrollment=enrollment, answers=[],
    )
    form = SimpleNamespace(
        revoked_at=None, locked=False, role=ROLE_EMPLOYEE, checkpoint=checkpoint,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = form
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    payload = await ep.get_public_adaptation_form("token-1", db)
    assert payload["employee_id"] == 55
    assert payload["enrollment_id"] == 3
    assert payload["full_name"] == "Петров Пётр"
    assert payload["checkpoint_id"] == 8
    assert payload["questions"]


def test_form_links_payload_skips_revoked():
    live = SimpleNamespace(role="employee", token="abc", sent_at=None, submitted_at=None, locked=False, revoked_at=None)
    revoked = SimpleNamespace(role="manager", token="zzz", sent_at=None, submitted_at=None, locked=False, revoked_at=datetime.now())
    cp = SimpleNamespace(participant_forms=[live, revoked])
    links = svc._form_links_payload(cp)
    assert [item["token"] for item in links] == ["abc"]
    assert links[0]["path"] == "/adaptation/forms/abc"


@pytest.mark.asyncio
async def test_ensure_participant_forms_preserves_revocation_without_duplicate():
    revoked = SimpleNamespace(role=ROLE_EMPLOYEE, revoked_at=datetime.now(), participant_user_id=None)
    hr_form = SimpleNamespace(role=ROLE_HR, revoked_at=None, participant_user_id=None)
    cp = SimpleNamespace(id=1, kind=KIND_WEEK_1, participant_forms=[revoked, hr_form])
    enrollment = SimpleNamespace(checkpoints=[cp], manager_user_id=None, employee=None)
    db = MagicMock()
    db.flush = AsyncMock()
    await svc.ensure_participant_forms(db, enrollment)
    assert revoked.revoked_at is not None
    db.add.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["archived", "closed"])
async def test_ensure_participant_forms_skips_inactive_enrollment(state):
    enrollment = SimpleNamespace(**{state: True}, checkpoints=[
        SimpleNamespace(id=1, kind=KIND_WEEK_1, participant_forms=[])
    ])
    db = MagicMock()
    db.flush = AsyncMock()
    await svc.ensure_participant_forms(db, enrollment)
    db.add.assert_not_called()
    db.flush.assert_not_called()
