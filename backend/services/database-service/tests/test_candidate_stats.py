"""Unit tests for candidate funnel analytics."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.v1.enums import CandidateStage, CandidateStatus
from app.utils import stats as stats_mod


def _rel(status, *, active=True, vacancy_name="Логист", vacancy_id=1, updated_at=None, rid=1):
    return SimpleNamespace(
        id=rid,
        is_active=active,
        vacancy_id=vacancy_id,
        status=status,
        updated_at=updated_at or datetime(2026, 8, 1, tzinfo=timezone.utc),
        created_at=updated_at or datetime(2026, 8, 1, tzinfo=timezone.utc),
        vacancy=SimpleNamespace(name=vacancy_name),
    )


def _cand(stage, relations, *, name="Иванов", cid=1, updated_at=None):
    return SimpleNamespace(
        id=cid,
        full_name=name,
        stage=stage,
        vacancies=relations,
        updated_at=updated_at or datetime(2026, 8, 10, tzinfo=timezone.utc),
        created_at=updated_at or datetime(2026, 8, 10, tzinfo=timezone.utc),
    )


def test_resolve_employment_uses_active_relation():
    c = _cand(
        CandidateStage.employment,
        [
            _rel(CandidateStatus.applied, active=False, rid=1),
            _rel(CandidateStatus.test_sent, active=True, rid=2),
        ],
    )
    assert stats_mod.resolve_candidate_funnel_status(c) == "тест: отправлен"


def test_resolve_hired_and_resigned():
    hired = _cand(
        CandidateStage.hired,
        [_rel(CandidateStatus.started_work, active=False)],
    )
    assert stats_mod.resolve_candidate_funnel_status(hired) == "ВНР"

    resigned = _cand(
        CandidateStage.hired,
        [_rel(CandidateStatus.resigned, active=False)],
    )
    assert stats_mod.resolve_candidate_funnel_status(resigned) == "уволился"


def test_resolve_archive_keeps_precise_status():
    c = _cand(
        CandidateStage.archieved,
        [_rel(CandidateStatus.refused, active=False)],
    )
    assert stats_mod.resolve_candidate_funnel_status(c) == "отказался"


def test_empty_funnel_has_all_new_statuses():
    counts = stats_mod.empty_funnel_counts()
    assert list(counts.keys()) == [
        "холодный контакт",
        "не подходит",
        "отказался",
        "откликнулся",
        "тест: отправлен",
        "тест: не прошли",
        "тест: пройден",
        "собес",
        "подумать",
        "оффер принят",
        "Full documents",
        "отказ",
        "ВНР",
        "уволился",
    ]
    assert all(v == 0 for v in counts.values())


@pytest.mark.asyncio
async def test_get_candidate_status_summary_counts_each_once():
    candidates = [
        _cand(CandidateStage.employment, [_rel(CandidateStatus.applied, active=True)], cid=1),
        _cand(CandidateStage.employment, [_rel(CandidateStatus.interview, active=True)], cid=2),
        _cand(
            CandidateStage.archieved,
            [_rel(CandidateStatus.rejection, active=False)],
            cid=3,
        ),
        _cand(CandidateStage.hired, [_rel(CandidateStatus.started_work, active=False)], cid=4),
    ]
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = candidates
    db.execute = AsyncMock(return_value=result)

    summary = await stats_mod.get_candidate_status_summary(db)
    assert summary["откликнулся"] == 1
    assert summary["собес"] == 1
    assert summary["отказ"] == 1
    assert summary["ВНР"] == 1
    assert summary["холодный контакт"] == 0
    assert sum(summary.values()) == 4


@pytest.mark.asyncio
async def test_get_funnel_data_filters_by_date():
    in_range = _cand(
        CandidateStage.employment,
        [_rel(CandidateStatus.applied, active=True)],
        cid=1,
        updated_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
    )
    out_range = _cand(
        CandidateStage.employment,
        [
            _rel(
                CandidateStatus.interview,
                active=True,
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ],
        cid=2,
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [in_range, out_range]
    db.execute = AsyncMock(return_value=result)

    funnel, detail = await stats_mod.get_funnel_data(
        db,
        datetime(2026, 8, 1, tzinfo=timezone.utc),
        datetime(2026, 8, 31, 23, 59, 59, tzinfo=timezone.utc),
    )
    assert funnel["откликнулся"] == 1
    assert funnel["собес"] == 0
    assert detail["откликнулся"][0][0] == "Иванов"


def test_resolve_status_for_specific_vacancy():
    c = _cand(
        CandidateStage.employment,
        [
            _rel(CandidateStatus.applied, active=True, vacancy_id=10, rid=1),
            _rel(CandidateStatus.interview, active=True, vacancy_id=11, rid=2),
        ],
    )
    assert stats_mod.resolve_candidate_funnel_status_for_vacancy(c, 10) == "откликнулся"
    assert stats_mod.resolve_candidate_funnel_status_for_vacancy(c, 11) == "собес"
    assert stats_mod.resolve_candidate_funnel_status_for_vacancy(c, 999) is None


def test_vacancy_filter_sql_does_not_distinct_json_columns():
    """Postgres cannot DISTINCT json columns (hobbies, languages, hard_skills…)."""
    from sqlalchemy.dialects import postgresql

    sql = str(
        stats_mod._candidates_with_relations_stmt(6).compile(dialect=postgresql.dialect())
    ).upper()
    assert "DISTINCT" not in sql
    assert "CANDIDATE_VACANCY_RELATIONS" in sql
    assert "VACANCY_ID" in sql


def test_relation_sort_accepts_mixed_aware_and_naive_datetimes():
    naive = _rel(CandidateStatus.applied, rid=1, updated_at=datetime(2026, 8, 1))
    aware = _rel(
        CandidateStatus.interview,
        rid=2,
        updated_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
    )
    ordered = sorted([naive, aware], key=stats_mod._relation_sort_key)
    assert [rel.id for rel in ordered] == [1, 2]


@pytest.mark.asyncio
async def test_get_funnel_data_naive_bounds_with_aware_candidate_ts():
    cand = _cand(
        CandidateStage.employment,
        [_rel(CandidateStatus.applied, active=True, vacancy_name="Логист")],
        cid=1,
        updated_at=datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc),
    )
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [cand]
    db.execute = AsyncMock(return_value=result)

    funnel, _ = await stats_mod.get_funnel_data(
        db,
        datetime(2026, 8, 1),
        datetime(2026, 8, 31, 23, 59, 59),
    )
    assert funnel["откликнулся"] == 1


@pytest.mark.asyncio
async def test_get_funnel_data_for_vacancy_uses_that_vacancy_name():
    cand = _cand(
        CandidateStage.employment,
        [
            _rel(CandidateStatus.applied, vacancy_id=10, vacancy_name="Логист", rid=1),
            _rel(CandidateStatus.interview, vacancy_id=11, vacancy_name="Водитель", rid=2),
        ],
        cid=1,
    )
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [cand]
    db.execute = AsyncMock(return_value=result)

    funnel, detail = await stats_mod.get_funnel_data(db, None, None, vacancy_id=10)
    assert funnel["откликнулся"] == 1
    assert detail["откликнулся"][0][1] == "Логист"


@pytest.mark.asyncio
async def test_get_candidate_status_summary_for_vacancy():
    candidates = [
        _cand(
            CandidateStage.employment,
            [
                _rel(CandidateStatus.applied, active=True, vacancy_id=10, rid=1),
                _rel(CandidateStatus.interview, active=True, vacancy_id=11, rid=2),
            ],
            cid=1,
        ),
        _cand(
            CandidateStage.archieved,
            [_rel(CandidateStatus.rejection, active=False, vacancy_id=10, rid=3)],
            cid=2,
        ),
    ]
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = candidates
    db.execute = AsyncMock(return_value=result)

    summary = await stats_mod.get_candidate_status_summary(db, vacancy_id=10)
    assert summary["откликнулся"] == 1
    assert summary["отказ"] == 1
    assert summary["собес"] == 0


def test_build_funnel_xlsx_writes_ordered_rows(tmp_path=None):
    funnel = stats_mod.empty_funnel_counts()
    funnel["откликнулся"] = 2
    funnel["ВНР"] = 1
    path = stats_mod.build_funnel_xlsx(funnel, {"откликнулся": [("A", "V")]}, None, None)
    assert path.endswith(".xlsx")
