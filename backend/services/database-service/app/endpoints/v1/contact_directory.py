from __future__ import annotations

from hashlib import sha1

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.adaptation.access import principal_from_claims, require_hr
from app.contact_directory import clear_other_primary, ensure_contact_available, normalize_contact
from app.db.middleware import get_db
from app.db.v1.models import ContactPoint, Employee, OrganizationDepartment
from app.schemas.v1.contact_directory import ContactPointIn, ContactPointRead, ContactPointUpdate, DepartmentIn
from app.utils.audit import write_audit
from app.utils.utils import get_current_user

router = APIRouter()


def _actor(claims) -> str | None:
    value = principal_from_claims(claims).user_id
    return value or None


async def _department_or_404(db, department_id: int):
    row = await db.get(OrganizationDepartment, department_id)
    if not row:
        raise HTTPException(404, "Отдел не найден")
    return row


async def _create_contact(db, *, data: ContactPointIn, owner_type: str, employee_id=None, department_id=None, actor_id=None):
    if owner_type == "department" and data.usage_type != "shared":
        raise HTTPException(422, "Контакт отдела должен быть общим")
    if owner_type == "department" and (data.is_primary or data.allow_adaptation):
        raise HTTPException(422, "Общий контакт отдела нельзя назначить основным или использовать для персональной адаптации")
    if owner_type == "employee" and data.usage_type == "shared":
        raise HTTPException(422, "Общий контакт необходимо закрепить за отделом")
    normalized = normalize_contact(data.contact_type, data.value)
    await ensure_contact_available(db, contact_type=data.contact_type, normalized=normalized, usage_type=data.usage_type)
    row = ContactPoint(
        **data.model_dump(), normalized_value=normalized, owner_type=owner_type,
        employee_id=employee_id, department_id=department_id,
        created_by=actor_id, updated_by=actor_id,
    )
    if data.contact_type == "telegram" and not row.telegram_username:
        row.telegram_username = normalized
    db.add(row)
    try:
        await db.flush()
        await clear_other_primary(db, row)
        await write_audit(db, action="contact.create", entity_type="contact_point", entity_id=row.id, details=f"{data.contact_type}:{owner_type}")
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Контакт уже используется или нарушает правила принадлежности") from exc
    await db.refresh(row)
    return row


