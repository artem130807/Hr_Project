from datetime import date, datetime, timezone

from app.utils.tz_helpers import deadline_state, days_in_status, vacancy_public_code


def test_deadline_state_rules():
    today = date(2026, 8, 13)
    assert deadline_state(date(2026, 8, 10), today) == "overdue"
    assert deadline_state(date(2026, 8, 15), today) == "warning"
    assert deadline_state(date(2026, 9, 1), today) == "ok"
    assert deadline_state(None, today) is None


def test_days_in_status():
    now = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
    started = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    assert days_in_status(started, None, now) == 3
    assert days_in_status(None, started, now) == 3


def test_vacancy_public_code():
    assert vacancy_public_code(12) == "В-12"


def test_read_vacancy_enriches_public_code_and_deadline():
    from datetime import datetime, timezone
    from app.db.v1.enums import Departments
    from app.schemas.v1.vacancies import ReadVacancy

    vac = ReadVacancy(
        id=12,
        name="Логист",
        vacancy_type_id="open",
        synonyms=["a"],
        description=("x" * 200),
        department=Departments.logistics,
        created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        planned_close_date=date(2026, 8, 10),
        is_template=False,
    )
    assert vac.public_code == "В-12"
    assert vac.deadline_state == "overdue"
