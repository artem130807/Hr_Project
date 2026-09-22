from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from hr_notify.consumer import process_delivery_body
from hr_notify.handler import schedule_hr_notification
from hr_notify.schedule import compute_notify_at, should_send_immediately
from hr_notify.schemas import parse_hr_event_notify
from hr_notify.tasks import resolve_chat_id, send_hr_telegram_notification_impl

FIXTURE = Path(__file__).parent / "fixtures" / "hr_event_notify.json"


def test_compute_notify_at():
    got = compute_notify_at("2026-05-01", 3)
    assert got == datetime(2026, 4, 28, tzinfo=timezone.utc)
    assert compute_notify_at(date(2026, 5, 1), 0) == datetime(2026, 5, 1, tzinfo=timezone.utc)


def test_compute_notify_at_samara_clock():
    # 28 Apr 2026 10:30 Samara (UTC+4) → 06:30 UTC
    got = compute_notify_at("2026-05-01", 3, "10:30")
    assert got == datetime(2026, 4, 28, 6, 30, tzinfo=timezone.utc)


def test_remind_before_zero_with_future_samara_time_is_eta():
    notify_at = compute_notify_at(date(2026, 8, 19), 0, "18:00")
    # 18:00 Samara = 14:00 UTC
    assert notify_at == datetime(2026, 8, 19, 14, 0, tzinfo=timezone.utc)
    now = datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc)
    assert should_send_immediately(notify_at, now=now) is False
    now_after = datetime(2026, 8, 19, 15, 0, tzinfo=timezone.utc)
    assert should_send_immediately(notify_at, now=now_after) is True


def test_schedule_with_samara_time_eta():
    data = {
        "event_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "event_type": "hr.event.notify",
        "occurred_at": "2026-08-19T08:00:00Z",
        "hr_event_id": 100,
        "type": "birthday",
        "event_date": "2026-08-19",
        "remind_before": 0,
        "remind_at_time": "18:00",
        "notify_at": "2026-08-19T14:00:00Z",
        "user_id": "11111111-2222-3333-4444-555555555555",
        "content": "HR: День рождения",
    }
    payload = parse_hr_event_notify(data)
    task = _fake_huey_task()
    mode = schedule_hr_notification(
        payload,
        task,
        now=datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc),
    )
    assert mode == "eta"
    task.schedule.assert_called_once()


def test_remind_before_zero_today_is_immediate():
    """event_date=today, remind_before=0 → notify_at=today 00:00 UTC → send now."""
    today = date(2026, 8, 19)
    notify_at = compute_notify_at(today, 0)
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    assert notify_at == datetime(2026, 8, 19, tzinfo=timezone.utc)
    assert should_send_immediately(notify_at, now=now) is True


def test_schedule_zero_day_today_enqueues_immediate():
    data = {
        "event_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "event_type": "hr.event.notify",
        "occurred_at": "2026-08-19T12:00:00Z",
        "hr_event_id": 99,
        "type": "birthday",
        "employee_name": "Тест",
        "event_date": "2026-08-19",
        "remind_before": 0,
        "notify_at": "2026-08-19T00:00:00Z",
        "user_id": "11111111-2222-3333-4444-555555555555",
        "content": "HR: День рождения",
    }
    payload = parse_hr_event_notify(data)
    task = _fake_huey_task()
    mode = schedule_hr_notification(
        payload,
        task,
        now=datetime(2026, 8, 19, 15, 0, tzinfo=timezone.utc),
    )
    assert mode == "immediate"
    task.assert_called_once_with("HR: День рождения")


def test_should_send_immediately():
    past = datetime(2020, 1, 1, tzinfo=timezone.utc)
    future = datetime(2099, 1, 1, tzinfo=timezone.utc)
    now = datetime(2026, 8, 18, tzinfo=timezone.utc)
    assert should_send_immediately(past, now=now) is True
    assert should_send_immediately(future, now=now) is False


def test_parse_hr_event_notify_fixture():
    payload = parse_hr_event_notify(FIXTURE.read_bytes())
    assert payload.event_type == "hr.event.notify"
    assert payload.hr_event_id == 55
    assert payload.notify_at == "2026-04-28T00:00:00Z"
    assert "День рождения" in payload.content
    assert payload.notify_at_dt() == datetime(2026, 4, 28, tzinfo=timezone.utc)


def _fake_huey_task():
    task = MagicMock()
    task.schedule = MagicMock()
    return task


def test_schedule_hr_notification_immediate_when_past():
    payload = parse_hr_event_notify(FIXTURE.read_bytes())
    task = _fake_huey_task()
    mode = schedule_hr_notification(
        payload,
        task,
        now=datetime(2026, 8, 18, tzinfo=timezone.utc),
    )
    assert mode == "immediate"
    task.assert_called_once_with(payload.content)
    task.schedule.assert_not_called()


