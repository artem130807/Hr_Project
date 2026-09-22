"""Evaluate a candidate from an HR request payload and enqueue the result outbox."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select

from app.agent.v1.errors import AIGenerationError
from app.app_logging import logger
from app.db.models import OutboxMessage
from app.db.session import get_session_factory
from app.loader import candidate_service, db
from app.messaging.outbox import enqueue_outbox
from app.messaging.rabbit import PermanentHandlerError
from app.schemas.v1.candidates import CandidateEvaluateResponse


EVENT_RESULT = "hr.candidate.evaluate.completed"


def _result_correlation(correlation_id: str) -> str:
    return f"{correlation_id}:result"


def _text(payload: Any, *keys: str) -> str:
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    if not isinstance(payload, dict):
        return ""
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("text")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return ""


def _summary_from_api(row: Any) -> str:
    if row is None:
        return ""
    return _text(row, "text")


async def _result_already_queued(correlation_id: str) -> bool:
    async with get_session_factory()() as session:
        row = (
            await session.execute(
                select(OutboxMessage).where(
                    OutboxMessage.correlation_id == _result_correlation(correlation_id)
                )
            )
        ).scalar_one_or_none()
        return row is not None


async def _enqueue_result(payload: dict[str, Any], extra: dict[str, Any]) -> None:
    correlation_id = str(payload.get("correlation_id") or "").strip()
    out_payload = {
        "event_type": EVENT_RESULT,
        "correlation_id": correlation_id,
        "evaluation_id": payload.get("evaluation_id"),
        "candidate_id": payload.get("candidate_id"),
        "vacancy_id": payload.get("vacancy_id"),
        **extra,
    }
    async with get_session_factory()() as session:
        await enqueue_outbox(
            session,
            event_type=EVENT_RESULT,
            correlation_id=_result_correlation(correlation_id),
            payload=out_payload,
            aggregate_id=str(payload.get("evaluation_id") or payload.get("candidate_id") or ""),
        )
        await session.commit()


async def _load_summaries(payload: dict[str, Any]) -> tuple[str, str, str, str]:
    candidate_text = _text(payload, "candidate_summary")
    vacancy_text = _text(payload, "vacancy_summary")
    company = _text(payload, "company_candidate_image")
    department = _text(payload, "department_candidate_image")

    candidate_id = payload.get("candidate_id")
    vacancy_id = payload.get("vacancy_id")
    department_name = payload.get("department")

    if not candidate_text and candidate_id:
        row = await db.post(f"/candidate/{int(candidate_id)}/summary")
        if row is None:
            raise RuntimeError("candidate summary unavailable")
        candidate_text = _summary_from_api(row)
    if not vacancy_text and vacancy_id:
        row = await db.post(f"/vacancy/{int(vacancy_id)}/summary")
        if row is None:
            raise RuntimeError("vacancy summary unavailable")
        vacancy_text = _summary_from_api(row)
    if not company:
        row = await db.post("/candidate-image/company/summary")
        if row is not None:
            company = _summary_from_api(row)
    if not department and department_name:
        row = await db.post(
            "/candidate-image/department/summary",
            json={"department": department_name},
        )
        if row is not None:
            department = _summary_from_api(row)
    return candidate_text, vacancy_text, company, department


async def handle_evaluate_request(payload: dict[str, Any]) -> Optional[CandidateEvaluateResponse]:
    correlation_id = str(payload.get("correlation_id") or "").strip()
    if not correlation_id:
        raise PermanentHandlerError("correlation_id is required")

    if await _result_already_queued(correlation_id):
        logger.info("Skip OpenAI: result already in outbox correlation_id=%s", correlation_id)
        return None

    try:
        candidate_text, vacancy_text, company, department = await _load_summaries(payload)
        if not candidate_text or not vacancy_text:
            raise ValueError("candidate_summary and vacancy_summary are required")

        result = await candidate_service.evaluate_candidate(
            candidate_text,
            vacancy_text,
            company,
            department,
        )
        if not isinstance(result, CandidateEvaluateResponse):
            raise AIGenerationError("evaluate_candidate returned empty result")
    except (ValueError, AIGenerationError) as exc:
        await _enqueue_result(payload, {"status": "failed", "error": str(exc)[:2000], "score": 0, "comment": ""})
        logger.warning("AI evaluation failed correlation_id=%s: %s", correlation_id, exc)
        return None

    await _enqueue_result(
        payload,
        {
            "status": "completed",
            "score": int(round(float(result.score))),
            "comment": result.comment,
        },
    )
    logger.info("Queued AI evaluation result correlation_id=%s score=%s", correlation_id, result.score)
    return result
