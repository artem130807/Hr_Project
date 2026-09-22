"""Candidates list filters: search, multi vacancy_id, vacancy options."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.v1.enums import CandidateStage, CandidateStatus
from app.db.v1.models import Candidate, CandidateVacancyRelation
from app.endpoints.v1 import candidates as cand_mod
from app.endpoints.v1 import vacancies as vac_mod
from app.schemas.v1.vacancies import VacancyOption


def test_candidate_status_column_uses_pg_values_not_names():
    """Status → Russian values; stage → English names (prod PG enums)."""
    status_type = CandidateVacancyRelation.__table__.c.status.type
    stage_type = Candidate.__table__.c.stage.type

    assert status_type.process_bind_param(CandidateStatus.applied, None) == "откликнулся"
    assert status_type.process_bind_param(CandidateStatus.not_suitable, None) == "не подходит"
    assert status_type.process_bind_param("applied", None) == "откликнулся"
    assert "откликнулся" in status_type.enums
    assert "applied" not in status_type.enums

    assert stage_type.process_bind_param(CandidateStage.employment, None) == "employment"
    assert stage_type.process_bind_param(CandidateStage.archieved, None) == "archieved"
    assert stage_type.process_bind_param("в процессе найма", None) == "employment"
    assert "employment" in stage_type.enums
    assert "в процессе найма" not in stage_type.enums


def test_hiring_request_status_column_uses_pg_values():
    from app.db.v1.enums import HiringRequestStatus
    from app.db.v1.models import EmployeeRequest

    col = EmployeeRequest.__table__.c.status.type
    assert col.process_bind_param(HiringRequestStatus.closed, None) == "закрыта"
    assert col.process_bind_param(HiringRequestStatus.completed, None) == "завершена"
    assert col.process_bind_param("closed", None) == "закрыта"
    assert "закрыта" in col.enums
    assert "closed" not in col.enums


@pytest.mark.asyncio
async def test_get_vacancy_options_hh_only():
    row = MagicMock()
    row.id = 5
    row.name = "Логист"
    row.hh_vacancy_id = "123"
    row.hh_vacancy_url = "https://hh.ru/vacancy/123"

    db = MagicMock()
    result = MagicMock()
    result.all.return_value = [row]
    db.execute = AsyncMock(return_value=result)

    out = await vac_mod.get_vacancy_options(hh_only=True, db=db)
    assert out == [
        VacancyOption(
            id=5,
            name="Логист",
            hh_vacancy_id="123",
            hh_vacancy_url="https://hh.ru/vacancy/123",
        )
    ]
    db.execute.assert_awaited()


@pytest.mark.asyncio
async def test_candidates_search_accepts_phone_needle():
    db = MagicMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    page_result = MagicMock()
    page_result.all.return_value = []
    db.execute = AsyncMock(side_effect=[count_result, page_result])

    out = await cand_mod.get_all_candidates(
        status=None,
        search="7922",
        vacancy_id=None,
        role_id=None,
        is_perfect_candidate=None,
        category="candidate",
        page=1,
        per_page=50,
        db=db,
    )
    assert out.total == 0
    assert out.items == []
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_candidates_accepts_multiple_vacancy_ids():
    db = MagicMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    page_result = MagicMock()
    page_result.all.return_value = []
    db.execute = AsyncMock(side_effect=[count_result, page_result])

    out = await cand_mod.get_all_candidates(
        status=None,
        search=None,
        vacancy_id=[1, 2, 3],
        role_id=None,
        is_perfect_candidate=None,
        category=None,
        page=1,
        per_page=50,
        db=db,
    )
    assert out.total == 0
    assert db.execute.await_count == 2
