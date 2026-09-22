"""Bidirectional work-start-date synchronization between HR and ERP records."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select, update

from app.adaptation.rules import plan_date_for
from app.db.v1.models import AdaptationAnswer, AdaptationCheckpoint, AdaptationEnrollment, Employee
from app.erp.client import ErpClient


def _normal_name(value: str | None) -> str:
    return " ".join(str(value or "").casefold().split())


async def find_hr_employee_by_erp_id(db, erp_user_id: str) -> Employee | None:
    erp_id = str(erp_user_id or "").strip()
    if not erp_id:
        return None
    result = await db.execute(select(Employee).where(Employee.erp_user_id == erp_id))
    row = result.scalars().first()
    return row if isinstance(row, Employee) else None


def validate_start_date(employee: Employee, value: date) -> None:
    if employee.date_fired is not None and value > employee.date_fired:
        raise ValueError("Дата выхода на работу не может быть позже даты увольнения")


async def apply_erp_date_to_hr_employee(db, employee: Employee, value: date) -> bool:
    """Apply ERP date locally without calling ERP again (loop prevention)."""
    validate_start_date(employee, value)
    if employee.date_hired == value:
        return False
    employee.date_hired = value
    return True


async def reschedule_active_adaptation_for_start_date(
    db,
    *,
    employee_id: int,
    value: date,
) -> int:
    """Move an active adaptation plan to a new employment start date.

    Historical and explicitly managed checkpoints are immutable: completed,
    answered, forced/finalized, manually rescheduled and extra checkpoints are
    left untouched. The active case start and untouched standard checkpoints
    receive the new baseline dates.
    """
    enrollment_result = await db.execute(
        select(AdaptationEnrollment.id).where(
            AdaptationEnrollment.employee_id == employee_id,
            AdaptationEnrollment.closed.is_(False),
            AdaptationEnrollment.archived.is_(False),
        )
    )
    enrollment_id = enrollment_result.scalar_one_or_none()
    if enrollment_id is None:
        return 0

    await db.execute(
        update(AdaptationEnrollment)
        .where(AdaptationEnrollment.id == enrollment_id)
        .values(start_date=value)
    )
    checkpoints_result = await db.execute(
        select(
            AdaptationCheckpoint.id,
            AdaptationCheckpoint.kind,
            AdaptationCheckpoint.plan_date,
            AdaptationCheckpoint.original_plan_date,
            AdaptationCheckpoint.closed,
            AdaptationCheckpoint.fact_date,
            AdaptationCheckpoint.forced_completed_at,
            AdaptationCheckpoint.finalized_at,
            AdaptationCheckpoint.rescheduled_at,
        ).where(
            AdaptationCheckpoint.enrollment_id == enrollment_id
        )
    )
    checkpoints = list(checkpoints_result.all())
    checkpoint_ids = [checkpoint.id for checkpoint in checkpoints]
    answered_ids: set[int] = set()
    if checkpoint_ids:
        answers_result = await db.execute(
            select(AdaptationAnswer.checkpoint_id)
            .where(AdaptationAnswer.checkpoint_id.in_(checkpoint_ids))
            .distinct()
        )
        answered_ids = {int(item) for item in answers_result.scalars().all()}

    changed = 0
    for checkpoint in checkpoints:
        if checkpoint.kind == "extra":
            continue
        if (
            checkpoint.id in answered_ids
            or checkpoint.closed
            or checkpoint.fact_date is not None
            or checkpoint.forced_completed_at is not None
            or checkpoint.finalized_at is not None
            or checkpoint.rescheduled_at is not None
        ):
            continue
        try:
            planned = plan_date_for(checkpoint.kind, value)
        except ValueError:
            # Unknown/custom kinds are not implicitly moved.
            continue
        if checkpoint.plan_date != planned or checkpoint.original_plan_date != planned:
            await db.execute(
                update(AdaptationCheckpoint)
                .where(AdaptationCheckpoint.id == checkpoint.id)
                .values(plan_date=planned, original_plan_date=planned)
            )
            changed += 1
    return changed


def _erp_identity(raw: dict) -> tuple[str | None, str]:
    erp_id = raw.get("id") or raw.get("user_id") or raw.get("uuid")
    name = raw.get("name") or raw.get("full_name") or raw.get("fio")
    return (str(erp_id).strip() if erp_id is not None else None, _normal_name(name))


async def resolve_erp_user_id(
    employee: Employee,
    client: ErpClient,
    *,
    access_token: str | None = None,
) -> str | None:
    """Prefer the stable link; use exact unique full-name match only for legacy rows."""
    linked = str(employee.erp_user_id or "").strip()
    if linked:
        return linked
    wanted = _normal_name(employee.full_name)
    if not wanted:
        return None
    matches: list[str] = []
    for raw in await client.list_users(access_token=access_token):
        erp_id, name = _erp_identity(raw)
        if erp_id and name == wanted:
            matches.append(erp_id)
    unique = list(dict.fromkeys(matches))
    return unique[0] if len(unique) == 1 else None


async def push_hr_date_to_erp(
    employee: Employee,
    value: date,
    *,
    client: ErpClient,
    access_token: str | None,
) -> str | None:
    """Update matching ERP user and return its id, or None when no safe match exists."""
    erp_user_id = await resolve_erp_user_id(employee, client, access_token=access_token)
    if not erp_user_id:
        return None
    await client.update_user(
        erp_user_id,
        {"date_hired": value.isoformat()},
        access_token=access_token,
    )
    return erp_user_id
