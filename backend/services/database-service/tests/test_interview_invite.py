from datetime import date, time, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.v1.enums import CandidateStatus
from app.endpoints.v1 import messages as mod
from app.endpoints.v1 import schedule as schedule_mod
from app.schemas.v1.messages import SendInterviewInviteData
from app.schemas.v1.schedule import EnsureBookRequest


@pytest.mark.asyncio
async def test_send_interview_invite_syncs_hh_and_books_slot():
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.get = AsyncMock(return_value=SimpleNamespace(id=5, full_name="Иванов Артём Валерьевич"))

    slot = SimpleNamespace(
        id=44,
        date=date(2026, 7, 9),
        start_time=time(16, 0),
        end_time=time(17, 0),
        is_booked=True,
        candidate_id=5,
    )
    slot.model_dump = lambda **kwargs: {"id": 44, "candidate_id": 5}
    hh_sync = AsyncMock(return_value={"status": "ok"})
    set_status = AsyncMock(return_value=True)
    ensure_book = AsyncMock(return_value=slot)

    with patch.object(mod, "sync_candidate_hh_action", hh_sync), patch.object(
        mod, "set_candidate_vacancy_status", set_status
    ), patch.object(mod, "ensure_and_book_slot", ensure_book):
        out = await mod.send_interview_invite_endpoint(
            SendInterviewInviteData(
                candidate_id=5,
                message="Артём Валерьевич, здравствуйте!\nПриглашаем вас на собеседование",
                hr_id="erp-1",
                interview_date=date(2026, 7, 9),
                start_time=time(16, 0),
            ),
            db,
            None,
        )

    assert out["status"] == "ok"
    assert out["delivery"] == "sent"
    ensure_book.assert_awaited_once()
    assert ensure_book.await_args.kwargs.get("commit") is False
    set_status.assert_awaited_once()
    assert set_status.await_args.args[2] == CandidateStatus.interview
    hh_sync.assert_awaited_once()
    assert hh_sync.await_args.args[2] == "interview"
    assert "Приглашаем вас на собеседование" in hh_sync.await_args.kwargs["message"]
    assert out["reminder_scheduled"] is False


@pytest.mark.asyncio
async def test_send_interview_invite_schedules_candidate_reminder():
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()
    db.get = AsyncMock(return_value=SimpleNamespace(id=5, full_name="Иванов Артём Валерьевич"))
    hh_sync = AsyncMock(return_value={"status": "ok"})

    with patch.object(mod, "sync_candidate_hh_action", hh_sync), patch.object(
        mod, "set_candidate_vacancy_status", AsyncMock(return_value=True)
    ), patch.object(mod, "ensure_and_book_slot", AsyncMock()):
        out = await mod.send_interview_invite_endpoint(
            SendInterviewInviteData(
                candidate_id=5,
                message="Приглашаем вас на собеседование",
                book_calendar=False,
                remind_candidate=True,
                remind_at=datetime(2026, 8, 28, 9, 0, 0, tzinfo=timezone.utc),
                reminder_message="Артём Валерьевич, напоминаем о собеседовании",
            ),
            db,
            None,
        )

    assert out["reminder_scheduled"] is True
    db.add.assert_called_once()
    row = db.add.call_args.args[0]
    assert row.is_send is False
    assert row.candidate_id == 5
    assert "напоминаем" in row.message.lower()


