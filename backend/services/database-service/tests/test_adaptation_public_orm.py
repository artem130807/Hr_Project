"""Exercise real ORM loading; forbid implicit SQL during response serialization."""
from datetime import date, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.db.v1.models import (
    AdaptationAnswer, AdaptationCheckpoint, AdaptationEnrollment,
    AdaptationParticipantForm, Employee, TemporaryEmployee,
)
from app.endpoints.v1.adaptation import get_public_adaptation_form


@pytest.mark.asyncio
@pytest.mark.parametrize("temporary", [False, True])
@pytest.mark.parametrize("state", ["active", "submitted", "archived", "closed", "checkpoint_closed", "revoked", "missing"])
async def test_public_form_serializes_without_lazy_database_io(temporary, state):
    engine = create_engine("sqlite://")
    models = [Employee, TemporaryEmployee, AdaptationEnrollment,
              AdaptationCheckpoint, AdaptationAnswer, AdaptationParticipantForm]
    for model in models:
        model.__table__.create(engine)
    with Session(engine) as session:
        fields = dict(full_name="Тестовый сотрудник", position="Логист", department="Логистика")
        employee = (TemporaryEmployee(**fields, start_date=date(2026, 9, 1)) if temporary
                    else Employee(**fields, date_hired=date(2026, 9, 1)))
        enrollment = AdaptationEnrollment(
            **{"temporary_employee" if temporary else "employee": employee},
            start_date=date(2026, 9, 1), archived=state == "archived", closed=state == "closed",
        )
        checkpoint = AdaptationCheckpoint(enrollment=enrollment, kind="week_1", plan_date=date(2026, 9, 8))
        checkpoint.closed = state == "checkpoint_closed"
        previous = AdaptationCheckpoint(enrollment=enrollment, kind="extra", plan_date=date(2026, 9, 2))
        session.add(AdaptationAnswer(checkpoint=previous, role="employee",
                                     payload={"core_e1": 5}, submitted_at=datetime(2026, 9, 2)))
        session.add(AdaptationParticipantForm(
            checkpoint=checkpoint, role="employee", token="test-token", locked=state == "submitted",
            revoked_at=datetime(2026, 9, 3) if state == "revoked" else None,
        ))
        session.commit()
    try:
        with Session(engine) as session:
            class Database:
                async def execute(self, stmt):
                    result = session.execute(stmt)
                    # selectin loaders finish as the result is consumed.
                    result = result.freeze()
                    event.listen(session, "do_orm_execute", forbid_sql)
                    return result()

            def forbid_sql(state):
                raise AssertionError("Implicit SQL outside awaited execute: async would raise MissingGreenlet")

            token = "unknown-token" if state == "missing" else "test-token"
            if state not in {"active", "submitted"}:
                with pytest.raises(HTTPException) as exc:
                    await get_public_adaptation_form(token, Database())
                assert exc.value.status_code == 404
                return
            payload = await get_public_adaptation_form(token, Database())
            assert payload["full_name"] == "Тестовый сотрудник"
            assert payload["role"] == "employee"
            assert payload["questions"]
            assert payload["locked"] == (state == "submitted")
            assert payload["core_history"]["core_e1"] == 5
    finally:
        engine.dispose()
