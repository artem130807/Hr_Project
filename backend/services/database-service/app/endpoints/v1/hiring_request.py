from datetime import date, datetime, timezone

from fastapi import APIRouter, Body, HTTPException, Request, Response, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound

from app.db.middleware import get_db
from app.db.v1.models import EmployeeRequest, HiringRequestHistory, Vacancy
from app.db.v1.enums import HiringRequestStatus, Departments
from app.schemas.v1.hiring_request import (
    EmployeeRequestCreate,
    EmployeeRequestRead,
    EmployeeRequestUpdate,
    HiringRequestInviteRead,
    PublicHiringRequestInviteRead,
    PublicHiringRequestSubmitted,
    HiringRequestHistoryRead,
    HiringRequestStatusChange,
)
from app.schemas.v1.vacancies import ReadVacancy
from app.services.hr_lifecycle import vacancy_payload_from_request, vacancy_hh_publish_gaps
from app.utils.tz_helpers import enrich_hiring_request
from app.utils.audit import write_audit
from app.utils.actor import actor_from_headers
from app.app_logging import logger
from app.endpoints.v1.vacancies import _proxy_vacancy_to_hh
from app.adaptation.access import principal_from_claims, require_hr
from app.services.hiring_requests import (
    create_invite,
    create_request_record,
    public_hiring_request_url,
    publish_request_created,
    resolve_invite,
)
from app.utils.utils import get_current_user
import app.config as conf

router = APIRouter()
public_router = APIRouter()

FINAL_REQUEST_STATUSES = {
    HiringRequestStatus.closed,
    HiringRequestStatus.cancelled,
    HiringRequestStatus.completed,
}
REQUEST_STATUS_TRANSITIONS = {
    HiringRequestStatus.created: {HiringRequestStatus.on_analysis, HiringRequestStatus.approved, HiringRequestStatus.returned, HiringRequestStatus.cancelled},
    HiringRequestStatus.on_analysis: {HiringRequestStatus.approved, HiringRequestStatus.returned, HiringRequestStatus.cancelled},
    HiringRequestStatus.returned: {HiringRequestStatus.on_analysis, HiringRequestStatus.cancelled},
    HiringRequestStatus.approved: {HiringRequestStatus.published, HiringRequestStatus.returned, HiringRequestStatus.closed, HiringRequestStatus.cancelled},
    HiringRequestStatus.published: {HiringRequestStatus.closed, HiringRequestStatus.cancelled},
    HiringRequestStatus.closed: set(),
    HiringRequestStatus.cancelled: set(),
    HiringRequestStatus.completed: set(),
}


def _history_value(value):
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


async def _record_request_history(db, req, *, event_type, actor=(None, None), from_status=None, to_status=None, comment=None, changes=None):
    actor_id, actor_name = actor
    row = HiringRequestHistory(
        hiring_request_id=req.id,
        event_type=event_type,
        from_status=_history_value(from_status),
        to_status=_history_value(to_status),
        comment=comment,
        changes=changes,
        actor_id=actor_id,
        actor_name=actor_name,
    )
    db.add(row)
    await db.flush()
    return row


def _to_read(req: EmployeeRequest) -> EmployeeRequestRead:
    return EmployeeRequestRead.model_validate(enrich_hiring_request(req))


@router.get('/hiring-requests', response_model=list[EmployeeRequestRead])
async def list_hiring_requests_endpoint(
    status: HiringRequestStatus = Query(None),
    department: Departments = Query(None),
    db: AsyncSession = Depends(get_db)
):
    query = select(EmployeeRequest)
    if status:
        query = query.where(EmployeeRequest.status == status)
    if department:
        query = query.where(EmployeeRequest.department == department)
    result = await db.execute(query)
    requests = result.scalars().all()
    out: list[EmployeeRequestRead] = []
    for r in requests:
        try:
            out.append(_to_read(r))
        except Exception as exc:
            logger.error(f"Skip hiring request id={getattr(r, 'id', '?')}: {exc}")
    return out


