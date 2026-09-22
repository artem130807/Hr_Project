from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.clients.api_client import APICLient

from app.schemas.v1.messages import (
    NewVacancyData,
    SendOfferData,
    SendInterviewInviteData,
    ExerciseData,
    SendProfessionalTestData,
)
from app.endpoints.v1.schedule import ensure_and_book_slot
from app.db.v1.enums import CandidateStatus, TestType
from app.db.v1.models import BotUser, Candidate, CandidateTestResult, Test
from app.dependencies import get_bot_client, get_hh_client
from app.db.middleware import get_db
from app.app_logging import logger
from app.utils.hh_sync import sync_candidate_hh_action
from app.utils.candidate_funnel import set_candidate_vacancy_status
from app.services.interview_reminders import (
    build_candidate_reminder_message,
    schedule_interview_reminder,
)
from app.services.candidate_documents import build_public_url, create_invite


router = APIRouter()


def _require_bot(bot: Optional[APICLient]) -> APICLient:
    if bot is None:
        raise HTTPException(503, "Bot service is not configured")
    return bot


def _build_prof_test_link(request: Request, test_id: int, candidate_id: int, result_id: int) -> str:
    base = (
        request.headers.get("Origin")
        or request.headers.get("origin")
        or str(request.base_url)
    ).rstrip("/")
    return (
        f"{base}/take/test/{int(test_id)}"
        f"?candidate_id={int(candidate_id)}&result_id={int(result_id)}"
    )


@router.post('/candidate/new-vacancy')
async def send_new_vacancy_endpoint(
    data: NewVacancyData,
    db: AsyncSession = Depends(get_db),
    bot: Optional[APICLient] = Depends(get_bot_client)
):
    bot = _require_bot(bot)
    query = (
        select(BotUser)
        .join(Candidate)
        .where(Candidate.id == data.candidate_id)
    )
    result = await db.execute(query)
    user: BotUser | None = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, 'BotUser not found')

    resp = await bot.post(
        '/v1/candidate/new-vacancy',
        params={
            "user_id": user.telegram_id,
            "vacancy_id": data.vacancy_id
        }
    )
    if not resp:
        logger.error('Error sending message')
        raise HTTPException(502, 'Failed to send message via bot service')
    return resp


