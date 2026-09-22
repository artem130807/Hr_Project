"""Domain event + RabbitMQ producer for HR calendar events."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.hr_events import HrEventCreatedEvent
from app.endpoints.v1 import events as events_mod
from app.messaging.message_event_producer import MessageEventProducer
from app.schemas.v1.events import EventCreate


def test_hr_event_created_preserves_remind_before_zero():
    row = SimpleNamespace(
        id=42,
        type="birthday",
        event_date=date(2026, 8, 19),
        remind_before=0,
        remind_at_time=None,
        employee_name="Иван",
        child_name=None,
        telegram_user="@ivan",
        note=None,
        is_done=False,
    )
    evt = HrEventCreatedEvent.from_orm(row, user_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    assert evt.remind_before == 0
    assert evt.to_dict()["remind_before"] == 0
    assert evt.to_dict()["remind_at_time"] is None


def test_hr_event_created_serializes_remind_at_time():
    from datetime import time as dt_time

    row = SimpleNamespace(
        id=7,
        type="birthday",
        event_date=date(2026, 8, 19),
        remind_before=0,
        remind_at_time=dt_time(15, 30),
        employee_name="Иван",
        child_name=None,
        telegram_user="@ivan",
        note=None,
        is_done=False,
    )
    evt = HrEventCreatedEvent.from_orm(row)
    assert evt.remind_at_time == "15:30"
    assert evt.to_dict()["remind_at_time"] == "15:30"


def test_hr_event_created_defaults_none_remind_before_to_three():
    row = SimpleNamespace(
        id=1,
        type="other",
        event_date=date(2026, 1, 1),
        remind_before=None,
        employee_name=None,
        child_name=None,
        telegram_user=None,
        note="x",
        is_done=False,
    )
    evt = HrEventCreatedEvent.from_orm(row)
    assert evt.remind_before == 3


def test_hr_event_created_payload():
    row = SimpleNamespace(
        id=42,
        type="birthday",
        event_date=date(2026, 5, 1),
        remind_before=3,
        employee_name="Иван Иванов",
        child_name=None,
        telegram_user="@ivan",
        note="note",
        is_done=False,
    )
    evt = HrEventCreatedEvent.from_orm(
        row,
        user_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        actor_user_id="u-1",
    )
    data = evt.to_dict()
    assert data["event_type"] == "hr.event.created"
    assert data["hr_event_id"] == 42
    assert data["event_date"] == "2026-05-01"
    assert data["telegram_user"] == "@ivan"
    assert data["user_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert data["userId"] == data["user_id"]
    assert data["actor_user_id"] == "u-1"
    assert data["occurrence"] == "initial"
    assert data["event_id"]
    assert data["occurred_at"]


@pytest.mark.asyncio
async def test_producer_skips_without_rabbit_url():
    producer = MessageEventProducer(rabbit_url="", queue="message.entity_changed")
    ok = await producer.publish(
        HrEventCreatedEvent(
            hr_event_id=1,
            type="other",
            event_date=date(2026, 1, 1),
        )
    )
    assert ok is False


@pytest.mark.asyncio
async def test_producer_publishes_to_queue():
    producer = MessageEventProducer(rabbit_url="amqp://guest:guest@localhost:5672/", queue="message.entity_changed")
    with patch.object(producer, "_publish_sync") as sync_publish:
        ok = await producer.publish(
            HrEventCreatedEvent(
                hr_event_id=7,
                type="work_anniversary",
                event_date=date(2026, 8, 18),
                note="Годовщина",
            )
        )
    assert ok is True
    sync_publish.assert_called_once()
    args, _kwargs = sync_publish.call_args
    payload, event_type = args
    assert event_type == "hr.event.created"
    assert payload["hr_event_id"] == 7
    assert payload["type"] == "work_anniversary"


@pytest.mark.asyncio
async def test_create_event_publishes_domain_event_with_recipient_user_id():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    created = SimpleNamespace(
        id=11,
        type="birthday",
        event_date=date(2026, 9, 1),
        remind_before=3,
        employee_name="Иван",
        child_name=None,
        telegram_user="@ivan_hr",
        note=None,
        is_done=False,
    )

    async def _refresh(_obj):
        for k, v in created.__dict__.items():
            setattr(_obj, k, v)

    db.refresh = AsyncMock(side_effect=_refresh)
    publish = AsyncMock(return_value=True)

    with patch.object(events_mod, "publish_hr_calendar_event", publish), patch.object(
        events_mod, "Event", side_effect=lambda **kw: SimpleNamespace(id=None, **kw)
    ):
        data = EventCreate(
            type="birthday",
            event_date=date(2026, 9, 1),
            employee_name="Иван",
            telegram_user="@ivan_hr",
        )
        result = await events_mod.create_event(data, db)

    assert result.telegram_user == "@ivan_hr"
    publish.assert_awaited_once()
    published_row = publish.await_args.args[0]
    assert published_row.telegram_user == "@ivan_hr"
    assert publish.await_args.kwargs["occurrence"] == "initial"


@pytest.mark.asyncio
async def test_create_event_publishes_remind_at_time():
    from datetime import time as dt_time

    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    created = SimpleNamespace(
        id=22,
        type="birthday",
        event_date=date(2026, 8, 19),
        remind_before=0,
        remind_at_time=dt_time(15, 0),
        employee_name="Иван",
        child_name=None,
        telegram_user="@ivan_hr",
        note=None,
        is_done=False,
    )

    async def _refresh(_obj):
        for k, v in created.__dict__.items():
            setattr(_obj, k, v)

    db.refresh = AsyncMock(side_effect=_refresh)
    publish = AsyncMock(return_value=True)

    with patch.object(events_mod, "publish_hr_calendar_event", publish), patch.object(
        events_mod, "Event", side_effect=lambda **kw: SimpleNamespace(id=None, **kw)
    ):
        data = EventCreate(
            type="birthday",
            event_date=date(2026, 8, 19),
            employee_name="Иван",
            telegram_user="@ivan_hr",
            remind_before=0,
            remind_at_time="15:00",
        )
        await events_mod.create_event(data, db)

    row = publish.await_args.args[0]
    assert row.remind_before == 0
    assert row.remind_at_time == dt_time(15, 0)


@pytest.mark.asyncio
async def test_create_other_event_clears_employee_name_and_publishes():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    created = SimpleNamespace(
        id=11,
        type="other",
        event_date=date(2026, 9, 1),
        remind_before=3,
        employee_name=None,
        child_name=None,
        telegram_user=None,
        note="misc",
        is_done=False,
    )

    async def _refresh(_obj):
        for k, v in created.__dict__.items():
            setattr(_obj, k, v)

    db.refresh = AsyncMock(side_effect=_refresh)
    publish = AsyncMock(return_value=True)

    with patch.object(events_mod, "publish_hr_calendar_event", publish), patch.object(
        events_mod, "Event", side_effect=lambda **kw: SimpleNamespace(id=None, **kw)
    ):
        data = EventCreate(
            type="other",
            event_date=date(2026, 9, 1),
            employee_name="should be cleared",
            note="misc",
        )
        result = await events_mod.create_event(data, db)

    assert result.employee_name is None
    publish.assert_awaited_once()
    assert publish.await_args.args[0].type == "other"


@pytest.mark.asyncio
async def test_create_permanent_event_schedules_next_dispatch_and_publishes():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    stored = {}

    def _event(**kw):
        row = SimpleNamespace(id=None, **kw)
        stored["row"] = row
        return row

    async def _refresh(_obj):
        _obj.id = 90

    db.refresh = AsyncMock(side_effect=_refresh)
    publish = AsyncMock(return_value=True)

    with patch.object(events_mod, "publish_hr_calendar_event", publish), patch.object(
        events_mod, "Event", side_effect=_event
    ):
        data = EventCreate(
            type="permanent",
            event_date=date(2026, 8, 24),
            note="каждый месяц",
            remind_before=0,
            repeat_interval_count=1,
            repeat_interval_unit="month",
        )
        result = await events_mod.create_event(data, db)

    assert result.next_dispatch_at is not None
    assert result.repeat_interval_unit == "month"
    assert result.last_dispatched_at is not None
    publish.assert_awaited_once()
    assert publish.await_args.kwargs["occurrence"] == "initial"
    assert db.commit.await_count == 2


@pytest.mark.asyncio
async def test_create_permanent_event_keeps_first_slot_if_broker_skips():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    def _event(**kw):
        return SimpleNamespace(id=None, **kw)

    async def _refresh(_obj):
        if _obj.id is None:
            _obj.id = 91

    db.refresh = AsyncMock(side_effect=_refresh)
    publish = AsyncMock(return_value=False)

    with patch.object(events_mod, "publish_hr_calendar_event", publish), patch.object(
        events_mod, "Event", side_effect=_event
    ):
        data = EventCreate(
            type="permanent",
            event_date=date(2026, 8, 24),
            note="retry",
            remind_before=0,
            repeat_interval_count=1,
            repeat_interval_unit="month",
        )
        result = await events_mod.create_event(data, db)

    assert getattr(result, "last_dispatched_at", None) is None
    assert result.next_dispatch_at.date() == date(2026, 8, 24)