def test_schedule_hr_notification_eta_when_future():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["notify_at"] = "2099-01-01T00:00:00Z"
    payload = parse_hr_event_notify(data)
    task = _fake_huey_task()
    mode = schedule_hr_notification(
        payload,
        task,
        now=datetime(2026, 8, 18, tzinfo=timezone.utc),
    )
    assert mode == "eta"
    task.assert_not_called()
    task.schedule.assert_called_once_with(
        args=(payload.content,),
        eta=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )


def test_consumer_schedules_huey(monkeypatch):
    """process_delivery_body must use Huey task call / schedule API correctly."""
    fake_task = _fake_huey_task()
    monkeypatch.setattr(
        "hr_notify.consumer.send_hr_telegram_notification",
        fake_task,
    )
    mode = process_delivery_body(FIXTURE.read_bytes())
    assert mode == "immediate"
    fake_task.assert_called_once()
    assert "День рождения" in fake_task.call_args.args[0]


def test_send_hr_telegram_notification_impl():
    send = MagicMock()
    send_hr_telegram_notification_impl("hello", send_message=send)
    send.assert_called_once_with("hello")


def test_resolve_chat_id_prefers_hr_chat(monkeypatch):
    monkeypatch.setenv("HR_NOTIFY_CHAT_ID", "-100222")
    monkeypatch.setenv("CHAT_ID", "-100111")
    assert resolve_chat_id() == "-100222"


def test_resolve_chat_id_falls_back(monkeypatch):
    monkeypatch.delenv("HR_NOTIFY_CHAT_ID", raising=False)
    monkeypatch.setenv("CHAT_ID", "-100111")
    assert resolve_chat_id() == "-100111"


def test_huey_app_registers_send_task():
    from hr_notify.huey_app import huey

    registry = getattr(huey._registry, "_registry", {})
    assert any("send_hr_telegram_notification" in str(name) for name in registry)


def test_pipeline_accepts_notify_json_without_user_id():
    """message-service may omit ERP uuid; Telegram channel notify must still fire."""
    body = json.dumps(
        {
            "event_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "event_type": "hr.event.notify",
            "occurred_at": "2026-08-19T12:00:00Z",
            "hr_event_id": 1,
            "type": "other",
            "telegram_user": "@Artem56798",
            "event_date": "2026-08-19",
            "remind_before": 0,
            "notify_at": "2026-08-19T00:00:00Z",
            "user_id": "",
            "content": "HR: Другое\nTelegram: @Artem56798",
        }
    ).encode()
    payload = parse_hr_event_notify(body)
    task = _fake_huey_task()
    mode = schedule_hr_notification(
        payload,
        task,
        now=datetime(2026, 8, 19, 15, 0, tzinfo=timezone.utc),
    )
    assert mode == "immediate"
    task.assert_called_once()
    assert "@Artem56798" in task.call_args.args[0]


def test_hiring_request_notify_is_always_immediate():
    data = {
        "event_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        "event_type": "hr.event.notify",
        "occurred_at": "2026-09-08T07:00:00Z",
        "hr_event_id": 42,
        "type": "hiring_request",
        "hiring_request_id": 42,
        "actor_name": "Иванов Иван",
        "position": "Логист",
        "department": "логистический",
        "headcount": 2,
        "notify_at": "2099-01-01T00:00:00Z",
        "content": "Создана заявка на подбор З-42\nСоздал: Иванов Иван",
    }
    payload = parse_hr_event_notify(data)
    assert payload.hiring_request_id == 42
    assert payload.actor_name == "Иванов Иван"
    task = _fake_huey_task()
    mode = schedule_hr_notification(
        payload,
        task,
        now=datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
    )
    assert mode == "immediate"
    task.assert_called_once_with(payload.content)
    task.schedule.assert_not_called()


def test_consumer_hiring_request_notify(monkeypatch):
    fake_task = _fake_huey_task()
    monkeypatch.setattr(
        "hr_notify.consumer.send_hr_telegram_notification",
        fake_task,
    )
    body = json.dumps(
        {
            "event_type": "hr.event.notify",
            "type": "hiring_request",
            "hiring_request_id": 7,
            "actor_name": "Сидоров",
            "notify_at": "2099-01-01T00:00:00Z",
            "content": "Создана заявка на подбор З-7\nСоздал: Сидоров",
        }
    ).encode()
    mode = process_delivery_body(body)
    assert mode == "immediate"
    fake_task.assert_called_once()
    assert "Создал: Сидоров" in fake_task.call_args.args[0]