@router.post('/candidate/offer')
@router.post('/candidate/send-offer')  # alias for older clients
async def send_offer_endpoint(
    data: SendOfferData,
    request: Request,
    db: AsyncSession = Depends(get_db),
    bot: Optional[APICLient] = Depends(get_bot_client),
    hh: Optional[APICLient] = Depends(get_hh_client),
):
    candidate = await db.get(Candidate, data.candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate not found")
    documents_url = None
    message_text = data.offer_text
    if data.include_documents_link:
        _invite, token = await create_invite(db, candidate, actor_id=None)
        documents_url = build_public_url(request, token)
        message_text = f"{message_text.rstrip()}\n\nДокументы для трудоустройства можно безопасно загрузить по ссылке:\n{documents_url}"
    query = (
        select(BotUser)
        .join(Candidate)
        .where(Candidate.id == data.candidate_id)
    )
    result = await db.execute(query)
    user: BotUser | None = result.scalar_one_or_none()

    if user and bot is None:
        raise HTTPException(503, "Bot service is not configured")
    # Snapshot ORM data before committing (sessions may expire on commit).
    telegram_id = user.telegram_id if user else None
    if documents_url:
        # Never deliver a link that is still invisible to other requests.
        # Delivery failure must not roll back an already delivered invitation.
        await db.commit()

    bot_resp = None
    if user:
        if bot is None:
            raise HTTPException(503, "Bot service is not configured")
        bot_resp = await bot.post(
            '/v1/candidate/send-offer',
            params={
                "user_id": telegram_id,
                "offer_text": message_text,
            }
        )
        if not bot_resp:
            logger.error('Error sending offer via bot')

    hh_resp = await sync_candidate_hh_action(
        hh,
        data.candidate_id,
        "offer",
        message=message_text,
    )

    if not bot_resp and not (isinstance(hh_resp, dict) and hh_resp.get("status") == "ok"):
        if not user:
            raise HTTPException(404, 'BotUser not found')
        raise HTTPException(502, 'Failed to send offer')
    await db.commit()
    response = bot_resp or hh_resp
    # Preserve the existing delivery response contract for API clients and only
    # enrich it with the generated form URL.
    if isinstance(response, dict):
        return {**response, "documents_url": documents_url}
    return {"status": "ok", "delivery": response, "documents_url": documents_url}


def _slot_payload(slot):
    if slot is None:
        return None
    dump = getattr(slot, "model_dump", None)
    if callable(dump):
        try:
            return dump(mode="json")
        except TypeError:
            return dump()
    return slot


@router.post("/candidate/interview-invite")
async def send_interview_invite_endpoint(
    data: SendInterviewInviteData,
    db: AsyncSession = Depends(get_db),
    hh: Optional[APICLient] = Depends(get_hh_client),
):
    message_text = (data.message or "").strip()
    if not message_text:
        raise HTTPException(400, "Текст приглашения обязателен")

    candidate = await db.get(Candidate, data.candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate not found")

    reminder_row = None
    if data.remind_candidate:
        if data.remind_at is None:
            raise HTTPException(400, "Укажите дату и время напоминания кандидату")
        reminder_text = (data.reminder_message or "").strip() or build_candidate_reminder_message(
            full_name=getattr(candidate, "full_name", None),
            interview_date=data.interview_date,
            interview_time=data.start_time,
        )
        try:
            reminder_row = schedule_interview_reminder(
                candidate_id=data.candidate_id,
                remind_at=data.remind_at,
                message=reminder_text,
                interview_date=data.interview_date,
                interview_time=data.start_time,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    slot = None
    should_book = (
        bool(data.book_calendar)
        and bool(str(data.hr_id or "").strip())
        and data.interview_date is not None
        and data.start_time is not None
    )
    if should_book:
        slot = await ensure_and_book_slot(
            db,
            hr_id=data.hr_id,
            candidate_id=data.candidate_id,
            slot_date=data.interview_date,
            start_time=data.start_time,
            end_time=data.end_time,
            commit=False,
        )

    if reminder_row is not None:
        db.add(reminder_row)

    try:
        updated = await set_candidate_vacancy_status(
            db, data.candidate_id, CandidateStatus.interview
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error("Failed to set interview status for candidate %s: %s", data.candidate_id, exc)
        raise HTTPException(500, "Не удалось сохранить статус собеседования") from exc

    hh_sync = await sync_candidate_hh_action(
        hh,
        data.candidate_id,
        "interview",
        message=message_text,
    )
    delivery = "sent"
    warning = None
    if isinstance(hh_sync, dict):
        sync_status = str(hh_sync.get("status") or "").lower()
        if sync_status != "ok":
            delivery = sync_status or "unavailable"
            reason = hh_sync.get("reason")
            detail = hh_sync.get("detail")
            extra = reason or ""
            if detail and str(detail) not in extra:
                extra = f"{extra}: {detail}" if extra else str(detail)
            warning = (
                "Собеседование сохранено, но HH не принял приглашение"
                + (f" ({extra})" if extra else "")
            )
            logger.warning(
                "HH interview invite not sent for candidate %s: %s",
                data.candidate_id,
                hh_sync,
            )
    else:
        delivery = "unavailable"
        warning = "Собеседование сохранено, но отправка в HH сейчас недоступна"

    return {
        "status": "ok",
        "candidate_id": data.candidate_id,
        "funnel_updated": bool(updated),
        "slot": _slot_payload(slot),
        "hh_sync": hh_sync if isinstance(hh_sync, dict) else {"status": "unavailable"},
        "delivery": delivery,
        "warning": warning,
        "reminder_scheduled": reminder_row is not None,
    }


@router.post('/candidate/exercise')
async def send_exercise_endpoint(
    data: ExerciseData,
    db: AsyncSession = Depends(get_db),
    bot: Optional[APICLient] = Depends(get_bot_client)
):
    bot = _require_bot(bot)
    query = (
        select(BotUser)
        .join(Candidate)
        .where(Candidate.id == data.candidate_id)
    )
    result = await db.execute(query)
    user: BotUser | None = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, 'BotUser not found')

    resp = await bot.post(
        '/v1/candidate/exercise',
        params={
            "user_id": user.telegram_id,
            "instruction_text": data.instruction_text,
            "minutes": data.minutes,
        }
    )
    if not resp:
        logger.error('Error sending message')
        raise HTTPException(502, 'Failed to send message via bot service')
    return resp


@router.post('/candidate/professional-test/send')
async def send_professional_test_endpoint(
    data: SendProfessionalTestData,
    request: Request,
    db: AsyncSession = Depends(get_db),
    hh: Optional[APICLient] = Depends(get_hh_client),
):
    candidate = await db.get(Candidate, data.candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate not found")

    test = await db.get(Test, data.test_id)
    if not test:
        raise HTTPException(404, "Test not found")
    if test.test_type != TestType.questions:
        raise HTTPException(400, "Можно отправлять только профессиональные вопросно-ответные тесты")

    existing = await db.execute(
        select(CandidateTestResult).where(
            CandidateTestResult.candidate_id == data.candidate_id,
            CandidateTestResult.test_id == data.test_id,
        )
    )
    result_row = existing.scalar_one_or_none()
    created = False
    if result_row is None:
        result_row = CandidateTestResult(
            candidate_id=data.candidate_id,
            test_id=data.test_id,
            score=None,
            comment=None,
            has_image=False,
        )
        db.add(result_row)
        try:
            await db.flush()
            created = True
        except Exception as exc:
            await db.rollback()
            logger.error("Failed to persist candidate test relation: %s", exc)
            raise HTTPException(500, "Не удалось создать связь кандидата с тестом")

    try:
        await set_candidate_vacancy_status(
            db, data.candidate_id, CandidateStatus.test_sent
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error("Failed to set test_sent status for candidate %s: %s", data.candidate_id, exc)
        raise HTTPException(500, "Не удалось сохранить отправку теста")

    test_url = _build_prof_test_link(request, data.test_id, data.candidate_id, result_row.id)
    candidate_name = (candidate.full_name or "кандидат").strip()
    custom_text = (data.message or "").strip()
    message_text = custom_text or (
        f"Здравствуйте, {candidate_name}!\n"
        f"Пожалуйста, пройдите профессиональный тест:\n{test.name}\n{test_url}"
    )

    hh_sync = await sync_candidate_hh_action(
        hh,
        data.candidate_id,
        "message",
        message=message_text,
    )
    delivery = "sent"
    warning = None
    if isinstance(hh_sync, dict):
        sync_status = str(hh_sync.get("status") or "").lower()
        if sync_status != "ok":
            delivery = sync_status or "unavailable"
            reason = hh_sync.get("reason")
            detail = hh_sync.get("detail")
            extra = reason or ""
            if detail and str(detail) not in extra:
                extra = f"{extra}: {detail}" if extra else str(detail)
            warning = (
                "Ссылка на тест сохранена, но HH не принял сообщение"
                + (f" ({extra})" if extra else "")
            )
            logger.warning(
                "HH test message not sent for candidate %s test %s: %s",
                data.candidate_id,
                data.test_id,
                hh_sync,
            )
    else:
        delivery = "unavailable"
        warning = "Ссылка на тест сохранена, но отправка в HH сейчас недоступна"
        logger.warning(
            "HH test message unavailable for candidate %s test %s",
            data.candidate_id,
            data.test_id,
        )

    return {
        "status": "ok",
        "candidate_id": data.candidate_id,
        "test_id": data.test_id,
        "result_id": result_row.id,
        "created_result": created,
        "test_url": test_url,
        "hh_sync": hh_sync if isinstance(hh_sync, dict) else {"status": "unavailable"},
        "delivery": delivery,
        "warning": warning,
    }
