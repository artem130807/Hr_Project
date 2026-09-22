"""Regression coverage using actual async SQLAlchemy sessions, not DB mocks."""
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.db.v1.models import (
    Employee, TemporaryEmployee, AdaptationEnrollment, AdaptationCheckpoint,
    AdaptationAnswer, AdaptationAnswerVersion, AdaptationParticipantForm,
    AdaptationModuleSettings,
)
from app.endpoints.v1.adaptation import (
    get_public_adaptation_form, submit_public_adaptation_form,
)
from app.adaptation.service import reports_for_period


@pytest.mark.asyncio
async def test_period_report_has_no_page_limit_and_keeps_terminated_history():
    engine = create_async_engine("sqlite+aiosqlite://")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    models = [Employee, TemporaryEmployee, AdaptationEnrollment, AdaptationCheckpoint,
              AdaptationAnswer, AdaptationParticipantForm]
    try:
        async with engine.begin() as connection:
            for model in models:
                await connection.run_sync(model.__table__.create)
        async with factory() as db:
            employee = Employee(full_name="Активный", department="Логистика", position="Логист", date_hired=date(2026, 1, 1))
            enrollment = AdaptationEnrollment(employee=employee, start_date=date(2026, 1, 1))
            for _ in range(105):
                db.add(AdaptationCheckpoint(enrollment=enrollment, kind="extra", plan_date=date(2026, 9, 10)))
            db.add(AdaptationCheckpoint(enrollment=enrollment, kind="extra", plan_date=date(2026, 8, 10)))
            former = Employee(full_name="Уволенный", department="Логистика", position="Логист", date_hired=date(2026, 1, 1), date_fired=date(2026, 9, 15))
            old = AdaptationEnrollment(employee=former, start_date=date(2026, 1, 1), archived=True)
            db.add(AdaptationCheckpoint(enrollment=old, kind="week_1", plan_date=date(2026, 9, 5), fact_date=date(2026, 9, 5)))
            await db.commit()
        async with factory() as db:
            report = await reports_for_period(db, year=2026, month=9)
            assert len(report["internal"]) == 105
            assert len(report["terminated"]) == 1
            assert report["terminated"][0]["employee"] == "Уволенный"
            assert all(item["plan_date"].month == 9 for item in report["internal"])
            assert "probation" not in report
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("temporary", [True, False])
@pytest.mark.parametrize("kind", ["week_1", "month_1", "month_2"])
async def test_public_hr_form_load_and_submit_in_fresh_async_sessions(temporary, kind):
    engine = create_async_engine("sqlite+aiosqlite://")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    models = [Employee, TemporaryEmployee, AdaptationEnrollment, AdaptationCheckpoint,
              AdaptationAnswer, AdaptationAnswerVersion, AdaptationParticipantForm,
              AdaptationModuleSettings]
    try:
        async with engine.begin() as connection:
            for model in models:
                await connection.run_sync(model.__table__.create)
        async with factory() as db:
            fields = dict(full_name="Тест", position="Логист", department="Логистика")
            employee = (TemporaryEmployee(**fields, start_date=date(2026, 9, 1)) if temporary
                        else Employee(**fields, date_hired=date(2026, 9, 1)))
            enrollment = AdaptationEnrollment(
                **{"temporary_employee" if temporary else "employee": employee},
                start_date=date(2026, 9, 1),
            )
            checkpoint = AdaptationCheckpoint(enrollment=enrollment, kind=kind, plan_date=date(2026, 9, 8))
            db.add(AdaptationParticipantForm(checkpoint=checkpoint, role="hr", token="async-test-token"))
            await db.commit()
        async with factory() as db:
            await get_public_adaptation_form("async-test-token", db)
        async with factory() as db:
            result = await submit_public_adaptation_form(
                "async-test-token", {"payload": {"hr_comment": "Все хорошо"}}, db,
            )
            assert result["submitted"] is True
        async with factory() as db:
            answer = (await db.execute(select(AdaptationAnswer))).scalar_one()
            assert answer.payload["hr_comment"] == "Все хорошо"
            assert (await db.execute(select(AdaptationAnswerVersion))).scalar_one()
            assert (await db.execute(select(AdaptationParticipantForm))).scalar_one().submitted_at
    finally:
        await engine.dispose()
