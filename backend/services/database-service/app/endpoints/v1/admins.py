"""Admin/HR directory — proxied from ERP (no local web_admin_panel_users)."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.middleware import get_db
from app.db.v1.models import HrNegotiationFlag
from app.erp.client import ErpClient
from app.erp.mapper import map_erp_user, map_role
from app.schemas.v1.admins import (
    AdminUserCreate,
    AdminUserCreateResponse,
    AdminUserRead,
    AdminUserUpdate,
    ErpRoleRead,
    ResponsibleForNegotiations,
)
from app.app_logging import logger
from app.config import ERP_BASE
from app.services.employee_start_date_sync import (
    apply_erp_date_to_hr_employee,
    find_hr_employee_by_erp_id,
    reschedule_active_adaptation_for_start_date,
)
from app.utils.audit import write_audit


router = APIRouter()
_oauth2 = OAuth2PasswordBearer(tokenUrl="/v1/token/user", auto_error=False)


def _to_admin_read(mapped: dict, flags: dict[str, bool]) -> dict:
    erp_id = mapped["erp_user_id"]
    return {
        "id": erp_id,
        "username": mapped["username"],
        "full_name": mapped.get("full_name"),
        "role": mapped["role"],
        "department": mapped.get("department"),
        "position": mapped.get("position") or mapped.get("department"),
        "user_id": None,
        "negotations_processing": flags.get(erp_id, False),
        "erp_user_id": erp_id,
        "date_hired": mapped.get("date_hired"),
        "created_at": None,
        "updated_at": None,
    }


async def _negotiation_flags(db: AsyncSession) -> dict[str, bool]:
    flag_rows = (await db.execute(select(HrNegotiationFlag))).scalars().all()
    return {r.erp_user_id: bool(r.negotations_processing) for r in flag_rows}


async def _list_erp_admins(
    db: AsyncSession,
    *,
    role: Optional[str] = None,
) -> list[dict]:
    if not ERP_BASE:
        raise HTTPException(503, "ERP_BASE is not configured")
    try:
        raw_users = await ErpClient().list_users()
    except Exception as exc:
        logger.exception(f"ERP users list failed: {exc}")
        raise HTTPException(502, f"Failed to load users from ERP: {exc}") from exc

    flags = await _negotiation_flags(db)

    items: list[dict] = []
    for raw in raw_users:
        mapped = map_erp_user(raw)
        if not mapped:
            continue
        if role and mapped["role"] != str(role).strip().lower():
            continue
        items.append(_to_admin_read(mapped, flags))
    return items


def _bearer_from_request(request: Request, token: Optional[str] = None) -> Optional[str]:
    if token:
        return token
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def _normalize_email(username: str) -> str:
    email = (username or "").strip().lower()
    if not email:
        raise HTTPException(400, "Укажите email (логин)")
    if "@" not in email:
        raise HTTPException(
            400,
            "Логин должен быть email (например user@company.com) — так создаётся учётка в ERP",
        )
    return email[:200]


@router.get("/admin/users", response_model=list[AdminUserRead])
async def list_admin_users_endpoint(
    role: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await _list_erp_admins(db, role=role)


@router.get("/admin/roles", response_model=list[ErpRoleRead])
async def list_admin_roles_endpoint(
    request: Request,
    token: Annotated[Optional[str], Depends(_oauth2)] = None,
):
    """ERP roles for the panel create-user form."""
    if not ERP_BASE:
        raise HTTPException(503, "ERP_BASE is not configured")
    access = _bearer_from_request(request, token)
    try:
        raw_roles = await ErpClient().list_roles(access_token=access)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"ERP roles list failed: {exc}")
        raise HTTPException(502, f"Failed to load roles from ERP: {exc}") from exc

    out: list[dict] = []
    for raw in raw_roles:
        rid = raw.get("id")
        if rid is None:
            continue
        out.append(
            {
                "id": int(rid),
                "name": raw.get("name"),
                "role": map_role(raw),
            }
        )
    return out


@router.get("/admin/user/{admin_id}", response_model=AdminUserRead)
async def get_admin_user_endpoint(admin_id: str, db: AsyncSession = Depends(get_db)):
    users = await _list_erp_admins(db)
    for u in users:
        if str(u.get("id")) == str(admin_id) or str(u.get("erp_user_id")) == str(admin_id):
            return u
    raise HTTPException(404, "Admin user not found in ERP")


@router.post(
    "/admin/user",
    response_model=AdminUserCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_admin_user_endpoint(
    body: AdminUserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: Annotated[Optional[str], Depends(_oauth2)] = None,
):
    """Create panel user in ERP (proxied POST /api/v2/users/)."""
    if not ERP_BASE:
        raise HTTPException(503, "ERP_BASE is not configured")

    access = _bearer_from_request(request, token)
    email = _normalize_email(body.username)
    full_name = (body.full_name or "").strip() or email.split("@")[0]
    client = ErpClient()

    role_id = await client.resolve_role_id(body.role, access_token=access)
    if role_id is None and body.role:
        raise HTTPException(
            400,
            f"Роль «{body.role}» не найдена в ERP. Выберите роль из списка ERP.",
        )

    payload: dict = {
        "name": full_name[:200],
        "email": email,
        "is_active": True,
    }
    if role_id is not None:
        payload["role_id"] = role_id
    if body.plain_password:
        payload["password"] = body.plain_password
    if body.date_hired is not None:
        payload["date_hired"] = body.date_hired.isoformat()

    try:
        result = await client.create_user(payload, access_token=access)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"ERP create user failed: {exc}")
        raise HTTPException(502, f"Failed to create user in ERP: {exc}") from exc

    raw_user = result.get("user") if isinstance(result.get("user"), dict) else result
    if not isinstance(raw_user, dict):
        raise HTTPException(502, "ERP create user returned no user object")

    mapped = map_erp_user(raw_user)
    if not mapped:
        erp_id = str(raw_user.get("id") or "")
        if not erp_id:
            raise HTTPException(502, "ERP create user returned user without id")
        mapped = {
            "erp_user_id": erp_id[:36],
            "username": email,
            "full_name": full_name[:200],
            "role": (body.role or "dev").lower(),
            "department": body.department,
            "date_hired": body.date_hired,
        }

    flags = await _negotiation_flags(db)
    user_read = _to_admin_read(mapped, flags)
    if body.department:
        user_read["department"] = body.department

    generated = result.get("password") if not body.plain_password else None
    return {"user": user_read, "password": generated}


@router.patch("/admin/user/{admin_id}", response_model=AdminUserRead)
async def update_admin_user_endpoint(
    admin_id: str,
    body: AdminUserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: Annotated[Optional[str], Depends(_oauth2)] = None,
):
    """Update panel user in ERP (proxied PUT /api/v2/users/{id})."""
    if not ERP_BASE:
        raise HTTPException(503, "ERP_BASE is not configured")

    access = _bearer_from_request(request, token)
    client = ErpClient()
    erp_payload: dict = {}
    linked_employee = None

    if body.full_name is not None:
        name = (body.full_name or "").strip()
        if name:
            erp_payload["name"] = name[:200]
    if body.username is not None:
        erp_payload["email"] = _normalize_email(body.username)
    if body.role is not None and str(body.role).strip():
        role_id = await client.resolve_role_id(body.role, access_token=access)
        if role_id is None:
            raise HTTPException(
                400,
                f"Роль «{body.role}» не найдена в ERP. Выберите роль из списка ERP.",
            )
        erp_payload["role_id"] = role_id
    if "date_hired" in body.model_fields_set:
        erp_payload["date_hired"] = body.date_hired.isoformat() if body.date_hired else None
        linked_employee = await find_hr_employee_by_erp_id(db, admin_id)
        if linked_employee is not None:
            if body.date_hired is None:
                raise HTTPException(422, "Дата выхода на работу обязательна для сотрудника HR-платформы")
            else:
                try:
                    # Validate before the remote write so a local invariant cannot
                    # leave ERP and HR with different dates.
                    from app.services.employee_start_date_sync import validate_start_date
                    validate_start_date(linked_employee, body.date_hired)
                except ValueError as exc:
                    raise HTTPException(422, str(exc)) from exc

    if not erp_payload:
        # Nothing to send to ERP — return current snapshot (department-only no-ops).
        return await get_admin_user_endpoint(admin_id, db)

    linked_changed = False
    if linked_employee is not None and body.date_hired is not None:
        try:
            linked_changed = await apply_erp_date_to_hr_employee(db, linked_employee, body.date_hired)
            if linked_changed:
                points_changed = await reschedule_active_adaptation_for_start_date(
                    db,
                    employee_id=linked_employee.id,
                    value=body.date_hired,
                )
                await write_audit(
                    db,
                    action="employee.date_hired.sync_from_erp",
                    entity_type="employee",
                    entity_id=linked_employee.id,
                    details=(
                        f"erp_user_id={admin_id}; date_hired={body.date_hired.isoformat()}; "
                        f"adaptation_points_rescheduled={points_changed}"
                    ),
                )
                # Detect local constraint problems before writing to ERP.
                await db.flush()
        except Exception as exc:
            await db.rollback()
            logger.exception(f"HR employee start-date validation failed: {exc}")
            raise HTTPException(500, "Не удалось сохранить дату выхода в HR-платформе") from exc

    try:
        raw_user = await client.update_user(admin_id, erp_payload, access_token=access)
    except HTTPException:
        if linked_changed:
            await db.rollback()
        raise
    except Exception as exc:
        if linked_changed:
            await db.rollback()
        logger.exception(f"ERP update user failed: {exc}")
        raise HTTPException(502, f"Failed to update user in ERP: {exc}") from exc

    mapped = map_erp_user(raw_user)
    if not mapped:
        raise HTTPException(
            502,
            "ERP обновил пользователя, но запись недоступна в списке панели "
            "(неактивен или роль не сопоставлена).",
        )
    if "date_hired" in body.model_fields_set and mapped.get("date_hired") is None:
        # ERP may omit nullable fields in its update response.
        mapped["date_hired"] = body.date_hired

    if linked_changed:
        try:
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.exception(f"HR employee start-date sync failed after ERP update: {exc}")
            raise HTTPException(
                500,
                "Дата сохранена в ERP, но не сохранена в HR-платформе. "
                "Повторите операцию после проверки связи сотрудника.",
            ) from exc

    flags = await _negotiation_flags(db)
    user_read = _to_admin_read(mapped, flags)
    if body.department is not None:
        user_read["department"] = body.department
    return user_read


@router.post("/admin/user/{admin_id}/reset-password")
async def reset_admin_user_password_endpoint(
    admin_id: str,
    request: Request,
    token: Annotated[Optional[str], Depends(_oauth2)] = None,
):
    """Reset password in ERP; returns generated password."""
    if not ERP_BASE:
        raise HTTPException(503, "ERP_BASE is not configured")
    access = _bearer_from_request(request, token)
    try:
        result = await ErpClient().reset_user_password(admin_id, access_token=access)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"ERP reset password failed: {exc}")
        raise HTTPException(502, f"Failed to reset password in ERP: {exc}") from exc
    password = result.get("password")
    if not password:
        raise HTTPException(502, "ERP reset password returned no password")
    return {"status": "ok", "password": password}


@router.delete("/admin/user/{admin_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def delete_admin_user_endpoint(admin_id: str):
    raise HTTPException(
        501,
        "Удаление пользователей перенесено в ERP. Используйте erp-backend.",
    )


@router.post("/admin/users/erp-sync", status_code=status.HTTP_410_GONE)
@router.post("/admin/users/erp-sync/run", status_code=status.HTTP_410_GONE)
async def sync_erp_users_gone():
    raise HTTPException(
        410,
        "Локальный sync пользователей удалён: HR читает пользователей напрямую из ERP.",
    )


async def _set_negotiation_flag(
    admin_id: str,
    responsible: bool,
    db: AsyncSession,
) -> dict:
    row = await db.get(HrNegotiationFlag, admin_id)
    if row is None:
        row = HrNegotiationFlag(erp_user_id=admin_id, negotations_processing=responsible)
        db.add(row)
    else:
        row.negotations_processing = responsible
    if responsible:
        others = (
            await db.execute(
                select(HrNegotiationFlag).where(
                    HrNegotiationFlag.erp_user_id != admin_id,
                    HrNegotiationFlag.negotations_processing.is_(True),
                )
            )
        ).scalars().all()
        for o in others:
            o.negotations_processing = False
    await db.commit()
    return await get_admin_user_endpoint(admin_id, db)


@router.put("/admin/hr/{admin_id}/negotation-processing", response_model=AdminUserRead)
@router.put("/admin/hr/{admin_id}/negotiation-processing", response_model=AdminUserRead)
async def set_hr_negotiation_processing(
    admin_id: str,
    body: ResponsibleForNegotiations,
    db: AsyncSession = Depends(get_db),
):
    return await _set_negotiation_flag(admin_id, bool(body.responsible_of_negotiations), db)


@router.get("/admin/hr/responsible-of-negotiations", response_model=Optional[AdminUserRead])
async def get_hr_responsible_of_negotiations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(HrNegotiationFlag).where(HrNegotiationFlag.negotations_processing.is_(True))
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    try:
        return await get_admin_user_endpoint(row.erp_user_id, db)
    except HTTPException:
        return {
            "id": row.erp_user_id,
            "username": row.erp_user_id,
            "full_name": None,
            "role": map_role("hr") or "hr",
            "department": None,
            "user_id": None,
            "negotations_processing": True,
            "erp_user_id": row.erp_user_id,
            "created_at": None,
            "updated_at": None,
        }