@pytest.mark.asyncio
async def test_send_interview_invite_requires_remind_at():
    from fastapi import HTTPException

    db = MagicMock()
    db.get = AsyncMock(return_value=SimpleNamespace(id=5, full_name="Иван"))
    with pytest.raises(HTTPException) as ei:
        await mod.send_interview_invite_endpoint(
            SendInterviewInviteData(
                candidate_id=5,
                message="Приглашаем вас на собеседование",
                book_calendar=False,
                remind_candidate=True,
            ),
            db,
            None,
        )
    assert ei.value.status_code == 400
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_send_interview_invite_skips_calendar_without_schedule():
    db = MagicMock()
    db.commit = AsyncMock()
    db.get = AsyncMock(return_value=SimpleNamespace(id=5, full_name="Иван"))
    hh_sync = AsyncMock(return_value={"status": "ok"})
    ensure_book = AsyncMock()
    with patch.object(mod, "sync_candidate_hh_action", hh_sync), patch.object(
        mod, "set_candidate_vacancy_status", AsyncMock(return_value=True)
    ), patch.object(mod, "ensure_and_book_slot", ensure_book):
        out = await mod.send_interview_invite_endpoint(
            SendInterviewInviteData(
                candidate_id=5,
                message="Приглашаем вас на собеседование",
                book_calendar=False,
            ),
            db,
            None,
        )
    assert out["status"] == "ok"
    ensure_book.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_and_book_creates_when_missing():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    empty = MagicMock()
    empty.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=empty)

    created = []

    def add_side_effect(slot):
        slot.id = 9
        created.append(slot)

    db.add.side_effect = add_side_effect

    out = await schedule_mod.ensure_and_book_slot(
        db,
        hr_id="erp-1",
        candidate_id=5,
        slot_date=date(2026, 7, 9),
        start_time=time(16, 0),
    )
    assert out.id == 9
    assert out.is_booked is True
    assert out.candidate_id == 5
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_ensure_and_book_can_flush_without_commit():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    empty = MagicMock()
    empty.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=empty)

    def add_side_effect(slot):
        slot.id = 12

    db.add.side_effect = add_side_effect
    await schedule_mod.ensure_and_book_slot(
        db,
        hr_id="erp-1",
        candidate_id=5,
        slot_date=date(2026, 7, 9),
        start_time=time(16, 0),
        commit=False,
    )
    db.flush.assert_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_and_book_reuses_same_candidate():
    slot = SimpleNamespace(
        id=3,
        date=date(2026, 7, 9),
        start_time=time(16, 0),
        end_time=time(17, 0),
        is_booked=True,
        candidate_id=5,
        candidate=SimpleNamespace(full_name="Иван"),
    )
    found = MagicMock()
    found.scalars.return_value.all.return_value = [slot]
    db = MagicMock()
    db.execute = AsyncMock(return_value=found)
    out = await schedule_mod.ensure_and_book_slot(
        db,
        hr_id="erp-1",
        candidate_id=5,
        slot_date=date(2026, 7, 9),
        start_time=time(16, 0),
    )
    assert out.id == 3
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_and_book_prefers_free_slot_over_other_candidate():
    taken = SimpleNamespace(
        id=1,
        date=date(2026, 7, 9),
        start_time=time(16, 0),
        end_time=time(17, 0),
        is_booked=True,
        candidate_id=99,
    )
    free = SimpleNamespace(
        id=2,
        date=date(2026, 7, 9),
        start_time=time(16, 0),
        end_time=time(17, 0),
        is_booked=False,
        candidate_id=None,
    )
    listed = MagicMock()
    listed.scalars.return_value.all.return_value = [taken, free]
    refreshed = MagicMock()
    booked_row = SimpleNamespace(
        id=2,
        date=date(2026, 7, 9),
        start_time=time(16, 0),
        end_time=time(17, 0),
        is_booked=True,
        candidate_id=5,
        candidate=SimpleNamespace(full_name="Артём"),
    )
    refreshed.scalar_one.return_value = booked_row
    db = MagicMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock(side_effect=[listed, MagicMock(rowcount=1), refreshed])

    out = await schedule_mod.ensure_and_book_slot(
        db,
        hr_id="erp-1",
        candidate_id=5,
        slot_date=date(2026, 7, 9),
        start_time=time(16, 0),
    )
    assert out.id == 2
    assert out.candidate_id == 5
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_ensure_book_endpoint_delegates():
    db = MagicMock()
    with patch.object(
        schedule_mod,
        "ensure_and_book_slot",
        new=AsyncMock(return_value=SimpleNamespace(id=1)),
    ) as ensure:
        body = EnsureBookRequest(
            hr_id="erp-1",
            candidate_id=7,
            date=date(2026, 7, 9),
            start_time=time(16, 0),
        )
        await schedule_mod.ensure_book_slot_endpoint(body, db)
        ensure.assert_awaited_once()
