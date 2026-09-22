from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.adaptation.onboarding import enroll_new_employee, initial_route
from app.adaptation.recurrence import recurrence_dates


@pytest.mark.asyncio
@pytest.mark.parametrize("position,expected", [("Логист", 3), ("Электромеханик", 1)])
async def test_employee_endpoint_persists_automatic_case(monkeypatch, position, expected):
    from sqlalchemy import select, func
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from unittest.mock import AsyncMock
    from app.db.v1.models import Employee, TemporaryEmployee, AdaptationEnrollment, AdaptationCheckpoint, AdaptationParticipantForm
    from app.endpoints.v1 import employees as api
    from app.schemas.v1.hr_ops import EmployeeCreate
    engine = create_async_engine("sqlite+aiosqlite://")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(api, "write_audit", AsyncMock())
    try:
        async with engine.begin() as connection:
            for model in [Employee, TemporaryEmployee, AdaptationEnrollment, AdaptationCheckpoint, AdaptationParticipantForm]:
                await connection.run_sync(model.__table__.create)
        async with factory() as db:
            employee = await api.create_employee(EmployeeCreate(
                full_name="Новый сотрудник", department="Логистика", position=position,
                date_hired=date(2026, 9, 1),
            ), db)
            employee_id = employee.id
        async with factory() as db:
            case = (await db.execute(select(AdaptationEnrollment).where(
                AdaptationEnrollment.employee_id == employee_id,
            ))).scalar_one()
            assert case.route == ("control" if expected == 1 else "full")
            count = await db.scalar(select(func.count()).select_from(AdaptationCheckpoint).where(
                AdaptationCheckpoint.enrollment_id == case.id,
            ))
            assert count == expected
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_employee_endpoint_allows_hr_to_override_automatic_route(monkeypatch):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from unittest.mock import AsyncMock
    from app.db.v1.models import Employee, TemporaryEmployee, AdaptationEnrollment, AdaptationCheckpoint, AdaptationParticipantForm
    from app.endpoints.v1 import employees as api
    from app.schemas.v1.hr_ops import EmployeeCreate
    engine = create_async_engine("sqlite+aiosqlite://")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(api, "write_audit", AsyncMock())
    try:
        async with engine.begin() as connection:
            for model in [Employee, TemporaryEmployee, AdaptationEnrollment, AdaptationCheckpoint, AdaptationParticipantForm]:
                await connection.run_sync(model.__table__.create)
        async with factory() as db:
            employee = await api.create_employee(EmployeeCreate(
                full_name="Водитель с полной адаптацией", department="Логистика",
                position="Водитель", date_hired=date(2026, 9, 1), adaptation_route="full",
            ), db)
            employee_id = employee.id
        async with factory() as db:
            case = (await db.execute(select(AdaptationEnrollment).where(
                AdaptationEnrollment.employee_id == employee_id,
            ))).scalar_one()
            assert case.route == "full"
            kinds = (await db.execute(select(AdaptationCheckpoint.kind).where(
                AdaptationCheckpoint.enrollment_id == case.id,
            ).order_by(AdaptationCheckpoint.plan_date))).scalars().all()
            assert kinds == ["week_1", "month_1", "month_2"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_series_retry_in_real_session_does_not_duplicate_checkpoints(monkeypatch):
    from sqlalchemy import select, func
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from unittest.mock import AsyncMock
    from app.db.v1.models import Employee, TemporaryEmployee, AdaptationEnrollment, AdaptationCheckpoint, AdaptationParticipantForm
    from app.endpoints.v1 import adaptation as api
    from app.schemas.v1.adaptation import AdaptationExtraIn
    engine = create_async_engine("sqlite+aiosqlite://")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(api, "write_audit", AsyncMock())
    try:
        async with engine.begin() as connection:
            for model in [Employee, TemporaryEmployee, AdaptationEnrollment, AdaptationCheckpoint, AdaptationParticipantForm]:
                await connection.run_sync(model.__table__.create)
        async with factory() as db:
            employee = Employee(full_name="Тест", department="Логистика", position="Логист", date_hired=date(2026, 9, 1))
            db.add(employee)
            await db.flush()
            case = enroll_new_employee(db, employee)
            await db.flush()
            case_id = case.id
            await db.commit()
        data = AdaptationExtraIn(enrollment_id=case_id, plan_date=date(2026, 9, 10), frequency="weekly", repeat_count=3, series_key="series-123")
        receipts = []
        for _ in range(2):
            async with factory() as db:
                receipts.append(await api.add_adaptation_checkpoint(data, db, {"role": "hr", "user_id": "hr-1"}))
        assert receipts[0] == receipts[1]
        async with factory() as db:
            count = await db.scalar(select(func.count()).select_from(AdaptationCheckpoint))
            assert count == 6  # three automatic stages and three recurring points
            roles = (await db.execute(select(AdaptationParticipantForm.role).join(
                AdaptationCheckpoint, AdaptationParticipantForm.checkpoint_id == AdaptationCheckpoint.id,
            ).where(AdaptationCheckpoint.series_key == "series-123"))).scalars().all()
            assert set(roles) == {"employee"}
    finally:
        await engine.dispose()


@pytest.mark.parametrize("position,route", [("Водитель-экспедитор", "control"), ("Электрик", "control"), ("HR менеджер", "full"), (None, "full")])
def test_initial_route(position, route):
    assert initial_route(position) == route


@pytest.mark.parametrize("position,kinds", [("Водитель", ["control_2m"]), ("Логист", ["week_1", "month_1", "month_2"])])
def test_new_employee_graph_has_expected_stages_and_roles(position, kinds):
    db = MagicMock()
    employee = SimpleNamespace(id=12, date_hired=date(2026, 9, 1), date_fired=None, position=position, erp_user_id="erp-12")
    enrollment = enroll_new_employee(db, employee)
    assert [stage.kind for stage in enrollment.checkpoints] == kinds
    assert all(stage.plan_date.weekday() < 5 for stage in enrollment.checkpoints)
    for stage in enrollment.checkpoints:
        if stage.kind != "control_2m":
            assert next(f for f in stage.participant_forms if f.role == "employee").participant_user_id == "erp-12"
    db.commit.assert_not_called()
    db.add.assert_called_once_with(enrollment)


def test_monthly_plan_preserves_month_end_anchor():
    assert recurrence_dates(date(2026, 1, 31), "monthly", 3) == [date(2026, 2, 2), date(2026, 3, 2), date(2026, 3, 31)]


def test_weekly_plan_shifts_weekends_without_drift():
    assert recurrence_dates(date(2026, 9, 5), "weekly", 2) == [date(2026, 9, 7), date(2026, 9, 14)]


def test_custom_plan_uses_explicit_day_interval_without_weekend_drift():
    assert recurrence_dates(date(2026, 9, 4), "custom", 3, interval_days=3) == [
        date(2026, 9, 4), date(2026, 9, 7), date(2026, 9, 10),
    ]


@pytest.mark.parametrize("frequency,count,interval", [("daily", 3, None), ("weekly", 0, None), ("monthly", 53, None), ("once", 2, None), ("custom", 3, None), ("custom", 3, 366)])
def test_invalid_series(frequency, count, interval):
    with pytest.raises(ValueError):
        recurrence_dates(date(2026, 9, 1), frequency, count, interval_days=interval)


def test_extra_without_hr_completes_after_employee_answer():
    from datetime import datetime, timezone
    from app.adaptation.rules import compute_status
    status = compute_status(kind="extra", plan_date=date(2026, 9, 1),
                            answers=[{"role": "employee"}], required_roles={"employee"},
                            now=datetime(2026, 9, 1, tzinfo=timezone.utc))
    assert status == "completed"


def test_extra_without_hr_has_no_hr_document():
    from app.adaptation.documents import document_types_for_kind
    assert document_types_for_kind("extra", has_hr=False) == ["employee_answers", "internal_slice"]


def test_documents_include_sources_history_and_actions_without_technical_question_ids():
    from app.adaptation.documents import document_lines
    row = {"kind": "month_2", "answers": [{"role": "employee", "payload": {"core_e1": 4}}],
           "stage_history": [{"kind": "week_1", "fact_date": "2026-09-01", "answers": []}],
           "action_records": [{"action": "Назначить наставника", "owner": "HR", "due_date": "2026-09-20", "status": "done", "effect": "Снижение нагрузки"}]}
    _, answers = document_lines(row, "employee_answers")
    assert "core_e1" not in str(answers)
    assert "комфортно" in str(answers)
    _, internal = document_lines(row, "internal_slice")
    assert "1 неделя" in str(internal)
    assert "Назначить наставника" in str(internal)
    assert "Снижение нагрузки" in str(internal)
    assert "Данных руководителя недостаточно" in str(internal)


@pytest.mark.parametrize("kind", ["internal_slice", "manager_safe", "conclusion"])
def test_management_pdf_is_forced_to_one_a4_page(kind):
    from app.adaptation.documents import render_document
    row = {"kind": "month_2", "full_name": "Иванов Иван", "position": "Логист",
           "answers": [{"role": "hr", "payload": {"manager_summary": "Работа стабильна"}}],
           "stage_history": [{"kind": "extra", "fact_date": "2026-09-01", "answers": []}] * 25,
           "action_records": [{"action": "Сопровождение " * 20, "status": "done"}] * 15}
    pdf = render_document(row, kind, "pdf", ["HR", "Руководитель", "Директор"])
    assert b"/Count 1" in pdf
