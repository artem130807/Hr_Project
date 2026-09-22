from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.v1.enums import CandidateStage
from app.endpoints.v1 import candidates as mod
from app.schemas.v1.candidates import CandidateStatusSchema


@pytest.mark.asyncio
async def test_update_status_succeeds_even_if_audit_write_fails():
    db = MagicMock()
    relation = SimpleNamespace(
        candidate_id=5,
        is_active=True,
        status="откликнулся",
        status_updated_at=None,
    )
    candidate = SimpleNamespace(id=5, stage=CandidateStage.employment)

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = relation
    db.execute = AsyncMock(return_value=execute_result)
    db.get = AsyncMock(return_value=candidate)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    with patch("app.utils.audit.record_stage_change", new=AsyncMock(side_effect=RuntimeError("no table"))), patch(
        "app.utils.audit.write_audit", new=AsyncMock()
    ):
        out = await mod.update_candidate_status_endpoint(
            5,
            CandidateStatusSchema(status="собес"),
            db,
            (None, None),
        )

    assert out["status"].value == "собес"
    # First commit persists status, second audit phase fails and rolls back safely.
    assert db.commit.await_count >= 1


@pytest.mark.asyncio
async def test_update_status_reactivates_latest_relation_when_no_active():
    db = MagicMock()
    latest_relation = SimpleNamespace(
        id=17,
        candidate_id=5,
        is_active=False,
        status="отказался",
        status_updated_at=None,
        updated_at=None,
        created_at=None,
    )
    candidate = SimpleNamespace(id=5, stage=CandidateStage.archieved)

    active_lookup = MagicMock()
    active_lookup.scalar_one_or_none.return_value = None
    latest_lookup = MagicMock()
    latest_lookup.scalars.return_value.first.return_value = latest_relation
    db.execute = AsyncMock(side_effect=[active_lookup, latest_lookup])
    db.get = AsyncMock(return_value=candidate)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    with patch("app.utils.audit.record_stage_change", new=AsyncMock()), patch(
        "app.utils.audit.write_audit", new=AsyncMock()
    ):
        out = await mod.update_candidate_status_endpoint(
            5,
            CandidateStatusSchema(status="откликнулся"),
            db,
            (None, None),
        )

    assert out["status"].value == "откликнулся"
    assert latest_relation.is_active is True
    assert candidate.stage == CandidateStage.employment


@pytest.mark.asyncio
async def test_get_status_falls_back_to_latest_relation_when_no_active():
    db = MagicMock()
    active_lookup = MagicMock()
    active_lookup.scalar_one_or_none.return_value = None
    latest_relation = SimpleNamespace(status="отказался")
    latest_lookup = MagicMock()
    latest_lookup.scalars.return_value.first.return_value = latest_relation
    db.execute = AsyncMock(side_effect=[active_lookup, latest_lookup])

    out = await mod.get_candidate_status_endpoint(5, db)
    assert out["status"] == "отказался"
