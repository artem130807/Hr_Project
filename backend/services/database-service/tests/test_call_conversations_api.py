from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.db.v1.enums import CallConversationStatus
from app.endpoints.v1.call_conversations import get_call_conversation, list_call_conversations
from app.schemas.v1.call_conversations import CallConversationRead, CALL_STATUS_LABELS


def _row(**kwargs):
    defaults = dict(
        id=1,
        filename="recording_2025-08-25_14-30-15.mp3",
        description=None,
        payload={
            "transcript": [
                {"channel": "B", "startTime": 0.3, "endTime": 1.08, "word": "информируем"},
                {"channel": "B", "startTime": 1.08, "endTime": 1.26, "word": "что"},
            ],
            "ats": {"status": "ANSWERED"},
        },
        call_start_time=datetime(2025, 8, 25, 14, 30, 15, tzinfo=timezone.utc),
        call_end_time=datetime(2025, 8, 25, 14, 35, 42, tzinfo=timezone.utc),
        caller_number="+79020013728",
        operator_number="+79007654321",
        duration=327,
        status=CallConversationStatus.pending.value,
        ats_status="ANSWERED",
        direction="incoming",
        caller_name=None,
        operator_name=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_read_schema_builds_turns_and_labels():
    dto = CallConversationRead.from_row(_row())
    assert dto.status == "pending"
    assert dto.status_label == "Определяется"
    assert CALL_STATUS_LABELS["dropped"] == "Сброс"
    assert dto.turns[0]["speaker"] == "hr"
    assert "информируем" in dto.turns[0]["text"]
    dumped = dto.model_dump(by_alias=True)
    assert dumped["callStartTime"]
    assert dumped["callerNumber"] == "+79020013728"


@pytest.mark.asyncio
async def test_list_endpoint():
    repo = SimpleNamespace(list_recent=AsyncMock(return_value=[_row()]))
    items = await list_call_conversations(limit=10, offset=0, status_filter=None, repo=repo)
    assert len(items) == 1
    assert items[0].filename.endswith(".mp3")


@pytest.mark.asyncio
async def test_get_endpoint_404():
    repo = SimpleNamespace(get=AsyncMock(return_value=None))
    with pytest.raises(Exception) as exc:
        await get_call_conversation(9, repo)
    assert getattr(exc.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_get_endpoint_ok():
    repo = SimpleNamespace(get=AsyncMock(return_value=_row(id=5, status="rejected")))
    item = await get_call_conversation(5, repo)
    assert item.id == 5
    assert item.status == "rejected"
    assert item.status_label == "Отказ"
    repo.get.assert_awaited_once_with(5)


@pytest.mark.asyncio
async def test_get_endpoint_hides_unrelated_number():
    repo = SimpleNamespace(
        get=AsyncMock(
            return_value=_row(id=8, caller_number="+79992140831", operator_number="+79000000000")
        )
    )
    with pytest.raises(Exception) as exc:
        await get_call_conversation(8, repo)
    assert getattr(exc.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_list_passes_status_filter():
    repo = SimpleNamespace(list_recent=AsyncMock(return_value=[]))
    items = await list_call_conversations(
        limit=20, offset=5, status_filter="pending", repo=repo
    )
    assert items == []
    repo.list_recent.assert_awaited_once_with(limit=20, offset=5, status="pending")


def test_routes_registered():
    from app.endpoints.v1.call_conversations import router

    paths = {getattr(r, "path", None) for r in router.routes}
    assert "/call-conversations" in paths
    assert "/call-conversations/{conversation_id}" in paths
