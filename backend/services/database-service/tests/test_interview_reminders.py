from datetime import date, datetime, time, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.interview_reminders import (
    build_candidate_reminder_message,
    dispatch_due_interview_reminders,
    floor_to_seconds,
    hh_message_sent,
    normalize_remind_at,
    purge_sent_interview_reminders,
    schedule_interview_reminder,
)


def test_reminder_text_uses_patronymic_greeting():
    text = build_candidate_reminder_message(
        full_name="Иванов Артём Валерьевич",
        interview_date=date(2026, 8, 28),
        interview_time=time(10, 0),
    )
    assert text.startswith("Артём Валерьевич, здравствуйте!")
    assert "28.08.2026 в 10:00" in text
    assert "собеседовании в ALT" in text


def test_normalize_naive_remind_at_is_samara():
    naive = datetime(2026, 8, 28, 9, 0, 0)
    utc = normalize_remind_at(naive)
    assert utc.tzinfo is not None
    assert utc.hour == 5  # Samara UTC+4


def test_schedule_row_is_unsent():
    row = schedule_interview_reminder(
        candidate_id=6,
        remind_at=datetime(2026, 8, 28, 9, 0, 1, 123456, tzinfo=timezone.utc),
        message="Напоминаем о собеседовании",
        interview_date=date(2026, 8, 28),
        interview_time=time(10, 0),
    )
    assert row.is_send is False
    assert row.remind_at.microsecond == 0
    assert row.candidate_id == 6


def test_hh_message_sent_only_ok():
    assert hh_message_sent({"status": "ok"}) is True
    assert hh_message_sent({"status": "unavailable"}) is False
    assert hh_message_sent(None) is False


@pytest.mark.asyncio
async def test_dispatch_sends_due_unsent_and_sets_is_send():
    due = SimpleNamespace(
        id=1,
        candidate_id=6,
        message="ping",
        remind_at=datetime(2026, 8, 28, 9, 0, 0, tzinfo=timezone.utc),
        is_send=False,
        sent_at=None,
        last_error=None,
    )
    executed = MagicMock()
    executed.scalars.return_value.all.return_value = [due]
    db = MagicMock()
    db.execute = AsyncMock(return_value=executed)
    db.commit = AsyncMock()
    send = AsyncMock(return_value={"status": "ok"})

    n = await dispatch_due_interview_reminders(
        db,
        now=datetime(2026, 8, 28, 9, 0, 0, tzinfo=timezone.utc),
        send=send,
    )
    assert n == 1
    send.assert_awaited_once_with(6, "ping")
    assert due.is_send is True
    assert due.sent_at == floor_to_seconds(datetime(2026, 8, 28, 9, 0, 0, tzinfo=timezone.utc))
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_dispatch_keeps_unsent_when_hh_fails():
    row = SimpleNamespace(
        id=1,
        candidate_id=6,
        message="ping",
        remind_at=datetime(2026, 8, 28, 9, 0, 0, tzinfo=timezone.utc),
        is_send=False,
        sent_at=None,
        last_error=None,
    )
    executed = MagicMock()
    executed.scalars.return_value.all.return_value = [row]
    db = MagicMock()
    db.execute = AsyncMock(return_value=executed)
    db.commit = AsyncMock()

    n = await dispatch_due_interview_reminders(
        db,
        now=datetime(2026, 8, 28, 9, 0, 5, tzinfo=timezone.utc),
        send=AsyncMock(return_value={"status": "unavailable", "reason": "hh_api_rejected"}),
    )
    assert n == 0
    assert row.is_send is False
    assert "hh_api_rejected" in row.last_error


@pytest.mark.asyncio
async def test_purge_deletes_sent_only():
    db = MagicMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(rowcount=3))
    db.commit = AsyncMock()
    n = await purge_sent_interview_reminders(db)
    assert n == 3
    db.commit.assert_awaited()
    compiled = str(db.execute.await_args.args[0].compile(compile_kwargs={"literal_binds": True}))
    assert "interview_reminders" in compiled.lower()
    assert "is_send" in compiled.lower()