@router.get('/hiring-requests/{request_id}', response_model=EmployeeRequestRead)
async def get_hiring_request_endpoint(
    request_id: int,
    db: AsyncSession = Depends(get_db)
):
    query = select(EmployeeRequest).where(EmployeeRequest.id == request_id)
    result = await db.execute(query)
    request = result.scalar_one_or_none()
    if not request:
        raise HTTPException(404, 'Request not found')
    return _to_read(request)


@router.get('/hiring-requests/{request_id}/history', response_model=list[HiringRequestHistoryRead])
async def get_hiring_request_history_endpoint(request_id: int, db: AsyncSession = Depends(get_db)):
    if not await db.get(EmployeeRequest, request_id):
        raise HTTPException(404, "Hiring request not found")
    result = await db.execute(
        select(HiringRequestHistory)
        .where(HiringRequestHistory.hiring_request_id == request_id)
        .order_by(HiringRequestHistory.created_at.desc(), HiringRequestHistory.id.desc())
    )
    return result.scalars().all()


@router.post('/hiring-requests', response_model=EmployeeRequestRead, status_code=status.HTTP_201_CREATED)
async def post_hiring_request_endpoint(
    data: EmployeeRequestCreate,
    db: AsyncSession = Depends(get_db),
    actor: tuple[str | None, str | None] = Depends(actor_from_headers),
):
    new_request = await create_request_record(db, data)
    await db.commit()
    await db.refresh(new_request)
    actor_id, actor_name = actor
    await publish_request_created(new_request, actor_id=actor_id, actor_name=actor_name)
    return _to_read(new_request)


