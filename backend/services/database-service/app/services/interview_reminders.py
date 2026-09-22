"""Candidate interview reminders delivered as hh.ru chat messages."""
from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Awaitable, Callable, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app_logging import logger
from app.db.v1.models import InterviewReminder
from app.events.recurrence import SAMARA, aware_utc

SendFn = Callable[[int, str], Awaitable[Optional[dict]]]


def floor_to_seconds(value: datetime) -> datetime:
    moment = aware_utc(value)
    return moment.replace(microsecond=0)


def normalize_remind_at(value: datetime) -> datetime:
    """Naive timestamps are Europe/Samara (HR panel clock); aware values stay UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=SAMARA).astimezone(timezone.utc)
    return value.astimezone(timezone.utc)


def _format_when(interview_date, interview_time: time | None) -> str:
    if interview_date is None:
        return "дату и время, указанные в приглашении"
    date_part = interview_date.strftime("%d.%m.%Y")
    if interview_time is None:
        return date_part
    return f"{date_part} в {interview_time.strftime('%H:%M')}"


def build_candidate_reminder_message(
    *,
    full_name: str | None = None,
    interview_date=None,
    interview_time: time | None = None,
) -> str:
    parts = (full_name or "").strip().split()
    greeting = " ".join(parts[1:3]) if len(parts) >= 3 else (parts[1] if len(parts) == 2 else (parts[0] if parts else "кандидат"))
    when = _format_when(interview_date, interview_time)
    return (
        f"{greeting}, здравствуйте!\n\n"
        "Напоминаем о собеседовании.\n"
        f"Дата и время: {when}\n\n"
        "Пожалуйста, подтвердите участие ответом на это сообщение. "
        "Если планы изменились — тоже напишите нам сюда."
    )


def hh_message_sent(result: object) -> bool:
    if not isinstance(result, dict):
        return False
    return str(result.get("status") or "").lower() == "ok"


async def _default_send(candidate_id: int, message: str) -> Optional[dict]:
    from app.utils.hh_sync import sync_candidate_hh_action

    return await sync_candidate_hh_action(None, candidate_id, "message", message=message)


def schedule_interview_reminder(
    *,
    candidate_id: int,
    remind_at: datetime,
    message: str,
    vacancy_id: int | None = None,
    interview_date=None,
    interview_time: time | None = None,
) -> InterviewReminder:
    text = (message or "").strip()
    if not text:
        raise ValueError("Текст напоминания обязателен")
    return InterviewReminder(
        candidate_id=int(candidate_id),
        vacancy_id=vacancy_id,
        interview_date=interview_date,
        interview_time=interview_time,
        remind_at=floor_to_seconds(normalize_remind_at(remind_at)),
        message=text,
        is_send=False,
    )


async def dispatch_due_interview_reminders(
    db: AsyncSession,
    *,
    now: Optional[datetime] = None,
    send: Optional[SendFn] = None,
    limit: int = 50,
) -> int:
    """Send unsent rows whose remind_at (to the second) is already due."""
    moment = floor_to_seconds(now or datetime.now(timezone.utc))
    send_fn = send or _default_send
    stmt = (
        select(InterviewReminder)
        .where(
            InterviewReminder.is_send.is_(False),
            InterviewReminder.remind_at <= moment,
        )
        .order_by(InterviewReminder.remind_at.asc(), InterviewReminder.id.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    sent = 0
    for row in rows:
        due = floor_to_seconds(row.remind_at)
        if due > moment:
            continue
        try:
            result = await send_fn(row.candidate_id, row.message)
        except Exception as exc:
            logger.exception("interview reminder %s send failed: %s", row.id, exc)
            row.last_error = str(exc)[:2000]
            continue
        if not hh_message_sent(result):
            detail = ""
            if isinstance(result, dict):
                detail = str(result.get("reason") or result.get("detail") or result.get("status") or "")
            row.last_error = (detail or "hh_send_failed")[:2000]
            logger.warning("interview reminder %s not sent: %s", row.id, result)
            continue
        row.is_send = True
        row.sent_at = moment
        row.last_error = None
        sent += 1
    await db.commit()
    return sent


async def purge_sent_interview_reminders(db: AsyncSession) -> int:
    result = await db.execute(
        delete(InterviewReminder).where(InterviewReminder.is_send.is_(True))
    )
    await db.commit()
    return int(result.rowcount or 0)
