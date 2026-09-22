"""Канальные события заявки на подбор → message.entity_changed (как ERP downtime/approval)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.db.v1.enums import Departments, HiringRequestStatus
from app.domain.hiring_request_events import HiringRequestCreatedEvent
from app.messaging.channel_events import (
    hiring_request_created_text,
    publish_hiring_request_created,
    safe_channel_publish,
)
from app.schemas.v1.hiring_request import EmployeeRequestCreate


def _req(**kwargs):
    defaults = dict(
        id=42,
        position="Логист",
        department=Departments.logistics,
        headcount=2,
        initiator_name="Петров",
        manager_name="Иванов",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_hiring_request_created_payload():
    event = HiringRequestCreatedEvent(
        hiring_request_id=42,
        text="Создана заявка на подбор З-42",
        target_role_ids=(2, 4, 7),
        actor_user_id="u-1",
    )
    data = event.to_dict()
    assert data["event_type"] == "message.hiring_request.created"
    assert data["hiring_request_id"] == 42
    assert data["text"] == "Создана заявка на подбор З-42"
    assert data["target_role_ids"] == [2, 4, 7]
    assert data["actor_user_id"] == "u-1"
    UUID(data["event_id"])
    assert isinstance(data["occurred_at"], str)


def test_hiring_request_created_text_includes_position_and_code():
    text = hiring_request_created_text(_req(), actor_name="Иван HR")
    lines = text.splitlines()
    assert lines[0] == "Создана заявка на подбор З-42"
    assert "Должность: Логист" in lines
    assert "Отдел: логистический" in lines
    assert "Нужно: 2 чел." in lines
    assert "Инициатор: Петров" in lines
    assert "Создал: Иван HR" in lines


def test_hiring_request_created_text_skips_empty_optional_fields():
    text = hiring_request_created_text(
        _req(department=None, headcount=None, initiator_name=None, manager_name=None)
    )
    assert "Отдел:" not in text
    assert "Нужно:" not in text
    assert "Инициатор:" not in text


@pytest.mark.asyncio
async def test_publish_hiring_request_created_sends_event():
    producer = MagicMock()
    producer.publish = AsyncMock()
    with patch(
        "app.messaging.channel_events.get_message_event_producer",
        return_value=producer,
    ), patch(
        "app.messaging.channel_events.ErpClient.list_roles",
        new_callable=AsyncMock,
        return_value=[
            {"id": 2, "name": "Админ"},
            {"id": 4, "name": "Руководитель"},
            {"id": 7, "name": "HR"},
        ],
    ):
        await publish_hiring_request_created(
            _req(),
            actor_user_id="u-1",
            actor_name="Иван HR",
        )
    event = producer.publish.await_args.args[0]
    assert isinstance(event, HiringRequestCreatedEvent)
    assert event.hiring_request_id == 42
    assert event.actor_user_id == "u-1"
    assert event.target_role_ids == (2, 4, 7)
    assert "З-42" in event.text
    assert "Логист" in event.text


@pytest.mark.asyncio
async def test_publish_hiring_request_created_skips_without_id():
    producer = MagicMock()
    producer.publish = AsyncMock()
    with patch(
        "app.messaging.channel_events.get_message_event_producer",
        return_value=producer,
    ):
        await publish_hiring_request_created(_req(id=None))
    producer.publish.assert_not_called()


@pytest.mark.asyncio
async def test_publish_hiring_request_created_skips_when_roles_unavailable():
    producer = MagicMock()
    producer.publish = AsyncMock()
    with patch(
        "app.messaging.channel_events.get_message_event_producer",
        return_value=producer,
    ), patch(
        "app.messaging.channel_events.ErpClient.list_roles",
        new_callable=AsyncMock,
        return_value=[],
    ):
        await publish_hiring_request_created(_req())
    producer.publish.assert_not_called()


@pytest.mark.asyncio
async def test_safe_channel_publish_swallows():
    async def boom():
        raise RuntimeError("broker down")

    await safe_channel_publish(boom(), context="hiring_request.create")


@pytest.mark.asyncio
async def test_post_hiring_request_publishes_after_commit():
    from app.endpoints.v1 import hiring_request as mod

    events = []
    row = SimpleNamespace(id=42)
    db = MagicMock()
    db.commit = AsyncMock(side_effect=lambda: events.append("commit"))
    db.refresh = AsyncMock()

    data = EmployeeRequestCreate(
        position="Логист",
        department=Departments.logistics,
        headcount=2,
        manager_name="Иванов",
        manager_position="CTO",
        phone="+7 999",
        purpose="Организация перевозок",
        mandatory_requirements=["Excel"],
        schedule="5/2",
        work_format="office",
        status=HiringRequestStatus.created,
    )
    create = AsyncMock(return_value=row)
    publish = AsyncMock(side_effect=lambda *args, **kwargs: events.append("publish"))
    read = MagicMock()

    with (
        patch.object(mod, "create_request_record", create),
        patch.object(mod, "publish_request_created", publish),
        patch.object(mod, "_to_read", return_value=read),
    ):
        result = await mod.post_hiring_request_endpoint(
            data, db, actor=("u-1", "Иван HR")
        )

    assert result is read
    db.commit.assert_awaited()
    publish.assert_awaited_once()
    assert publish.await_args.args[0].id == 42
    assert publish.await_args.kwargs == {"actor_id": "u-1", "actor_name": "Иван HR"}
    assert db.commit.await_count == 1
    assert events == ["commit", "publish"]


@pytest.mark.asyncio
async def test_post_hiring_request_publishes_hr_notify_event():
    from app.endpoints.v1 import hiring_request as mod

    row = SimpleNamespace(id=42)
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    data = EmployeeRequestCreate(
        position="Логист",
        department=Departments.logistics,
        headcount=2,
        manager_name="Иванов",
        manager_position="CTO",
        phone="+7 999",
        purpose="Организация перевозок",
        mandatory_requirements=["Excel"],
        schedule="5/2",
        work_format="office",
        status=HiringRequestStatus.created,
    )
    publish = AsyncMock()
    read = MagicMock()

    with (
        patch.object(mod, "create_request_record", AsyncMock(return_value=row)),
        patch.object(mod, "publish_request_created", publish),
        patch.object(mod, "_to_read", return_value=read),
    ):
        await mod.post_hiring_request_endpoint(data, db, actor=("u-1", "Иван HR"))

    publish.assert_awaited_once_with(row, actor_id="u-1", actor_name="Иван HR")