@router.post('/hiring-request-invites', response_model=HiringRequestInviteRead, status_code=status.HTTP_201_CREATED)
async def create_hiring_request_invite(
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    principal = principal_from_claims(claims)
    require_hr(principal)
    invite, token = await create_invite(
        db,
        actor_id=principal.user_id,
        actor_name=principal.name,
    )
    await write_audit(
        db,
        action="hiring_request.invite.create",
        entity_type="hiring_request_invite",
        entity_id=invite.id,
        details=f"expires_at={invite.expires_at.isoformat()}",
    )
    await db.commit()
    return HiringRequestInviteRead(
        url=public_hiring_request_url(request, token),
        expires_at=invite.expires_at,
    )


@public_router.get('/public/hiring-request-invites/{token}', response_model=PublicHiringRequestInviteRead)
async def get_public_hiring_request_invite(
    token: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    invite = await resolve_invite(db, token)
    return PublicHiringRequestInviteRead(expires_at=invite.expires_at)


@public_router.post(
    '/public/hiring-request-invites/{token}',
    response_model=PublicHiringRequestSubmitted,
    status_code=status.HTTP_201_CREATED,
)
async def submit_public_hiring_request(
    token: str,
    data: EmployeeRequestCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    invite = await resolve_invite(db, token, lock=True)
    # A public invite permits creation, not linking arbitrary internal vacancies.
    data = data.model_copy(update={"linked_vacancy_id": None, "initiator_name": data.manager_name})
    new_request = await create_request_record(
        db,
        data,
        audit_action="hiring_request.public.create",
    )
    invite.used_at = datetime.now(timezone.utc)
    invite.hiring_request_id = new_request.id
    await db.commit()
    await db.refresh(new_request)
    await publish_request_created(
        new_request,
        actor_id=None,
        actor_name=new_request.manager_name,
    )
    return PublicHiringRequestSubmitted(
        id=new_request.id,
        public_code=f"З-{new_request.id}",
        status=new_request.status,
    )


@router.patch('/hiring-requests/{request_id}', response_model=EmployeeRequestRead)
async def update_hiring_request_endpoint(
    request_id: int,
    data: EmployeeRequestUpdate,
    db: AsyncSession = Depends(get_db),
    actor: tuple[str | None, str | None] = Depends(actor_from_headers),
):
    req = await db.get(EmployeeRequest, request_id)
    if not req:
        raise HTTPException(404, "Hiring request not found")
    if req.status in FINAL_REQUEST_STATUSES:
        raise HTTPException(409, "Closed hiring request cannot be edited")

    updates = data.model_dump(exclude_unset=True)
    changes = {
        field: {"from": _history_value(getattr(req, field, None)), "to": _history_value(value)}
        for field, value in updates.items()
        if getattr(req, field, None) != value
    }
    for field, value in updates.items():
        setattr(req, field, value)

    if changes:
        await _record_request_history(db, req, event_type="conditions_updated", actor=actor, changes=changes)

    await write_audit(
        db,
        action="hiring_request.update",
        entity_type="hiring_request",
        entity_id=request_id,
        details=f"fields={list(updates.keys())}",
    )
    await db.commit()
    await db.refresh(req)
    return _to_read(req)


@router.put('/hiring-requests/{request_id}/status', response_model=EmployeeRequestRead)
async def change_status_hiring_request_endpoint(
    request_id: int,
    status: HiringRequestStatus | None = Query(None),
    data: HiringRequestStatusChange | None = Body(None),
    db: AsyncSession = Depends(get_db),
    actor: tuple[str | None, str | None] = Depends(actor_from_headers),
):
    query = select(EmployeeRequest).where(EmployeeRequest.id == request_id)
    result = await db.execute(query)
    try:
        employee_request = result.scalar_one()
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Hiring request not found")

    target = data.status if data else status
    if target is None:
        raise HTTPException(422, "Status is required")
    old = employee_request.status
    if target == old:
        return _to_read(employee_request)
    if target not in REQUEST_STATUS_TRANSITIONS.get(old, set()):
        raise HTTPException(409, f"Недопустимый переход статуса: {old.value} → {target.value}")
    comment = (data.comment or "").strip() if data else ""
    reason = (data.reason or "").strip() if data else ""
    if target == HiringRequestStatus.returned and not comment:
        raise HTTPException(422, "При возврате на уточнение обязателен комментарий")
    if target in {HiringRequestStatus.closed, HiringRequestStatus.cancelled} and not reason:
        raise HTTPException(422, "Укажите основание закрытия или отмены заявки")

    employee_request.status = target
    actor_id, actor_name = actor
    # A manager may resubmit a clarified request. Do not accidentally record
    # that manager as the responsible HR during this transition.
    if target != HiringRequestStatus.on_analysis and not employee_request.assigned_hr_id and actor_id:
        employee_request.assigned_hr_id = actor_id
        employee_request.assigned_hr_name = actor_name
    employee_request.status_changed_at = datetime.now(timezone.utc)
    if target == HiringRequestStatus.returned:
        employee_request.return_comment = comment
    elif target == HiringRequestStatus.closed:
        employee_request.close_reason = reason
    elif target == HiringRequestStatus.cancelled:
        employee_request.cancel_reason = reason
    await _record_request_history(
        db, employee_request, event_type="status_changed", actor=actor,
        from_status=old, to_status=target, comment=comment or reason,
    )
    await write_audit(
        db,
        action="hiring_request.status",
        entity_type="hiring_request",
        entity_id=request_id,
        details=f"{old} → {target}; reason={comment or reason}",
    )
    await db.commit()
    await db.refresh(employee_request)
    return _to_read(employee_request)


@router.post(
    '/hiring-requests/{request_id}/create-vacancy',
    response_model=ReadVacancy,
    status_code=status.HTTP_201_CREATED,
)
async def create_vacancy_from_hiring_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Create local Vacancy from approved hiring request and link both sides."""
    req = await db.get(EmployeeRequest, request_id)
    if not req:
        raise HTTPException(404, "Hiring request not found")
    if req.status in FINAL_REQUEST_STATUSES or req.status == HiringRequestStatus.returned:
        raise HTTPException(409, "Cannot create vacancy from closed request")
    if req.linked_vacancy_id:
        existing = await db.get(Vacancy, req.linked_vacancy_id)
        if existing:
            raise HTTPException(
                409,
                f"Request already linked to vacancy #{req.linked_vacancy_id}",
            )

    payload = vacancy_payload_from_request(req)
    vacancy = Vacancy(**payload)
    db.add(vacancy)
    await db.flush()

    req.linked_vacancy_id = vacancy.id
    if req.status in (HiringRequestStatus.created, HiringRequestStatus.on_analysis):
        old_status = req.status
        req.status = HiringRequestStatus.approved
        req.status_changed_at = datetime.now(timezone.utc)
        await _record_request_history(
            db, req, event_type="status_changed", from_status=old_status,
            to_status=HiringRequestStatus.approved,
            comment=f"Создана связанная вакансия #{vacancy.id}",
        )

    await write_audit(
        db,
        action="hiring_request.create_vacancy",
        entity_type="hiring_request",
        entity_id=request_id,
        details=f"vacancy_id={vacancy.id}",
    )
    await db.commit()
    await db.refresh(vacancy)
    return vacancy


@router.post('/hiring-requests/{request_id}/publish-hh')
async def publish_hiring_request_to_hh(
    request_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Publish linked vacancy to HH.ru and mark request as published."""
    req = await db.get(EmployeeRequest, request_id)
    if not req:
        raise HTTPException(404, "Hiring request not found")
    if req.status in FINAL_REQUEST_STATUSES or req.status == HiringRequestStatus.returned:
        raise HTTPException(409, "Closed hiring request cannot be published to HH")
    if not req.linked_vacancy_id:
        raise HTTPException(
            409,
            "Сначала создайте вакансию из заявки (create-vacancy)",
        )
    vacancy = await db.get(Vacancy, req.linked_vacancy_id)
    if not vacancy:
        raise HTTPException(404, "Linked vacancy not found")
    gaps = vacancy_hh_publish_gaps(vacancy)
    if gaps:
        raise HTTPException(
            400,
            "Перед публикацией на HH.ru откройте вакансию #"
            f"{vacancy.id} и заполните: " + ", ".join(gaps),
        )
    if not conf.HH_SERVICE_URL:
        raise HTTPException(503, "HH service is not configured (HH_SERVICE_INTERNAL)")

    method = "PUT" if vacancy.hh_vacancy_id else "POST"
    try:
        hh_result = await _proxy_vacancy_to_hh(method, vacancy.id, json_body={}, timeout=90.0)
    except HTTPException:
        raise

    await db.refresh(vacancy)
    old_status = req.status
    req.status = HiringRequestStatus.published
    req.status_changed_at = datetime.now(timezone.utc)
    await _record_request_history(
        db, req, event_type="status_changed", from_status=old_status,
        to_status=HiringRequestStatus.published,
        comment=f"Вакансия #{vacancy.id} опубликована на HH.ru",
    )
    await write_audit(
        db,
        action="hiring_request.publish_hh",
        entity_type="hiring_request",
        entity_id=request_id,
        details=f"vacancy_id={vacancy.id} hh_id={vacancy.hh_vacancy_id}",
    )
    await db.commit()
    await db.refresh(req)

    return {
        "status": "ok",
        "hiring_request": _to_read(req),
        "vacancy_id": vacancy.id,
        "hh_vacancy_id": vacancy.hh_vacancy_id,
        "hh_vacancy_url": vacancy.hh_vacancy_url,
        "hh_result": hh_result,
    }


@router.delete('/hiring-requests/{request_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_hiring_request_endpoint(
    request_id: int,
    db: AsyncSession = Depends(get_db)
):
    request = await db.get(EmployeeRequest, request_id)
    if not request:
        raise HTTPException(404, 'Request not found')

    raise HTTPException(
        409,
        "Физическое удаление заявки запрещено. Используйте отмену с обязательным основанием.",
    )
