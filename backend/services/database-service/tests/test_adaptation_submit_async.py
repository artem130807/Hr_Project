"""Public submission with real ORM persistence and an implicit-SQL guard.

The async facade permits SQL only in explicit awaits; lazy loads fail as they
would in AsyncSession, without requiring a platform-specific greenlet binary.
"""
from datetime import date
import pytest
from sqlalchemy import select, func, create_engine, event
from sqlalchemy.orm import Session
from app.db.v1.models import (
    Employee, TemporaryEmployee, AdaptationEnrollment, AdaptationCheckpoint,
    AdaptationAnswer, AdaptationAnswerVersion, AdaptationParticipantForm,
    AdaptationModuleSettings,
)
from app.endpoints.v1.adaptation import submit_public_adaptation_form


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["week_1", "month_1", "month_2"])
@pytest.mark.parametrize("temporary", [True, False])
async def test_public_hr_comment_is_committed_with_version(kind, temporary):
    engine = create_engine("sqlite://")
    tables = [Employee, TemporaryEmployee, AdaptationEnrollment, AdaptationCheckpoint,
              AdaptationAnswer, AdaptationAnswerVersion, AdaptationParticipantForm, AdaptationModuleSettings]
    try:
        for model in tables:
            model.__table__.create(engine)
        with Session(engine, expire_on_commit=False) as db:
            fields = dict(full_name="Тест", position="Логист", department="Логистика")
            employee = (TemporaryEmployee(**fields, start_date=date(2026, 9, 1)) if temporary
                        else Employee(**fields, date_hired=date(2026, 9, 1)))
            enrollment = AdaptationEnrollment(**{"temporary_employee" if temporary else "employee": employee}, start_date=date(2026, 9, 1))
            cp = AdaptationCheckpoint(enrollment=enrollment, kind=kind, plan_date=date(2026, 9, 8))
            db.add(AdaptationParticipantForm(checkpoint=cp, role="hr", token="test-hr-token"))
            db.commit()
        with Session(engine, expire_on_commit=False) as session:
            class Database:
                permitted = False
                async def execute(self, stmt):
                    self.permitted = True
                    try:
                        return session.execute(stmt).freeze()()
                    finally:
                        self.permitted = False
                def add(self, row): session.add(row)
                async def flush(self): session.flush()
                async def commit(self): session.commit()
            db = Database()
            def forbid_implicit_sql(state):
                if not db.permitted:
                    raise AssertionError("Implicit SQL outside awaited execute (MissingGreenlet in production)")
            event.listen(session, "do_orm_execute", forbid_implicit_sql)
            result = await submit_public_adaptation_form("test-hr-token", {"payload": {"hr_comment": "Включается в рабочие процессы"}}, db)
            assert result["submitted"] is True
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(AdaptationAnswer)) == 1
            assert db.scalar(select(func.count()).select_from(AdaptationAnswerVersion)) == 1
            answer = db.scalar(select(AdaptationAnswer))
            assert answer.payload["hr_comment"] == "Включается в рабочие процессы"
            assert db.scalar(select(AdaptationParticipantForm)).submitted_at is not None
    finally:
        engine.dispose()
