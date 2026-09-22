from datetime import datetime, time, timedelta, timezone
from hashlib import sha256
import re
import secrets
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adaptation import service as svc
from app.adaptation.access import (
    can_manage_enrollment,
    principal_from_claims,
    redact_checkpoint,
    require_enrollment_access,
    require_hr,
)
from app.adaptation.rules import KIND_LABELS, aware
from app.adaptation.links import public_adaptation_form_path, public_adaptation_form_url
from app.contact_directory import resolve_adaptation_recipient
from app.adaptation.documents import (
    SAFE_DOCUMENT_TYPES,
    build_zip,
    content_hash,
    document_types_for_kind,
    render_document,
    render_filename,
)
from app.app_logging import logger
from app.db.middleware import get_db
from app.schemas.v1.adaptation import (
    AdaptationAnswerIn,
    AdaptationEnrollIn,
    AdaptationExtraIn,
    AdaptationListResponse,
    AdaptationRescheduleIn,
    AdaptationForceCompleteIn,
    AdaptationFinalizeIn,
    AdaptationManagerChangeIn,
    AdaptationActionIn,
    AdaptationActionUpdate,
    AdaptationArchiveIn,
    AdaptationRestartIn,
    TemporaryEmployeeIn,
    TemporaryEmployeeLinkIn,
    AdaptationSettingsUpdate,
    AdaptationTemplateUpdate,
    AdaptationDocumentGenerateIn,
    AdaptationRotateTokenIn,
)
from app.schemas.v1.contact_directory import RoutingPolicyUpdate
from app.messaging.adaptation_events import publish_adaptation_talk_hr
from app.messaging.channel_events import safe_channel_publish
from app.utils.audit import write_audit as _write_audit
from app.utils.utils import get_current_user
from app.db.v1.models import (
    AdaptationCheckpoint,
    AdaptationEnrollment,
    AdaptationModuleSettings,
    AdaptationNotificationDelivery,
    AdaptationNotificationTemplate,
    AdaptationParticipantForm,
    AdaptationReportDocument,
    AdaptationActionRecord,
    Employee,
    TemporaryEmployee,
    ContactPoint,
    AdaptationRoutingDecision,
)

router = APIRouter()
public_router = APIRouter()


async def write_audit(db: AsyncSession, **kwargs):
    """Isolate audit failures from the adaptation business transaction."""
    try:
        async with db.begin_nested():
            return await _write_audit(db, **kwargs)
    except Exception as exc:
        logger.error("Adaptation audit write skipped: %s", exc)
        return None


def _domain_http(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    raise exc


def _reraise_adaptation(exc: Exception, action: str):
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, (LookupError, ValueError)):
        raise _domain_http(exc) from exc
    logger.exception("Adaptation %s failed: %s", action, exc)
    raise HTTPException(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Не удалось выполнить действие адаптации. "
        "Повторите попытку или обратитесь к администратору.",
    ) from exc


def _public_form_query(token: str):
    return (
        select(AdaptationParticipantForm)
        .options(
            selectinload(AdaptationParticipantForm.checkpoint)
            .selectinload(AdaptationCheckpoint.enrollment)
            .selectinload(AdaptationEnrollment.employee),
            selectinload(AdaptationParticipantForm.checkpoint)
            .selectinload(AdaptationCheckpoint.enrollment)
            .selectinload(AdaptationEnrollment.temporary_employee),
            selectinload(AdaptationParticipantForm.checkpoint)
            .selectinload(AdaptationCheckpoint.enrollment)
            .selectinload(AdaptationEnrollment.checkpoints)
            .selectinload(AdaptationCheckpoint.answers),
        )
        .where(AdaptationParticipantForm.token == token)
        # A request owns a fresh session. populate_existing on this cyclic graph
        # reloads checkpoint via enrollment.checkpoints and expires its already
        # loaded enrollment; later attribute access then triggers MissingGreenlet.
    )


@router.get("/adaptation/catalog")
async def get_catalog():
    return svc.catalog_payload()


