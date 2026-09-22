from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.candidates.statuses import (
    STATUS_DEFINITIONS,
    allowed_transitions,
    status_catalog_item,
    validate_status_transition,
)
from app.db.v1.enums import CandidateStage, CandidateStatus
from app.endpoints.v1 import candidates as candidates_endpoint
from app.endpoints.v1.dictionaries import get_status_dict_endpoint
from app.schemas.v1.candidates import CandidateStatusSchema, ChangeVacancyData


def test_catalog_has_labels_actions_and_transitions_for_every_status():
    assert set(STATUS_DEFINITIONS) == set(CandidateStatus)
    full_documents = status_catalog_item(CandidateStatus.full_documents)
    assert full_documents["status"] == "Full documents"
    assert full_documents["label"] == "Полный пакет документов"
    assert full_documents["stage"] == "Оформление"
    assert full_documents["state"] == "Документы собраны"
    assert full_documents["next_action"] == "Подтвердить выход на работу"
    assert CandidateStatus.started_work.value in full_documents["allowed_transitions"]


@pytest.mark.asyncio
async def test_dictionary_exposes_canonical_status_catalog():
    payload = await get_status_dict_endpoint()
    item = next(row for row in payload["items"] if row["status"] == "Full documents")
    assert item["label"] == "Полный пакет документов"
    assert item["stage"] == "Оформление"
    assert item["state"] == "Документы собраны"
    assert item["allowed_transitions"]


def test_transition_policy_rejects_skipped_and_reverse_steps():
    validate_status_transition(CandidateStatus.offer_accepted, CandidateStatus.full_documents)
    validate_status_transition(CandidateStatus.rejection, CandidateStatus.applied)
    with pytest.raises(ValueError, match="Недопустимый переход"):
        validate_status_transition(CandidateStatus.applied, CandidateStatus.full_documents)
    with pytest.raises(ValueError, match="Недопустимый переход"):
        validate_status_transition(CandidateStatus.started_work, CandidateStatus.interview)


@pytest.mark.asyncio
async def test_endpoint_rejects_invalid_transition_before_commit():
    relation = SimpleNamespace(status=CandidateStatus.applied, is_active=True)
    result = MagicMock()
    result.scalar_one_or_none.return_value = relation
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await candidates_endpoint.update_candidate_status_endpoint(
            7, CandidateStatusSchema(status=CandidateStatus.full_documents), db, (None, None)
        )
    assert exc.value.status_code == 409
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_change_vacancy_reactivates_archived_candidate_and_resets_status():
    candidate = SimpleNamespace(id=7, stage=CandidateStage.archieved)
    vacancy = SimpleNamespace(id=12)
    old_relation = SimpleNamespace(candidate_id=7, vacancy_id=11, is_active=True)
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = old_relation
    db = MagicMock()
    db.get = AsyncMock(side_effect=[candidate, vacancy])
    db.execute = AsyncMock(return_value=query_result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch("app.ai_eval.service.enqueue_candidate_evaluation", new=AsyncMock()):
        result = await candidates_endpoint.change_vacancy_endpoint(
            ChangeVacancyData(candidate_id=7, vacancy_id=12), db
        )

    assert old_relation.is_active is False
    assert result.status == CandidateStatus.applied
    assert result.is_active is True
    assert candidate.stage == CandidateStage.employment
    db.commit.assert_awaited_once()
