from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.v1.enums import CandidateStatus, TestType as CandidateTestType
from app.endpoints.v1 import messages as mod
from app.schemas.v1.messages import SendProfessionalTestData


def _patch_send_side_effects(**extra):
    patches = {
        "sync_candidate_hh_action": AsyncMock(return_value={"status": "ok"}),
        "set_candidate_vacancy_status": AsyncMock(return_value=True),
        **extra,
    }
    return patch.multiple(mod, **patches)


@pytest.mark.asyncio
async def test_send_professional_test_creates_result_and_syncs_hh_message():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()

    candidate = SimpleNamespace(id=5, full_name="Иван Иванов")
    test = SimpleNamespace(id=11, name="Проф. тест логиста", test_type=CandidateTestType.questions)
    existing_result = None

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = existing_result
    db.execute = AsyncMock(return_value=execute_result)
    db.get = AsyncMock(side_effect=[candidate, test])

    # emulate PK assignment on flush
    def _assign_id():
        added = db.add.call_args.args[0]
        added.id = 77

    db.flush.side_effect = _assign_id

    req = MagicMock()
    req.headers = {}
    req.base_url = "https://hr-web.alt-cargo.tw1.ru/"

    hh_sync = AsyncMock(return_value={"status": "ok"})
    set_status = AsyncMock(return_value=True)
    with patch.object(mod, "sync_candidate_hh_action", hh_sync), patch.object(
        mod, "set_candidate_vacancy_status", set_status
    ):
        out = await mod.send_professional_test_endpoint(
            SendProfessionalTestData(candidate_id=5, test_id=11),
            req,
            db,
            None,
        )

    assert out["status"] == "ok"
    assert out["result_id"] == 77
    assert out["created_result"] is True
    assert "/take/test/11?" in out["test_url"]
    assert "candidate_id=5" in out["test_url"]
    assert "result_id=77" in out["test_url"]
    hh_sync.assert_awaited_once()
    args = hh_sync.await_args.args
    assert args[1] == 5
    assert args[2] == "message"
    assert "take/test/11" in hh_sync.await_args.kwargs["message"]
    set_status.assert_awaited_once()
    assert set_status.await_args.args[1] == 5
    assert set_status.await_args.args[2] == CandidateStatus.test_sent


@pytest.mark.asyncio
async def test_send_professional_test_reuses_existing_result():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()

    candidate = SimpleNamespace(id=5, full_name="Иван Иванов")
    test = SimpleNamespace(id=11, name="Проф. тест логиста", test_type=CandidateTestType.questions)
    existing_result = SimpleNamespace(id=21, candidate_id=5, test_id=11)

    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = existing_result
    db.execute = AsyncMock(return_value=execute_result)
    db.get = AsyncMock(side_effect=[candidate, test])

    req = MagicMock()
    req.headers = {}
    req.base_url = "https://hr-web.alt-cargo.tw1.ru/"

    with _patch_send_side_effects():
        out = await mod.send_professional_test_endpoint(
            SendProfessionalTestData(candidate_id=5, test_id=11),
            req,
            db,
            None,
        )

    assert out["result_id"] == 21
    assert out["created_result"] is False
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_send_professional_test_returns_warning_when_hh_skips():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()

    candidate = SimpleNamespace(id=5, full_name="Иван Иванов")
    test = SimpleNamespace(id=11, name="Проф. тест логиста", test_type=CandidateTestType.questions)
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = SimpleNamespace(id=21, candidate_id=5, test_id=11)
    db.execute = AsyncMock(return_value=execute_result)
    db.get = AsyncMock(side_effect=[candidate, test])

    req = MagicMock()
    req.headers = {}
    req.base_url = "https://hr-web.alt-cargo.tw1.ru/"

    with _patch_send_side_effects(
        sync_candidate_hh_action=AsyncMock(
            return_value={"status": "skipped", "reason": "negotiation_not_found"}
        )
    ):
        out = await mod.send_professional_test_endpoint(
            SendProfessionalTestData(candidate_id=5, test_id=11),
            req,
            db,
            None,
        )

    assert out["status"] == "ok"
    assert out["delivery"] == "skipped"
    assert "warning" in out
    assert out["warning"]


@pytest.mark.asyncio
async def test_send_professional_test_returns_unavailable_reason():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()

    candidate = SimpleNamespace(id=5, full_name="Иван Иванов")
    test = SimpleNamespace(id=11, name="Проф. тест логиста", test_type=CandidateTestType.questions)
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = SimpleNamespace(id=21, candidate_id=5, test_id=11)
    db.execute = AsyncMock(return_value=execute_result)
    db.get = AsyncMock(side_effect=[candidate, test])

    req = MagicMock()
    req.headers = {}
    req.base_url = "https://hr-web.alt-cargo.tw1.ru/"

    with _patch_send_side_effects(
        sync_candidate_hh_action=AsyncMock(
            return_value={"status": "unavailable", "reason": "hh_service_not_configured"}
        )
    ):
        out = await mod.send_professional_test_endpoint(
            SendProfessionalTestData(candidate_id=5, test_id=11),
            req,
            db,
            None,
        )

    assert out["status"] == "ok"
    assert out["delivery"] == "unavailable"
    assert "hh_service_not_configured" in out["warning"]


@pytest.mark.asyncio
async def test_send_professional_test_rejects_non_professional_test():
    db = MagicMock()
    db.get = AsyncMock(
        side_effect=[
            SimpleNamespace(id=5, full_name="Иван Иванов"),
            SimpleNamespace(id=12, name="Псих тест", test_type=CandidateTestType.url),
        ]
    )

    req = MagicMock()
    req.headers = {}
    req.base_url = "https://hr-web.alt-cargo.tw1.ru/"

    with pytest.raises(HTTPException) as exc:
        await mod.send_professional_test_endpoint(
            SendProfessionalTestData(candidate_id=5, test_id=12),
            req,
            db,
            None,
        )
    assert exc.value.status_code == 400
    assert isinstance(exc.value.detail, str)
    assert exc.value.detail