@router.get("/employees/{employee_id}/contacts", response_model=list[ContactPointRead])
async def employee_contacts(employee_id: int, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    if not await db.get(Employee, employee_id):
        raise HTTPException(404, "Сотрудник не найден")
    result = await db.execute(select(ContactPoint).where(ContactPoint.employee_id == employee_id).order_by(ContactPoint.is_active.desc(), ContactPoint.contact_type, ContactPoint.priority, ContactPoint.id))
    return result.scalars().all()


@router.post("/employees/{employee_id}/contacts", response_model=ContactPointRead, status_code=status.HTTP_201_CREATED)
async def create_employee_contact(employee_id: int, data: ContactPointIn, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    if not await db.get(Employee, employee_id):
        raise HTTPException(404, "Сотрудник не найден")
    try:
        return await _create_contact(db, data=data, owner_type="employee", employee_id=employee_id, actor_id=_actor(claims))
    except ValueError as exc:
        raise HTTPException(409 if "закреплён" in str(exc) or "используется" in str(exc) else 422, str(exc)) from exc


@router.patch("/contacts/{contact_id}", response_model=ContactPointRead)
async def update_contact(contact_id: int, data: ContactPointUpdate, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    row = await db.get(ContactPoint, contact_id)
    if not row:
        raise HTTPException(404, "Контакт не найден")
    values = data.model_dump(exclude_unset=True)
    next_usage = values.get("usage_type", row.usage_type)
    if row.owner_type == "department" and next_usage != "shared":
        raise HTTPException(422, "Контакт отдела должен быть общим")
    if row.owner_type == "department" and (values.get("is_primary") or values.get("allow_adaptation")):
        raise HTTPException(422, "Общий контакт отдела нельзя назначить основным или использовать для персональной адаптации")
    if row.owner_type == "employee" and next_usage == "shared":
        raise HTTPException(422, "Общий контакт необходимо закрепить за отделом")
    if row.contact_type != "telegram" and any(values.get(key) is not None for key in ("telegram_chat_id", "telegram_username")):
        raise HTTPException(422, "Telegram-поля разрешены только для Telegram-контакта")
    if row.contact_type != "telegram" and values.get("allow_adaptation"):
        raise HTTPException(422, "Адаптация разрешена только для Telegram")
    normalized = row.normalized_value
    if "value" in values:
        normalized = normalize_contact(row.contact_type, values["value"])
        row.normalized_value = normalized
        if row.contact_type == "telegram" and "telegram_username" not in values:
            row.telegram_username = normalized
    if "value" in values or "usage_type" in values or values.get("is_active") is True:
        try:
            await ensure_contact_available(db, contact_type=row.contact_type, normalized=normalized, usage_type=next_usage, exclude_id=row.id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
    for key, value in values.items():
        setattr(row, key, value)
    row.updated_by = _actor(claims)
    await clear_other_primary(db, row)
    await write_audit(db, action="contact.update", entity_type="contact_point", entity_id=row.id, details=f"fields:{','.join(values)}")
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Контакт уже используется или основной контакт этого типа уже выбран") from exc
    await db.refresh(row)
    return row


@router.delete("/contacts/{contact_id}", status_code=204)
async def deactivate_contact(contact_id: int, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    row = await db.get(ContactPoint, contact_id)
    if not row:
        raise HTTPException(404, "Контакт не найден")
    row.is_active = False
    row.is_primary = False
    row.updated_by = _actor(claims)
    await write_audit(db, action="contact.deactivate", entity_type="contact_point", entity_id=row.id, details="deactivated")
    await db.commit()


@router.get("/organization/departments")
async def list_departments(db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    # Local employee departments are materialized lazily without mutating ERP.
    names = list((await db.execute(select(Employee.department).where(Employee.date_fired.is_(None)).distinct())).scalars().all())
    existing = {row.name: row for row in (await db.execute(select(OrganizationDepartment))).scalars().all()}
    used_codes = {row.code for row in existing.values()}
    for raw_name in filter(None, names):
        name = str(raw_name).strip()
        if not name or name in existing:
            continue
        code = "-".join(name.lower().split())[:100]
        if not code or code in used_codes:
            suffix = sha1(name.encode("utf-8")).hexdigest()[:8]
            code = f"{code[:91] or 'department'}-{suffix}"
        if name not in existing:
            row = OrganizationDepartment(code=code, name=name)
            db.add(row)
            existing[name] = row
            used_codes.add(code)
    try:
        await db.commit()
    except IntegrityError:
        # Another request may have materialized the same departments concurrently.
        await db.rollback()
    rows = list((await db.execute(select(OrganizationDepartment).where(OrganizationDepartment.is_active.is_(True)).order_by(OrganizationDepartment.name))).scalars().all())
    counts = dict((await db.execute(select(Employee.department, func.count(Employee.id)).where(Employee.date_fired.is_(None)).group_by(Employee.department))).all())
    return [{"id": r.id, "code": r.code, "name": r.name, "lead_user_id": r.lead_user_id, "lead_name": r.lead_name, "employee_count": counts.get(r.name, 0)} for r in rows]


@router.post("/organization/departments", status_code=201)
async def create_department(data: DepartmentIn, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    row = OrganizationDepartment(**data.model_dump())
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Отдел с таким кодом или названием уже существует") from exc
    await db.refresh(row)
    return {"id": row.id, **data.model_dump()}


@router.get("/organization/departments/{department_id}")
async def department_detail(department_id: int, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    principal = principal_from_claims(claims)
    row = await _department_or_404(db, department_id)
    employees = list((await db.execute(select(Employee).where(Employee.department == row.name, Employee.date_fired.is_(None)).order_by(Employee.full_name))).scalars().all())
    contacts_stmt = select(ContactPoint).where(ContactPoint.department_id == row.id)
    if not principal.full_access:
        contacts_stmt = contacts_stmt.where(ContactPoint.is_active.is_(True))
    contacts = list((await db.execute(contacts_stmt.order_by(ContactPoint.is_active.desc(), ContactPoint.contact_type, ContactPoint.priority))).scalars().all())
    return {"id": row.id, "code": row.code, "name": row.name, "lead_user_id": row.lead_user_id, "lead_name": row.lead_name, "employees": [{"id": e.id, "full_name": e.full_name, "position": e.position, "erp_user_id": e.erp_user_id} for e in employees], "contacts": [ContactPointRead.model_validate(c).model_dump() for c in contacts]}


@router.post("/organization/departments/{department_id}/contacts", response_model=ContactPointRead, status_code=201)
async def create_department_contact(department_id: int, data: ContactPointIn, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    await _department_or_404(db, department_id)
    try:
        return await _create_contact(db, data=data, owner_type="department", department_id=department_id, actor_id=_actor(claims))
    except ValueError as exc:
        raise HTTPException(409 if "закреплён" in str(exc) or "используется" in str(exc) else 422, str(exc)) from exc
