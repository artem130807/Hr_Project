"""Доменное событие hr.hiring_request.created (Telegram-поток как hr.event.created)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.db.v1.enums import Departments
from app.domain.hr_hiring_request_events import HrHiringRequestCreatedEvent
from app.events.publisher import publish_hr_hiring_request_created
from app.messaging.channel_events import hiring_request_created_text


def test_hr_hiring_request_created_payload():
    req = SimpleNamespace(
        id=42,
        position="Логист",
        department=Departments.logistics,
        headcount=2,
        urgency="high",
        initiator_name="Петров",
        manager_name="Иванов",
    )
    text = hiring_request_created_text(req, actor_name="Сидоров Сидор")
    event = HrHiringRequestCreatedEvent.from_orm(
        req,
        text=text,
        actor_user_id="u-1",
        actor_name="Сидоров Сидор",
    )
    data = event.to_dict()
    assert data["event_type"] == "hr.hiring_request.created"
    assert data["hiring_request_id"] == 42
    assert data["position"] == "Логист"
    assert data["department"] == "логистический"
    assert data["headcount"] == 2
    assert data["actor_name"] == "Сидоров Сидор"
    assert data["actor_user_id"] == "u-1"
    assert "З-42" in data["text"]
    assert "Создал: Сидоров Сидор" in data["text"]
    UUID(data["event_id"])
    assert isinstance(data["occurred_at"], str)


def test_hr_hiring_request_payload_omits_nulls_and_fills_actor_from_initiator():
    req = SimpleNamespace(
        id=3,
        position="QA",
        department=None,
        headcount=None,
        urgency=None,
        initiator_name="Петров Пётр",
        manager_name="Иванов",
    )
    event = HrHiringRequestCreatedEvent.from_orm(req, text="Создана заявка на подбор З-3")
    data = event.to_dict()
    assert "headcount" not in data
    assert "department" not in data
    assert data["actor_name"] == "Петров Пётр"
    assert data["initiator_name"] == "Петров Пётр"


@pytest.mark.asyncio
async def test_publish_hr_hiring_request_created():
    producer = MagicMock()
    producer.publish = AsyncMock(return_value=True)
    req = SimpleNamespace(
        id=7,
        position="Backend",
        department=Departments.it,
        headcount=1,
        urgency=None,
        initiator_name="HR",
        manager_name="HR",
    )
    with patch(
        "app.events.publisher.get_message_event_producer",
        return_value=producer,
    ):
        ok = await publish_hr_hiring_request_created(
            req, actor_user_id="abc", actor_name="Иванов Иван"
        )
    assert ok is True
    event = producer.publish.await_args.args[0]
    assert isinstance(event, HrHiringRequestCreatedEvent)
    assert event.hiring_request_id == 7
    assert event.actor_name == "Иванов Иван"
    assert "Создал: Иванов Иван" in event.text
    assert "Backend" in event.text


@pytest.mark.asyncio
async def test_publish_hr_hiring_request_created_skips_without_id():
    producer = MagicMock()
    producer.publish = AsyncMock()
    with patch(
        "app.events.publisher.get_message_event_producer",
        return_value=producer,
    ):
        ok = await publish_hr_hiring_request_created(SimpleNamespace(id=None))
    assert ok is False
    producer.publish.assert_not_called()
