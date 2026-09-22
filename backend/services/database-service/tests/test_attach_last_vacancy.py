"""GET /candidate/{id} should expose the vacancy the candidate applied to."""
from datetime import datetime, timezone
from types import SimpleNamespace

from app.endpoints.v1.candidates import _attach_last_vacancy


def test_attach_last_vacancy_prefers_active_relation():
    candidate = SimpleNamespace(
        vacancies=[
            SimpleNamespace(
                id=1,
                is_active=False,
                status_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                updated_at=None,
                created_at=None,
                vacancy_id=1,
                vacancy=SimpleNamespace(id=1, name="Старая"),
            ),
            SimpleNamespace(
                id=2,
                is_active=True,
                status_updated_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
                updated_at=None,
                created_at=None,
                vacancy_id=2,
                vacancy=SimpleNamespace(id=2, name="Водитель категории C"),
            ),
        ]
    )
    _attach_last_vacancy(candidate)
    assert candidate.last_vacancy_id == 2
    assert candidate.last_vacancy_title == "Водитель категории C"


def test_attach_last_vacancy_uses_latest_when_none_active():
    candidate = SimpleNamespace(
        vacancies=[
            SimpleNamespace(
                id=1,
                is_active=False,
                status_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                updated_at=None,
                created_at=None,
                vacancy_id=1,
                vacancy=SimpleNamespace(id=1, name="Первая"),
            ),
            SimpleNamespace(
                id=3,
                is_active=False,
                status_updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
                updated_at=None,
                created_at=None,
                vacancy_id=3,
                vacancy=SimpleNamespace(id=3, name="Последняя"),
            ),
        ]
    )
    _attach_last_vacancy(candidate)
    assert candidate.last_vacancy_title == "Последняя"
    assert candidate.last_vacancy_id == 3


def test_attach_last_vacancy_empty_relations_keeps_existing():
    candidate = SimpleNamespace(vacancies=[], last_vacancy_id=None, last_vacancy_title=None)
    _attach_last_vacancy(candidate)
    assert candidate.last_vacancy_title is None