@router.get("/adaptation/checkpoints", response_model=AdaptationListResponse)
async def list_adaptation_checkpoints(
    year: int | None = Query(None),
    month: int | None = Query(None),
    q: str | None = Query(None),
    department: str | None = Query(None),
    kind: str | None = Query(None),
    risk: str | None = Query(None),
    route: str | None = Query(None),
    outcome: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    hide_completed: bool = Query(False),
    archived: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    today = aware().date()
    y = year or today.year
    m = month or today.month
    if not (1 <= m <= 12) or y < 2000:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Некорректный период")
    try:
        result = await svc.list_checkpoints(
            db,
            year=y,
            month=m,
            q=q,
            department=department,
            kind=kind,
            risk=risk,
            route=route,
            outcome=outcome,
            status=status_filter,
            hide_completed=hide_completed,
            archived=archived,
            page=page,
            page_size=page_size,
        )
        principal = principal_from_claims(claims)
        if not principal.full_access:
            result["items"] = [
                redact_checkpoint(row, principal)
                for row in result["items"]
                if principal.role in {"leader", "manager"}
                and str(row.get("manager_user_id") or "") == principal.user_id
            ]
        return result
    except Exception as exc:
        _reraise_adaptation(exc, "list")


@router.get("/adaptation/checkpoints/{checkpoint_id}")
async def get_adaptation_checkpoint(
    checkpoint_id: int,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    try:
        row = await svc.get_checkpoint_detail(db, checkpoint_id)
        principal = principal_from_claims(claims)
        enrollment = await db.get(AdaptationEnrollment, row["enrollment_id"])
        require_enrollment_access(principal, enrollment)
        return redact_checkpoint(row, principal)
    except Exception as exc:
        _reraise_adaptation(exc, "checkpoint")


@router.post("/adaptation/enrollments", status_code=status.HTTP_201_CREATED)
async def enroll_adaptation(
    data: AdaptationEnrollIn,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    try:
        principal = principal_from_claims(claims)
        require_hr(principal)
        enrollment = await svc.enroll_employee(
            db,
            employee_id=data.employee_id,
            erp_user_id=data.erp_user_id,
            include_control_2m=data.include_control_2m,
            extra_on=data.extra_on,
            route=data.route,
            start_date=data.start_date,
            manager_user_id=data.manager_user_id,
            manager_name=data.manager_name,
            hiring_request_id=data.hiring_request_id,
        )
        try:
            await write_audit(
                db,
                action="adaptation.enroll",
                entity_type="employee",
                entity_id=enrollment.employee_id,
                details=f"enrollment {enrollment.id}",
            )
        except Exception:
            logger.exception("Adaptation enroll audit skipped")
        await db.commit()
    except Exception as exc:
        _reraise_adaptation(exc, "enroll")
    try:
        take = await svc.take_links_for_enrollment(db, enrollment.id)
        await db.commit()
    except Exception:
        logger.exception("Adaptation enroll take-links skipped")
        take = {
            "enrollment_id": enrollment.id,
            "employee_id": enrollment.employee_id,
            "links": [],
        }
    return {
        "id": enrollment.id,
        "employee_id": enrollment.employee_id,
        "full_name": take.get("full_name"),
        "route": take.get("route"),
        "take_links": take.get("links") or [],
    }


@router.post("/adaptation/checkpoints", status_code=status.HTTP_201_CREATED)
async def add_adaptation_checkpoint(
    data: AdaptationExtraIn,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    try:
        require_hr(principal_from_claims(claims))
        from app.adaptation.recurrence import recurrence_dates
        dates = recurrence_dates(
            data.plan_date, data.frequency, data.repeat_count, interval_days=data.interval_days,
        )
        if data.kind != "extra" and len(dates) > 1:
            raise ValueError("Повторение доступно только дополнительным точкам")
        rule = {
            "start": data.plan_date.isoformat(), "frequency": data.frequency,
            "count": data.repeat_count, "interval_days": data.interval_days,
            "include_hr": data.include_hr,
        }
        series_key = data.series_key or secrets.token_urlsafe(24)
        # Serialize retries and creation inside this case, without committing
        # a partially generated series.
        enrollment = await db.get(AdaptationEnrollment, data.enrollment_id, with_for_update=True)
        if not enrollment:
            raise LookupError("Enrollment not found")
        result = await db.execute(select(AdaptationCheckpoint).where(
            AdaptationCheckpoint.enrollment_id == data.enrollment_id,
            AdaptationCheckpoint.series_key == series_key,
        ).order_by(AdaptationCheckpoint.plan_date))
        existing = list(result.scalars().all())
        if existing:
            if existing[0].recurrence_rule != rule or existing[0].kind != data.kind:
                raise HTTPException(409, "Этот ключ серии уже используется с другими параметрами")
            cp = existing[0]
        else:
            for planned in dates:
                created = await svc.add_extra_checkpoint(db, enrollment_id=data.enrollment_id, plan_date=planned, kind=data.kind, include_hr=data.include_hr)
                created.series_key = series_key
                created.recurrence_rule = rule
                if planned == dates[0]:
                    cp = created
        response = {"id": cp.id, "kind": cp.kind, "plan_date": cp.plan_date, "series_key": series_key, "count": len(dates)}
        await write_audit(
            db,
            action="adaptation.checkpoint.add",
            entity_type="adaptation_checkpoint",
            entity_id=cp.id,
            details=data.kind,
        )
        await db.commit()
    except Exception as exc:
        _reraise_adaptation(exc, "checkpoint.add")
    return response


@router.get("/adaptation/enrollments/{enrollment_id}")
async def get_adaptation_enrollment(
    enrollment_id: int,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    try:
        principal = principal_from_claims(claims)
        enrollment = await db.get(AdaptationEnrollment, enrollment_id)
        if not enrollment:
            raise LookupError("Enrollment not found")
        require_enrollment_access(principal, enrollment)
        data = await svc.get_enrollment_detail(db, enrollment_id)
        if not principal.full_access:
            data["checkpoints"] = [redact_checkpoint(row, principal) for row in data["checkpoints"]]
            data.pop("take_links", None)
        return data
    except Exception as exc:
        _reraise_adaptation(exc, "enrollment")


@router.get("/adaptation/enrollments/{enrollment_id}/take-links")
async def get_adaptation_take_links(
    enrollment_id: int,
    include_internal: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    """Return stable participant links; missing forms are repaired idempotently."""
    try:
        enrollment = await db.get(AdaptationEnrollment, enrollment_id)
        if not enrollment:
            raise LookupError("Enrollment not found")
        principal = principal_from_claims(claims)
        require_enrollment_access(principal, enrollment)
        payload = await svc.take_links_for_enrollment(db, enrollment_id)
        visible_roles = ({"employee"} if not include_internal else None) if principal.full_access else {"manager"}
        if visible_roles is not None:
            payload["links"] = [link for link in payload.get("links", []) if link.get("role") in visible_roles]
        await write_audit(
            db,
            action="adaptation.links.view",
            entity_type="adaptation_enrollment",
            entity_id=enrollment.id,
            details="participant links viewed",
        )
        await db.commit()
        return payload
    except Exception as exc:
        _reraise_adaptation(exc, "take-links")


@router.post("/adaptation/forms/{form_id}/rotate-token")
async def rotate_adaptation_form_token(
    form_id: int,
    data: AdaptationRotateTokenIn,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    """Explicitly invalidate the old public token and issue a new one."""
    principal = principal_from_claims(claims)
    require_hr(principal)
    if not data.confirmed:
        raise HTTPException(422, "Необходимо подтвердить перевыпуск ссылки")
    stmt = (
        select(AdaptationParticipantForm)
        .options(selectinload(AdaptationParticipantForm.checkpoint))
        .where(AdaptationParticipantForm.id == form_id)
        .with_for_update()
    )
    form = (await db.execute(stmt)).scalar_one_or_none()
    if not form:
        raise HTTPException(404, "Форма адаптации не найдена")
    enrollment = await db.get(AdaptationEnrollment, form.checkpoint.enrollment_id)
    if not enrollment:
        raise HTTPException(404, "Кейс адаптации не найден")
    if enrollment.archived:
        raise HTTPException(409, "Нельзя перевыпустить ссылку архивного кейса")
    if form.locked or form.submitted_at:
        raise HTTPException(409, "Нельзя перевыпустить ссылку заполненной или заблокированной формы")
    old_token_hash = sha256(form.token.encode("utf-8")).hexdigest()[:16]
    form.token = secrets.token_urlsafe(32)
    form.revoked_at = None
    form.sent_at = None
    await write_audit(
        db,
        action="adaptation.link.rotate",
        entity_type="adaptation_participant_form",
        entity_id=form.id,
        details=f"reason={data.reason}; old_token_hash={old_token_hash}",
    )
    await db.commit()
    await db.refresh(form)
    return {
        "form_id": form.id,
        "token": form.token,
        "path": public_adaptation_form_path(form.token),
        "url": public_adaptation_form_url(form.token),
        "revoked_previous": True,
    }


@router.post("/adaptation/enrollments/{enrollment_id}/resolve-recipient")
async def resolve_adaptation_contact(
    enrollment_id: int,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    """Resolve and journal a recipient without sending any notification."""
    principal = principal_from_claims(claims)
    require_hr(principal)
    enrollment = await db.get(AdaptationEnrollment, enrollment_id)
    if not enrollment:
        raise HTTPException(404, "Кейс адаптации не найден")
    contacts = []
    if enrollment.employee_id:
        contacts = list((await db.execute(select(ContactPoint).where(ContactPoint.employee_id == enrollment.employee_id))).scalars().all())
    settings = (await db.execute(select(AdaptationModuleSettings).order_by(AdaptationModuleSettings.id).limit(1))).scalar_one_or_none()
    global_fallback = bool(getattr(settings, "allow_personal_telegram_fallback", False))
    fallback = enrollment.allow_personal_telegram_fallback if enrollment.allow_personal_telegram_fallback is not None else global_fallback
    resolution = resolve_adaptation_recipient(contacts, allow_personal_fallback=fallback, responsible_hr_user_id=enrollment.responsible_hr_user_id)
    decision = AdaptationRoutingDecision(
        enrollment_id=enrollment.id, employee_id=enrollment.employee_id,
        selected_contact_id=resolution.contact_id,
        resolved_recipient_type=resolution.recipient_type,
        resolved_recipient_user_id=resolution.recipient_user_id,
        reason=resolution.reason,
        policy_snapshot={"allow_personal_telegram_fallback": fallback, "fallback_role": getattr(settings, "fallback_role", "hr") if settings else "hr"},
        status="manual_action_required" if resolution.recipient_type in {"responsible_hr", "hr_role"} else "resolved",
        decided_by=principal.user_id,
    )
    db.add(decision)
    await db.commit()
    await db.refresh(decision)
    return {"id": decision.id, "recipient_type": resolution.recipient_type, "contact_id": resolution.contact_id, "recipient_user_id": resolution.recipient_user_id, "reason": resolution.reason, "status": decision.status, "sent": False}


@router.get("/adaptation/enrollments/{enrollment_id}/routing-decisions")
async def adaptation_routing_decisions(enrollment_id: int, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    principal = principal_from_claims(claims)
    require_hr(principal)
    enrollment = await db.get(AdaptationEnrollment, enrollment_id)
    if not enrollment:
        raise HTTPException(404, "Кейс адаптации не найден")
    rows = list((await db.execute(select(AdaptationRoutingDecision).where(AdaptationRoutingDecision.enrollment_id == enrollment_id).order_by(AdaptationRoutingDecision.id.desc()))).scalars().all())
    return [{"id": row.id, "recipient_type": row.resolved_recipient_type, "contact_id": row.selected_contact_id, "recipient_user_id": row.resolved_recipient_user_id, "reason": row.reason, "status": row.status, "policy_snapshot": row.policy_snapshot, "created_at": row.created_at} for row in rows]


@router.patch("/adaptation/enrollments/{enrollment_id}/routing-policy")
async def update_adaptation_routing_policy(enrollment_id: int, data: RoutingPolicyUpdate, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    principal = principal_from_claims(claims)
    require_hr(principal)
    enrollment = await db.get(AdaptationEnrollment, enrollment_id)
    if not enrollment:
        raise HTTPException(404, "Кейс адаптации не найден")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(enrollment, key, value)
    await write_audit(db, action="adaptation.routing_policy.update", entity_type="adaptation_enrollment", entity_id=enrollment.id, details="routing policy updated")
    await db.commit()
    return {"responsible_hr_user_id": enrollment.responsible_hr_user_id, "responsible_hr_name": enrollment.responsible_hr_name, "allow_personal_telegram_fallback": enrollment.allow_personal_telegram_fallback}


@router.post("/adaptation/checkpoints/{checkpoint_id}/answers")
async def submit_adaptation_answer(
    checkpoint_id: int,
    data: AdaptationAnswerIn,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    answer_payload = data.payload or {}
    should_notify_hr = data.role == "employee" and svc.wants_hr_talk(answer_payload)
    try:
        principal = principal_from_claims(claims)
        if not principal.full_access:
            cp = await db.get(AdaptationCheckpoint, checkpoint_id)
            if not cp:
                raise LookupError("Checkpoint not found")
            enrollment = await db.get(AdaptationEnrollment, cp.enrollment_id)
            if data.role != "manager" or not can_manage_enrollment(principal, enrollment):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Нельзя отправить форму от имени этой роли")
        await svc.submit_answer(
            db,
            checkpoint_id=checkpoint_id,
            role=data.role,
            payload=data.payload,
            actor_user_id=principal.user_id,
            actor_name=principal.name,
        )
        detail = await svc.get_checkpoint_detail(db, checkpoint_id)
        if detail.get("status") == "data_collected":
            try:
                async with db.begin_nested():
                    await _ensure_automatic_draft(db, detail, principal.user_id)
                    detail = await svc.get_checkpoint_detail(db, checkpoint_id)
            except Exception:
                logger.exception("Adaptation auto-draft skipped after answer")
        await write_audit(
            db,
            action="adaptation.answer",
            entity_type="adaptation_checkpoint",
            entity_id=checkpoint_id,
            details=data.role,
        )
        await db.commit()
    except Exception as exc:
        _reraise_adaptation(exc, "answer")
    if should_notify_hr:
        detail_for_notification = dict(detail)
        detail_for_notification["talk_hr_topic"] = next(
            (value for key, value in answer_payload.items() if "talk" in str(key) and str(key).endswith("_topic")),
            None,
        )
        await safe_channel_publish(
            publish_adaptation_talk_hr(detail_for_notification),
            context="adaptation.talk_hr",
        )
    return detail


@router.post("/adaptation/checkpoints/{checkpoint_id}/reschedule")
async def reschedule_adaptation_checkpoint(
    checkpoint_id: int,
    data: AdaptationRescheduleIn,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    principal = principal_from_claims(claims)
    require_hr(principal)
    try:
        cp = await svc.reschedule_checkpoint(
            db,
            checkpoint_id=checkpoint_id,
            plan_date=data.plan_date,
            reason=data.reason,
            actor_user_id=principal.user_id,
        )
        await write_audit(db, action="adaptation.checkpoint.reschedule", entity_type="adaptation_checkpoint", entity_id=checkpoint_id, details=data.reason)
        await db.commit()
        return {"id": cp.id, "plan_date": cp.plan_date, "original_plan_date": cp.original_plan_date}
    except Exception as exc:
        _reraise_adaptation(exc, "checkpoint.reschedule")


@router.post("/adaptation/checkpoints/{checkpoint_id}/force-complete")
async def force_complete_adaptation_checkpoint(
    checkpoint_id: int,
    data: AdaptationForceCompleteIn,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    principal = principal_from_claims(claims)
    require_hr(principal)
    try:
        cp = await svc.force_complete_checkpoint(db, checkpoint_id=checkpoint_id, reason=data.reason, actor_user_id=principal.user_id)
        await write_audit(db, action="adaptation.checkpoint.force_complete", entity_type="adaptation_checkpoint", entity_id=checkpoint_id, details=data.reason)
        await db.commit()
        return {"id": cp.id, "status": "forced_completed", "fact_date": cp.fact_date}
    except Exception as exc:
        _reraise_adaptation(exc, "checkpoint.force_complete")


@router.post("/adaptation/checkpoints/{checkpoint_id}/finalize")
async def finalize_adaptation_checkpoint(
    checkpoint_id: int,
    data: AdaptationFinalizeIn,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    principal = principal_from_claims(claims)
    require_hr(principal)
    try:
        cp = await svc.finalize_checkpoint(db, checkpoint_id=checkpoint_id, outcome=data.outcome, risk=data.risk, comment=data.comment, actor_user_id=principal.user_id)
        detail = await svc.get_checkpoint_detail(db, checkpoint_id)
        version_key = ".".join(
            f"{answer['role']}-{answer.get('version', 1)}"
            for answer in sorted(detail.get("answers") or [], key=lambda item: item["role"])
        )
        await generate_adaptation_documents(
            checkpoint_id,
            AdaptationDocumentGenerateIn(
                formats=["docx", "pdf"],
                final=True,
                idempotency_key=f"final-{checkpoint_id}-{version_key}",
            ),
            db,
            claims,
        )
        await write_audit(db, action="adaptation.checkpoint.finalize", entity_type="adaptation_checkpoint", entity_id=checkpoint_id, details=data.comment)
        await db.commit()
        return {"id": cp.id, "status": "completed", "fact_date": cp.fact_date}
    except Exception as exc:
        _reraise_adaptation(exc, "checkpoint.finalize")


@router.post("/adaptation/enrollments/{enrollment_id}/finalize")
async def finalize_adaptation_enrollment(
    enrollment_id: int,
    data: AdaptationFinalizeIn,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    principal = principal_from_claims(claims)
    require_hr(principal)
    try:
        enrollment = await svc.finalize_enrollment(
            db, enrollment_id=enrollment_id, outcome=data.outcome, risk=data.risk,
            comment=data.comment, actor_user_id=principal.user_id,
            credit_hiring_request=data.credit_hiring_request,
        )
        await write_audit(db, action="adaptation.enrollment.finalize", entity_type="adaptation_enrollment", entity_id=enrollment_id, details=data.comment)
        await db.commit()
        return {"id": enrollment.id, "closed": True, "quota_credited_at": enrollment.quota_credited_at}
    except Exception as exc:
        _reraise_adaptation(exc, "enrollment.finalize")


@router.post("/adaptation/enrollments/{enrollment_id}/manager")
async def change_adaptation_manager(
    enrollment_id: int,
    data: AdaptationManagerChangeIn,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    principal = principal_from_claims(claims)
    require_hr(principal)
    try:
        enrollment = await svc.change_enrollment_manager(db, enrollment_id=enrollment_id, manager_user_id=data.manager_user_id, manager_name=data.manager_name)
        await write_audit(db, action="adaptation.manager.change", entity_type="adaptation_enrollment", entity_id=enrollment_id, details=data.manager_name)
        await db.commit()
        return {"id": enrollment.id, "manager_user_id": enrollment.manager_user_id, "manager_name": enrollment.manager_name}
    except Exception as exc:
        _reraise_adaptation(exc, "manager.change")


@router.post("/adaptation/temporary-employees", status_code=status.HTTP_201_CREATED)
async def create_temporary_adaptation_case(
    data: TemporaryEmployeeIn,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    principal = principal_from_claims(claims)
    require_hr(principal)
    try:
        enrollment = await svc.create_temporary_employee_case(db, **data.model_dump())
        await db.commit()
    except Exception as exc:
        _reraise_adaptation(exc, "temporary.create")
    try:
        take = await svc.take_links_for_enrollment(db, enrollment.id)
        await db.commit()
    except Exception:
        logger.exception("Adaptation temporary take-links skipped")
        take = {"links": []}
    return {
        "id": enrollment.id,
        "temporary_employee_id": enrollment.temporary_employee_id,
        "employee_id": enrollment.employee_id,
        "full_name": take.get("full_name"),
        "take_links": take.get("links") or [],
    }


@router.post("/adaptation/temporary-employees/{temporary_employee_id}/link")
async def link_temporary_adaptation_case(
    temporary_employee_id: int,
    data: TemporaryEmployeeLinkIn,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    principal = principal_from_claims(claims)
    require_hr(principal)
    try:
        enrollment = await svc.link_temporary_employee(db, temporary_employee_id=temporary_employee_id, employee_id=data.employee_id, actor_user_id=principal.user_id)
        await db.commit()
        return {"id": enrollment.id, "employee_id": enrollment.employee_id}
    except Exception as exc:
        _reraise_adaptation(exc, "temporary.link")


def _normalized_match_text(value: str) -> str:
    return re.sub(r"[^a-zа-я0-9]", "", str(value or "").lower().replace("ё", "е"))


@router.get("/adaptation/temporary-employees/{temporary_employee_id}/matches")
async def find_temporary_employee_matches(temporary_employee_id: int, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    temporary = await db.get(TemporaryEmployee, temporary_employee_id)
    if not temporary:
        raise HTTPException(404, "Временная карточка не найдена")
    result = await db.execute(
        select(Employee).where(
            Employee.date_fired.is_(None),
            Employee.date_hired >= temporary.start_date - timedelta(days=14),
            Employee.date_hired <= temporary.start_date + timedelta(days=14),
        )
    )
    expected_name = _normalized_match_text(temporary.full_name)
    expected_position = _normalized_match_text(temporary.position)
    matches = []
    for employee in result.scalars().all():
        score = 0
        if _normalized_match_text(employee.full_name) == expected_name:
            score += 70
        if _normalized_match_text(employee.position) == expected_position:
            score += 20
        if employee.date_hired == temporary.start_date:
            score += 10
        if score >= 70:
            matches.append({
                "employee_id": employee.id, "full_name": employee.full_name,
                "position": employee.position, "department": employee.department,
                "date_hired": employee.date_hired, "score": score,
            })
    return sorted(matches, key=lambda item: (-item["score"], item["employee_id"]))


def _action_payload(row: AdaptationActionRecord) -> dict:
    return {
        "id": row.id,
        "enrollment_id": row.enrollment_id,
        "source_checkpoint_id": row.source_checkpoint_id,
        "action": row.action,
        "owner_user_id": row.owner_user_id,
        "owner_name": row.owner_name,
        "due_date": row.due_date,
        "status": row.status,
        "effect": row.effect,
        "created_at": row.created_at,
    }


@router.get("/adaptation/enrollments/{enrollment_id}/actions")
async def list_adaptation_actions(enrollment_id: int, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    principal = principal_from_claims(claims)
    enrollment = await db.get(AdaptationEnrollment, enrollment_id)
    if not enrollment:
        raise HTTPException(404, "Кейс адаптации не найден")
    require_enrollment_access(principal, enrollment)
    rows = await svc.list_action_records(db, enrollment_id=enrollment_id)
    return [_action_payload(row) for row in rows]


@router.post("/adaptation/enrollments/{enrollment_id}/actions", status_code=status.HTTP_201_CREATED)
async def create_adaptation_action(enrollment_id: int, data: AdaptationActionIn, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    principal = principal_from_claims(claims)
    require_hr(principal)
    row = await svc.add_action_record(db, enrollment_id=enrollment_id, **data.model_dump())
    await write_audit(db, action="adaptation.action.create", entity_type="adaptation_action", entity_id=row.id, details=row.action)
    await db.commit()
    return _action_payload(row)


@router.patch("/adaptation/actions/{action_id}")
async def update_adaptation_action(action_id: int, data: AdaptationActionUpdate, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    row = await svc.update_action_record(db, action_id=action_id, **data.model_dump())
    await db.commit()
    return _action_payload(row)


@router.post("/adaptation/enrollments/{enrollment_id}/archive")
async def archive_adaptation_enrollment(enrollment_id: int, data: AdaptationArchiveIn, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    row = await svc.archive_enrollment(db, enrollment_id=enrollment_id, reason=data.reason)
    await write_audit(db, action="adaptation.enrollment.archive", entity_type="adaptation_enrollment", entity_id=row.id, details=data.reason)
    await db.commit()
    return {"id": row.id, "archived": True, "archive_reason": row.archive_reason}


@router.post("/adaptation/enrollments/{enrollment_id}/restart", status_code=status.HTTP_201_CREATED)
async def restart_adaptation_after_transfer(enrollment_id: int, data: AdaptationRestartIn, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    principal = principal_from_claims(claims)
    require_hr(principal)
    row = await svc.restart_enrollment(
        db,
        enrollment_id=enrollment_id,
        start_date=data.start_date,
        reason=data.reason,
        route=data.route,
        actor_user_id=principal.user_id,
    )
    await write_audit(db, action="adaptation.enrollment.restart", entity_type="adaptation_enrollment", entity_id=row.id, details=data.reason)
    await db.commit()
    return {"id": row.id, "previous_enrollment_id": row.previous_enrollment_id, "start_date": row.start_date}


def _document_payload(row: AdaptationReportDocument) -> dict:
    return {
        "id": row.id,
        "checkpoint_id": row.checkpoint_id,
        "enrollment_id": row.enrollment_id,
        "document_type": row.document_type,
        "format": row.format,
        "version": row.version,
        "file_name": row.file_name,
        "content_sha256": row.content_sha256,
        "is_final": row.is_final,
        "created_at": row.created_at,
    }


def _document_filename_context(detail: dict, document_type: str, version: int) -> dict:
    parts = str(detail.get("full_name") or "Сотрудник").split()
    surname = parts[0] if parts else "Сотрудник"
    first_name = parts[1] if len(parts) > 1 else ""
    initials = "".join(f"{part[0]}." for part in parts[1:3] if part)
    completed = detail.get("fact_date") or detail.get("plan_date")
    return {
        "Фамилия": surname,
        "Имя": first_name,
        "Инициалы": initials,
        "ФИО": detail.get("full_name") or "Сотрудник",
        "Должность": detail.get("position") or "",
        "Этап": detail.get("kind_label") or detail.get("kind") or "",
        "Дата приема": detail.get("date_hired") or "",
        "Дата завершения": completed or "",
        "Месяц": getattr(completed, "month", ""),
        "Год": getattr(completed, "year", ""),
        "ID сотрудника": detail.get("employee_id") or detail.get("temporary_employee_id") or "",
        "Тип": document_type,
        "Версия": version,
    }


def _stable_generation_key(value: str) -> str:
    return value if len(value) <= 80 else f"sha256:{sha256(value.encode('utf-8')).hexdigest()}"


async def _ensure_automatic_draft(db: AsyncSession, detail: dict, actor_user_id: str) -> None:
    """Create the internal slice once for a completed external response set."""
    if "internal_slice" not in document_types_for_kind(detail["kind"], has_hr=True):
        return
    answer_versions = ".".join(
        f"{answer['role']}-{answer.get('version', 1)}"
        for answer in sorted(detail.get("answers") or [], key=lambda item: item["role"])
        if answer["role"] != "hr"
    )
    from app.adaptation.notifications import get_settings

    settings = await get_settings(db)
    for fmt in ("docx", "pdf"):
        generation_key = _stable_generation_key(f"auto-draft:{detail['id']}:{answer_versions}:{fmt}")
        exists = await db.execute(
            select(AdaptationReportDocument.id).where(
                AdaptationReportDocument.generation_key == generation_key
            )
        )
        if exists.scalar_one_or_none() is not None:
            continue
        version_result = await db.execute(
            select(func.max(AdaptationReportDocument.version)).where(
                AdaptationReportDocument.checkpoint_id == detail["id"],
                AdaptationReportDocument.document_type == "internal_slice",
                AdaptationReportDocument.format == fmt,
            )
        )
        version = int(version_result.scalar_one_or_none() or 0) + 1
        binary = render_document(detail, "internal_slice", fmt, settings.signature_roles or [])
        template = (settings.file_name_templates or {}).get("internal_slice") or "{ФИО}_{Этап}_{Тип}_v{Версия}"
        name = render_filename(
            template,
            _document_filename_context(detail, "internal_slice", version),
            extension=fmt,
        )
        db.add(AdaptationReportDocument(
            checkpoint_id=detail["id"], enrollment_id=detail["enrollment_id"],
            document_type="internal_slice", format=fmt, version=version,
            file_name=name, content=binary, content_sha256=content_hash(binary),
            generation_key=generation_key, is_final=False, created_by=actor_user_id,
        ))
    checkpoint = await db.get(AdaptationCheckpoint, detail["id"])
    if checkpoint and not checkpoint.draft_ready_at:
        checkpoint.draft_ready_at = aware()
    await db.flush()


@router.post("/adaptation/checkpoints/{checkpoint_id}/documents", status_code=status.HTTP_201_CREATED)
async def generate_adaptation_documents(checkpoint_id: int, data: AdaptationDocumentGenerateIn, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    principal = principal_from_claims(claims)
    require_hr(principal)
    detail = await svc.get_checkpoint_detail(db, checkpoint_id)
    actions = await svc.list_action_records(db, enrollment_id=detail["enrollment_id"])
    detail["action_records"] = [
        {"action": action.action, "owner": action.owner_name, "due_date": action.due_date,
         "status": action.status, "effect": action.effect}
        for action in actions
    ]
    has_hr = any(item.get("role") == ROLE_HR and item.get("state") != "muted" for item in detail.get("progress") or [])
    allowed = document_types_for_kind(detail["kind"], has_hr=has_hr)
    requested = data.document_types or allowed
    if not requested or any(item not in allowed for item in requested):
        raise HTTPException(422, "Для этого этапа запрошен неподдерживаемый тип документа")
    from app.adaptation.notifications import get_settings

    settings = await get_settings(db)
    created: list[AdaptationReportDocument] = []
    for document_type in requested:
        for fmt in data.formats:
            generation_key = (
                _stable_generation_key(f"{data.idempotency_key}:{checkpoint_id}:{document_type}:{fmt}")
                if data.idempotency_key else None
            )
            if document_type in SAFE_DOCUMENT_TYPES:
                # Old stored binaries may contain the private HR comment.
                source_key = generation_key or secrets.token_urlsafe(24)
                generation_key = "safe2:" + sha256(source_key.encode("utf-8")).hexdigest()
            if generation_key:
                existing = await db.execute(select(AdaptationReportDocument).where(AdaptationReportDocument.generation_key == generation_key))
                existing_row = existing.scalar_one_or_none()
                if existing_row:
                    created.append(existing_row)
                    continue
            version_result = await db.execute(
                select(func.max(AdaptationReportDocument.version)).where(
                    AdaptationReportDocument.checkpoint_id == checkpoint_id,
                    AdaptationReportDocument.document_type == document_type,
                    AdaptationReportDocument.format == fmt,
                )
            )
            version = int(version_result.scalar_one_or_none() or 0) + 1
            binary = render_document(detail, document_type, fmt, settings.signature_roles or [])
            template = (settings.file_name_templates or {}).get(document_type) or "{ФИО}_{Этап}_{Тип}_v{Версия}"
            name = render_filename(
                template,
                _document_filename_context(detail, document_type, version),
                extension=fmt,
            )
            row = AdaptationReportDocument(
                checkpoint_id=checkpoint_id, enrollment_id=detail["enrollment_id"],
                document_type=document_type, format=fmt, version=version,
                file_name=name, content=binary, content_sha256=content_hash(binary),
                generation_key=generation_key, is_final=data.final, created_by=principal.user_id,
            )
            db.add(row)
            await db.flush()
            created.append(row)
    await write_audit(
        db,
        action="adaptation.documents.generate",
        entity_type="adaptation_checkpoint",
        entity_id=checkpoint_id,
        details=f"{len(created)} files; final={data.final}",
    )
    await db.commit()
    return [_document_payload(row) for row in created]


@router.get("/adaptation/enrollments/{enrollment_id}/documents")
async def list_adaptation_documents(enrollment_id: int, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    principal = principal_from_claims(claims)
    enrollment = await db.get(AdaptationEnrollment, enrollment_id)
    if not enrollment:
        raise HTTPException(404, "Кейс адаптации не найден")
    require_enrollment_access(principal, enrollment)
    stmt = select(AdaptationReportDocument).where(AdaptationReportDocument.enrollment_id == enrollment_id)
    if not principal.full_access:
        stmt = stmt.where(AdaptationReportDocument.document_type.in_(SAFE_DOCUMENT_TYPES), AdaptationReportDocument.is_final.is_(True), AdaptationReportDocument.generation_key.like("safe2:%"))
    result = await db.execute(stmt.order_by(AdaptationReportDocument.created_at.desc(), AdaptationReportDocument.id.desc()))
    return [_document_payload(row) for row in result.scalars().all()]


async def _authorized_document(document_id: int, db: AsyncSession, claims) -> AdaptationReportDocument:
    row = await db.get(AdaptationReportDocument, document_id)
    if not row:
        raise HTTPException(404, "Документ не найден")
    enrollment = await db.get(AdaptationEnrollment, row.enrollment_id)
    principal = principal_from_claims(claims)
    require_enrollment_access(principal, enrollment)
    if not principal.full_access and row.document_type not in SAFE_DOCUMENT_TYPES:
        raise HTTPException(403, "Документ содержит конфиденциальные ответы")
    if not principal.full_access and (not row.is_final or not (row.generation_key or "").startswith("safe2:")):
        raise HTTPException(403, "HR должен сформировать новую безопасную финальную версию")
    return row


@router.get("/adaptation/documents/{document_id}/download")
async def download_adaptation_document(document_id: int, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    row = await _authorized_document(document_id, db, claims)
    await write_audit(db, action="adaptation.document.download", entity_type="adaptation_document", entity_id=row.id, details=row.file_name)
    await db.commit()
    media = "application/pdf" if row.format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return Response(row.content, media_type=media, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(row.file_name)}"})


@router.get("/adaptation/enrollments/{enrollment_id}/documents.zip")
async def download_adaptation_documents_zip(enrollment_id: int, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    principal = principal_from_claims(claims)
    enrollment = await db.get(AdaptationEnrollment, enrollment_id)
    if not enrollment:
        raise HTTPException(404, "Кейс адаптации не найден")
    require_enrollment_access(principal, enrollment)
    stmt = select(AdaptationReportDocument).where(AdaptationReportDocument.enrollment_id == enrollment_id)
    if not principal.full_access:
        raise HTTPException(403, "Полный ZIP доступен только HR")
    result = await db.execute(stmt.order_by(AdaptationReportDocument.id))
    rows = list(result.scalars().all())
    content = build_zip((row.file_name, row.content) for row in rows)
    await write_audit(db, action="adaptation.documents.zip", entity_type="adaptation_enrollment", entity_id=enrollment_id, details=f"{len(rows)} files")
    await db.commit()
    return Response(content, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename=adaptation_{enrollment_id}.zip"})


@router.delete("/adaptation/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_adaptation_document_version(document_id: int, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    row = await _authorized_document(document_id, db, claims)
    bounds = await db.execute(
        select(
            func.min(AdaptationReportDocument.version),
            func.max(AdaptationReportDocument.version),
        ).where(
            AdaptationReportDocument.checkpoint_id == row.checkpoint_id,
            AdaptationReportDocument.document_type == row.document_type,
            AdaptationReportDocument.format == row.format,
        )
    )
    first_version, last_version = bounds.one()
    if row.version in {first_version, last_version}:
        raise HTTPException(409, "Первую и последнюю версии удалять нельзя")
    await db.delete(row)
    await write_audit(db, action="adaptation.document.delete", entity_type="adaptation_document", entity_id=document_id, details=row.file_name)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/adaptation/reports")
async def adaptation_reports(
    enrollment_id: int | None = Query(None),
    year: int | None = Query(None),
    month: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    today = aware().date()
    try:
        principal = principal_from_claims(claims)
        if enrollment_id:
            enrollment = await db.get(AdaptationEnrollment, enrollment_id)
            if not enrollment:
                raise LookupError("Enrollment not found")
            require_enrollment_access(principal, enrollment)
            reports = await svc.reports_for_enrollment(db, enrollment_id)
            if not principal.full_access:
                return {"manager_safe": reports.get("manager_safe", []), "probation": reports.get("probation")}
            return reports
        require_hr(principal)
        return await svc.reports_for_period(
            db, year=year or today.year, month=month or today.month
        )
    except Exception as exc:
        _reraise_adaptation(exc, "reports")


@router.get("/adaptation/settings")
async def get_adaptation_settings(db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    from app.adaptation.notifications import get_settings

    row = await get_settings(db)
    return {
        "overdue_enabled": row.overdue_enabled,
        "overdue_time": row.overdue_time.strftime("%H:%M"),
        "timezone": row.timezone,
        "visible_columns": row.visible_columns,
        "show_photo": row.show_photo,
        "file_name_templates": row.file_name_templates,
        "signature_roles": row.signature_roles,
        "risk_rules": row.risk_rules,
        "allow_personal_telegram_fallback": row.allow_personal_telegram_fallback,
        "fallback_role": row.fallback_role,
        "manual_share_confirmation_hours": row.manual_share_confirmation_hours,
    }


@router.put("/adaptation/settings")
async def update_adaptation_settings(data: AdaptationSettingsUpdate, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    from app.adaptation.notifications import get_settings

    row = await get_settings(db)
    values = data.model_dump(exclude_unset=True)
    if "overdue_time" in values:
        try:
            hh, mm = values.pop("overdue_time").split(":", 1)
            row.overdue_time = time(int(hh), int(mm))
        except (ValueError, TypeError):
            raise HTTPException(422, "Время должно быть в формате HH:MM") from None
    for key, value in values.items():
        if key == "timezone":
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError, TypeError):
                raise HTTPException(422, "Неизвестный часовой пояс") from None
        if key == "visible_columns" and any(item not in {"position", "progress", "risk"} for item in value):
            raise HTTPException(422, "Некорректный список колонок")
        setattr(row, key, value)
    await db.commit()
    return await get_adaptation_settings(db, claims)


@router.get("/adaptation/notification-templates")
async def list_adaptation_templates(db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    from app.adaptation.notifications import ensure_default_templates

    await ensure_default_templates(db)
    await db.commit()
    result = await db.execute(select(AdaptationNotificationTemplate).order_by(AdaptationNotificationTemplate.audience, AdaptationNotificationTemplate.event))
    return [{"id": row.id, "audience": row.audience, "event": row.event, "text": row.text, "enabled": row.enabled} for row in result.scalars().all()]


@router.put("/adaptation/notification-templates/{audience}/{event}")
async def update_adaptation_template(audience: str, event: str, data: AdaptationTemplateUpdate, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    result = await db.execute(select(AdaptationNotificationTemplate).where(AdaptationNotificationTemplate.audience == audience, AdaptationNotificationTemplate.event == event))
    row = result.scalar_one_or_none()
    if row is None:
        row = AdaptationNotificationTemplate(audience=audience, event=event, text=data.text, enabled=data.enabled)
        db.add(row)
    else:
        row.text = data.text
        row.enabled = data.enabled
    await db.commit()
    return {"audience": audience, "event": event, "text": row.text, "enabled": row.enabled}


@router.get("/adaptation/notification-errors")
async def list_adaptation_notification_errors(db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    result = await db.execute(select(AdaptationNotificationDelivery).where(AdaptationNotificationDelivery.status == "failed").order_by(AdaptationNotificationDelivery.scheduled_at.desc()).limit(200))
    return [{"id": row.id, "checkpoint_id": row.checkpoint_id, "role": row.role, "event": row.event, "attempts": row.attempts, "last_error": row.last_error} for row in result.scalars().all()]


@router.post("/adaptation/notification-errors/{delivery_id}/retry")
async def retry_adaptation_notification(delivery_id: int, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    row = await db.get(AdaptationNotificationDelivery, delivery_id)
    if not row:
        raise HTTPException(404, "Уведомление не найдено")
    row.status = "pending"
    row.attempts = 0
    row.scheduled_at = aware(datetime.now(timezone.utc))
    row.last_error = None
    await db.commit()
    return {"id": row.id, "status": row.status}


@public_router.get("/public/adaptation/forms/{token}")
async def get_public_adaptation_form(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(_public_form_query(token))
    form = result.scalar_one_or_none()
    if (
        not form
        or form.revoked_at
        or form.checkpoint.closed
        or form.checkpoint.enrollment.closed
        or form.checkpoint.enrollment.archived
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ссылка недействительна")
    cp = form.checkpoint
    enrollment = cp.enrollment
    employee = enrollment.employee or enrollment.temporary_employee
    return {
        "checkpoint_id": cp.id,
        "enrollment_id": enrollment.id,
        "employee_id": enrollment.employee_id,
        "temporary_employee_id": enrollment.temporary_employee_id,
        "full_name": getattr(employee, "full_name", None),
        "role": form.role,
        "title": svc.form_public_title(cp.kind, form.role),
        "questions": svc.form_for(cp.kind, form.role),
        "plan_date": cp.plan_date,
        "kind": cp.kind,
        "kind_label": KIND_LABELS.get(cp.kind, cp.kind),
        "locked": bool(form.locked and not cp.forced_completed_at),
        "late_answer": bool(cp.forced_completed_at),
        "core_history": svc.core_history_from_checkpoint(cp),
    }


@public_router.post("/public/adaptation/forms/{token}")
async def submit_public_adaptation_form(
    token: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(_public_form_query(token))
    form = result.scalar_one_or_none()
    if (
        not form
        or form.revoked_at
        or form.checkpoint.closed
        or form.checkpoint.enrollment.closed
        or form.checkpoint.enrollment.archived
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ссылка недействительна")
    if form.locked and not form.checkpoint.forced_completed_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ответы уже отправлены")
    # Commit expires ORM attributes in production. Cache everything needed by
    # the response before committing to avoid an async lazy-load afterwards.
    checkpoint_id = form.checkpoint_id
    participant_role = form.role
    participant_user_id = form.participant_user_id
    forced_completed = bool(form.checkpoint.forced_completed_at)
    payload = data.get("payload") if isinstance(data, dict) else None
    if not isinstance(payload, dict):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Некорректные ответы")
    try:
        await svc.submit_answer(
            db,
            checkpoint_id=checkpoint_id,
            role=participant_role,
            payload=payload,
            actor_user_id=participant_user_id,
            actor_name="public-link",
        )
        detail = await svc.get_checkpoint_detail(db, checkpoint_id)
        if detail.get("status") == "data_collected":
            try:
                async with db.begin_nested():
                    await _ensure_automatic_draft(db, detail, participant_user_id or "public-link")
                    detail = await svc.get_checkpoint_detail(db, checkpoint_id)
            except Exception:
                logger.exception("Adaptation auto-draft skipped after public answer")
        await db.commit()
        if participant_role == "employee" and svc.wants_hr_talk(payload):
            detail_for_notification = dict(detail)
            detail_for_notification["talk_hr_topic"] = next(
                (value for key, value in payload.items() if "talk" in str(key) and str(key).endswith("_topic")),
                None,
            )
            await safe_channel_publish(
                publish_adaptation_talk_hr(detail_for_notification),
                context="adaptation.public.talk_hr",
            )
        return {"submitted": True, "locked": not forced_completed}
    except Exception as exc:
        _reraise_adaptation(exc, "public.answer")
