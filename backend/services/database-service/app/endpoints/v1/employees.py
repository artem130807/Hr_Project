from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.middleware import get_db
from app.db.v1.models import AdaptationEnrollment, ContactPoint, Employee, VnrHire
from app.db.v1.enums import VnrHireStatus
from app.schemas.v1.hr_ops import EmployeeCreate, EmployeeRead, EmployeeUpdate
from app.adaptation.access import principal_from_claims, require_hr
from app.utils.audit import write_audit
from app.utils.utils import get_current_user
from app.config import ERP_BASE
from app.app_logging import logger
from app.erp.client import ErpClient
from app.services.employee_start_date_sync import (
    reschedule_active_adaptation_for_start_date,
    resolve_erp_user_id,
)

router = APIRouter()
_oauth2 = OAuth2PasswordBearer(tokenUrl="/v1/token/user", auto_error=False)


@router.get("/employees", response_model=list[EmployeeRead])
async def list_employees(
    department: str | None = Query(None),
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    q = select(Employee).where(Employee.archived_at.is_(None)).order_by(Employee.id.desc())
    if department:
        q = q.where(Employee.department == department)
    if active_only:
        q = q.where(Employee.date_fired.is_(None))
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/employees/{employee_id}", response_model=EmployeeRead)
async def get_employee(employee_id: int, db: AsyncSession = Depends(get_db)):
    emp = await db.get(Employee, employee_id)
    if not emp:
        raise HTTPException(404, "Employee not found")
    return emp


@router.post("/employees", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
async def create_employee(data: EmployeeCreate, db: AsyncSession = Depends(get_db)):
    payload = data.model_dump(exclude_unset=True)
    adaptation_route = payload.pop("adaptation_route", None)
    if not payload.get("date_hired"):
        payload["date_hired"] = date.today()
    if payload.get("hobbies") is None:
        payload["hobbies"] = []
    emp = Employee(**payload)
    db.add(emp)
    await db.flush()
    from app.adaptation.onboarding import enroll_new_employee
    enroll_new_employee(db, emp, route=adaptation_route)
    await write_audit(
        db,
        action="employee.create",
        entity_type="employee",
        entity_id=emp.id,
        details=f"Created employee {payload.get('full_name')}",
    )
    await db.commit()
    await db.refresh(emp)
    return emp


@router.patch("/employees/{employee_id}", response_model=EmployeeRead)
async def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
    token: str | None = Depends(_oauth2),
):
    require_hr(principal_from_claims(claims))
    emp = await db.get(Employee, employee_id)
    if not emp:
        raise HTTPException(404, "Employee not found")
    changes = data.model_dump(exclude_unset=True)
    if "date_hired" in changes and changes["date_hired"] is None:
        raise HTTPException(422, "Дата выхода на работу обязательна")
    effective_start = changes.get("date_hired", emp.date_hired)
    effective_end = changes.get("date_fired", emp.date_fired)
    if effective_end is not None and effective_start > effective_end:
        raise HTTPException(422, "Дата выхода на работу не может быть позже даты увольнения")
    erp_id: str | None = None
    erp_client: ErpClient | None = None
    access = token if isinstance(token, str) else None
    if "date_hired" in changes and ERP_BASE:
        erp_client = ErpClient()
        try:
            erp_id = await resolve_erp_user_id(emp, erp_client, access_token=access)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(502, f"Не удалось определить сотрудника в ERP: {exc}") from exc
        if erp_id and not emp.erp_user_id:
            # A legacy row may be found by its exact full name. Never create a
            # second local owner for the same stable ERP identifier.
            owner_result = await db.execute(
                select(Employee.id).where(
                    Employee.erp_user_id == erp_id,
                    Employee.id != employee_id,
                )
            )
            if owner_result.scalar_one_or_none() is not None:
                raise HTTPException(
                    409,
                    "Пользователь ERP уже связан с другой карточкой сотрудника. "
                    "Объедините дубли перед синхронизацией даты.",
                )
            emp.erp_user_id = erp_id

    try:
        for k, v in changes.items():
            setattr(emp, k, v)
        adaptation_points_changed = 0
        if "date_hired" in changes:
            adaptation_points_changed = await reschedule_active_adaptation_for_start_date(
                db,
                employee_id=employee_id,
                value=changes["date_hired"],
            )
        await write_audit(
            db,
            action="employee.update",
            entity_type="employee",
            entity_id=employee_id,
            details=(
                f"Updated fields: {list(changes.keys())}; "
                f"adaptation_points_rescheduled={adaptation_points_changed}"
            ),
        )
        # Flush local constraints before changing the remote ERP record. This
        # prevents a successful ERP update followed by an avoidable local 500.
        await db.flush()
        if erp_id and erp_client is not None:
            await erp_client.update_user(
                erp_id,
                {"date_hired": changes["date_hired"].isoformat()},
                access_token=access,
            )
        await db.commit()
        await db.refresh(emp)
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            409,
            "Не удалось связать карточки HR и ERP: такая связь уже существует.",
        ) from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.exception(
            f"Employee start-date transaction failed: employee_id={employee_id}; "
            f"fields={list(changes.keys())}; error={exc}"
        )
        raise HTTPException(500, "Не удалось сохранить дату выхода в HR-платформе") from exc
    except Exception as exc:
        await db.rollback()
        raise HTTPException(502, f"Не удалось синхронизировать дату выхода с ERP: {exc}") from exc
    return emp


@router.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    claims=Depends(get_current_user),
):
    require_hr(principal_from_claims(claims))
    emp = await db.get(Employee, employee_id)
    if not emp:
        raise HTTPException(404, "Employee not found")
    if emp.archived_at is not None:
        return None

    now = datetime.now(timezone.utc)
    emp.archived_at = now
    # Preserve business history but stop operational use of the removed row.
    await db.execute(
        update(ContactPoint)
        .where(ContactPoint.employee_id == employee_id, ContactPoint.is_active.is_(True))
        .values(is_active=False)
    )
    await db.execute(
        update(AdaptationEnrollment)
        .where(
            AdaptationEnrollment.employee_id == employee_id,
            AdaptationEnrollment.archived.is_(False),
        )
        .values(archived=True, archive_reason="Сотрудник удалён из HR-платформы")
    )
    await db.execute(
        update(VnrHire)
        .where(VnrHire.employee_id == employee_id, VnrHire.status == VnrHireStatus.in_work.value)
        .values(status=VnrHireStatus.left.value, left_at=now)
    )
    await write_audit(
        db,
        action="employee.archive",
        entity_type="employee",
        entity_id=employee_id,
        details=f"Archived employee {emp.full_name}; related history preserved",
    )
    await db.commit()
    return None
