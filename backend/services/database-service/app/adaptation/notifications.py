"""Idempotent adaptation notification schedule executed by the Huey worker."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adaptation.rules import KIND_LABELS, ROLE_EMPLOYEE, ROLE_HR, ROLE_MANAGER, roles_for_kind
from app.adaptation.links import public_adaptation_form_url
from app.db.v1.models import (
    AdaptationCheckpoint,
    AdaptationEnrollment,
    AdaptationModuleSettings,
    AdaptationNotificationDelivery,
    AdaptationNotificationTemplate,
    AdaptationParticipantForm,
    Employee,
)
from app.domain.adaptation_events import AdaptationNotificationEvent
from app.domain.hr_events import HrEventCreatedEvent
from app.messaging.channel_events import resolve_notification_role_ids
from app.messaging.message_event_producer import get_message_event_producer


DEFAULT_TEMPLATES: dict[tuple[str, str], str] = {
    ("employee", "initial"): "{full_name}, заполните форму адаптации «{stage}» до {plan_date}: {link}",
    ("manager", "initial"): "Заполните форму руководителя по адаптации сотрудника {full_name}, этап «{stage}»: {link}",
    ("employee", "reminder"): "Напоминание: форма адаптации «{stage}» ещё не заполнена: {link}",
    ("manager", "reminder"): "Напоминание: ожидается ваша форма по сотруднику {full_name}: {link}",
    ("employee", "next_day"): "Форма адаптации просрочена. Пожалуйста, заполните её: {link}",
    ("hr", "missing_16"): "Не все формы по этапу «{stage}» сотрудника {full_name} заполнены.",
    ("hr", "overdue_12"): "Сотрудник {full_name} не заполнил форму этапа «{stage}» на следующий день.",
    ("hr", "data_collected"): "Внешние ответы по этапу «{stage}» сотрудника {full_name} собраны. Нужен комментарий HR.",
}

# A deployment must not send every reminder accumulated for old checkpoints.
# A short grace period tolerates worker restarts while preventing a backfill storm.
DELIVERY_GRACE_PERIOD = timedelta(minutes=30)
MAX_AUTOMATIC_ATTEMPTS = 3


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_stale_delivery(scheduled_at: datetime, now: datetime) -> bool:
    return _as_aware_utc(scheduled_at) < _as_aware_utc(now) - DELIVERY_GRACE_PERIOD


class _TemplateVars(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def stage_display_name(kind: str) -> str:
    """Return a recipient-facing stage name instead of an internal event code."""
    return KIND_LABELS.get(kind, kind)


async def ensure_default_templates(db: AsyncSession) -> None:
    result = await db.execute(select(AdaptationNotificationTemplate))
    existing = {(row.audience, row.event) for row in result.scalars().all()}
    for (audience, event), text in DEFAULT_TEMPLATES.items():
        if (audience, event) not in existing:
            db.add(AdaptationNotificationTemplate(audience=audience, event=event, text=text, enabled=True))


async def get_settings(db: AsyncSession) -> AdaptationModuleSettings:
    result = await db.execute(select(AdaptationModuleSettings).order_by(AdaptationModuleSettings.id).limit(1))
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = AdaptationModuleSettings()
        db.add(settings)
        await db.flush()
    return settings


def _schedule(
    checkpoint: AdaptationCheckpoint,
    tz: ZoneInfo,
    *,
    overdue_enabled: bool,
    overdue_time: time,
) -> list[tuple[str, str, datetime]]:
    day = checkpoint.plan_date
    next_day = day + timedelta(days=1)
    events: list[tuple[str, str, datetime]] = []
    for role in roles_for_kind(checkpoint.kind):
        if role == ROLE_HR:
            continue
        events.append((role, "initial", datetime.combine(day, time(9), tzinfo=tz)))
        events.append((role, "reminder", datetime.combine(day, time(14), tzinfo=tz)))
    events.append((ROLE_HR, "missing_16", datetime.combine(day, time(16), tzinfo=tz)))
    if overdue_enabled and ROLE_EMPLOYEE in roles_for_kind(checkpoint.kind):
        events.append((ROLE_EMPLOYEE, "next_day", datetime.combine(next_day, overdue_time, tzinfo=tz)))
        events.append((ROLE_HR, "overdue_12", datetime.combine(next_day, time(12), tzinfo=tz)))
    return [(role, event, at.astimezone(timezone.utc)) for role, event, at in events]


async def _create_missing_deliveries(
    db: AsyncSession,
    checkpoints: list[AdaptationCheckpoint],
    *,
    tz: ZoneInfo,
    overdue_enabled: bool,
    overdue_time: time,
    now: datetime,
) -> None:
    for cp in checkpoints:
        if cp.closed or cp.forced_completed_at or cp.enrollment.archived:
            continue
        existing_forms = {form.role for form in (cp.participant_forms or [])}
        for participant_role in roles_for_kind(cp.kind):
            if participant_role in existing_forms:
                continue
            participant_user_id = None
            if participant_role == ROLE_EMPLOYEE and cp.enrollment.employee:
                participant_user_id = cp.enrollment.employee.erp_user_id
            elif participant_role == ROLE_MANAGER:
                participant_user_id = cp.enrollment.manager_user_id
            form = AdaptationParticipantForm(
                checkpoint_id=cp.id,
                role=participant_role,
                participant_user_id=participant_user_id,
            )
            db.add(form)
            cp.participant_forms.append(form)
        result = await db.execute(
            select(AdaptationNotificationDelivery).where(
                AdaptationNotificationDelivery.checkpoint_id == cp.id
            )
        )
        existing = {(row.role, row.event): row for row in result.scalars().all()}
        schedule = _schedule(
            cp,
            tz,
            overdue_enabled=overdue_enabled,
            overdue_time=overdue_time,
        )
        required_external = {role for role in roles_for_kind(cp.kind) if role != ROLE_HR}
        submitted = {answer.role for answer in (cp.answers or [])}
        if required_external and required_external.issubset(submitted) and ROLE_HR not in submitted:
            external_answers = [
                answer for answer in (cp.answers or []) if answer.role in required_external
            ]
            latest_answer_at = max(
                (answer.submitted_at for answer in external_answers),
                default=None,
            )
            if latest_answer_at is not None:
                if _as_aware_utc(latest_answer_at) >= _as_aware_utc(now) - DELIVERY_GRACE_PERIOD:
                    schedule.append((ROLE_HR, "data_collected", now))
        for role, event, scheduled_at in schedule:
            current = existing.get((role, event))
            if current is None:
                is_stale = is_stale_delivery(scheduled_at, now)
                db.add(
                    AdaptationNotificationDelivery(
                        checkpoint_id=cp.id,
                        role=role,
                        event=event,
                        scheduled_at=scheduled_at,
                        status="cancelled" if is_stale else "pending",
                        last_error=(
                            "Пропущено как устаревшее уведомление при первом запуске"
                            if is_stale else None
                        ),
                    )
                )


def _answered(cp: AdaptationCheckpoint, role: str) -> bool:
    return any(answer.role == role for answer in (cp.answers or []))


def _should_cancel(cp: AdaptationCheckpoint, delivery: AdaptationNotificationDelivery) -> bool:
    if cp.closed or cp.forced_completed_at or cp.enrollment.archived:
        return True
    if delivery.role in {ROLE_EMPLOYEE, ROLE_MANAGER}:
        return _answered(cp, delivery.role)
    missing_external = any(
        not _answered(cp, role) for role in roles_for_kind(cp.kind) if role != ROLE_HR
    )
    return delivery.event in {"missing_16", "overdue_12"} and not missing_external


async def _render(db: AsyncSession, cp: AdaptationCheckpoint, role: str, event: str) -> str:
    result = await db.execute(
        select(AdaptationNotificationTemplate).where(
            AdaptationNotificationTemplate.audience == role,
            AdaptationNotificationTemplate.event == event,
        )
    )
    template = result.scalar_one_or_none()
    if template is not None and not template.enabled:
        return ""
    text = template.text if template else DEFAULT_TEMPLATES.get((role, event), "")
    person = cp.enrollment.employee or cp.enrollment.temporary_employee
    form = next((item for item in (getattr(cp, "participant_forms", None) or []) if item.role == role), None)
    link = public_adaptation_form_url(form.token) if form else ""
    return text.format_map(
        _TemplateVars(
            full_name=getattr(person, "full_name", "Сотрудник"),
            stage=stage_display_name(cp.kind),
            plan_date=cp.plan_date.strftime("%d.%m.%Y"),
            link=link,
        )
    ).strip()


async def _publish_delivery(db: AsyncSession, delivery: AdaptationNotificationDelivery) -> bool:
    cp_result = await db.execute(
        select(AdaptationCheckpoint)
        .options(
            selectinload(AdaptationCheckpoint.answers),
            selectinload(AdaptationCheckpoint.participant_forms),
            selectinload(AdaptationCheckpoint.enrollment).selectinload(AdaptationEnrollment.employee),
            selectinload(AdaptationCheckpoint.enrollment).selectinload(AdaptationEnrollment.temporary_employee),
        )
        .where(AdaptationCheckpoint.id == delivery.checkpoint_id)
        .execution_options(populate_existing=True)
    )
    cp = cp_result.scalar_one_or_none()
    if not cp or _should_cancel(cp, delivery):
        delivery.status = "cancelled"
        return True
    content = await _render(db, cp, delivery.role, delivery.event)
    if not content:
        delivery.status = "cancelled"
        return True
    producer = get_message_event_producer()
    if delivery.role == ROLE_HR:
        role_ids = await resolve_notification_role_ids(("hr",))
        if not role_ids:
            raise RuntimeError("ERP HR role is not resolved")
        ok = await producer.publish(
            AdaptationNotificationEvent(
                checkpoint_id=cp.id,
                notification_type=delivery.event,
                text=content,
                target_role_ids=tuple(role_ids),
            )
        )
    else:
        user_id = (
            getattr(cp.enrollment.employee, "erp_user_id", None)
            if delivery.role == ROLE_EMPLOYEE
            else cp.enrollment.manager_user_id
        )
        if not user_id:
            raise RuntimeError(f"recipient for role {delivery.role} is not configured")
        ok = await producer.publish(
            HrEventCreatedEvent(
                hr_event_id=cp.id,
                type=f"adaptation_{delivery.event}",
                event_date=datetime.now(timezone.utc).date(),
                remind_before=0,
                employee_name=(cp.enrollment.employee or cp.enrollment.temporary_employee).full_name,
                note=content,
                user_id=str(user_id),
            )
        )
    if not ok:
        raise RuntimeError("RabbitMQ publish failed")
    delivery.status = "sent"
    delivery.sent_at = datetime.now(timezone.utc)
    delivery.last_error = None
    if delivery.event == "initial":
        form = next(
            (item for item in (cp.participant_forms or []) if item.role == delivery.role),
            None,
        )
        if form:
            form.sent_at = delivery.sent_at
    return True


async def run_notification_tick(db: AsyncSession, *, now: datetime | None = None) -> dict[str, int]:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    settings = await get_settings(db)
    try:
        tz = ZoneInfo(settings.timezone or "Europe/Samara")
    except Exception:
        tz = ZoneInfo("Europe/Samara")
    await ensure_default_templates(db)
    terminated_result = await db.execute(
        select(AdaptationEnrollment)
        .join(Employee, AdaptationEnrollment.employee_id == Employee.id)
        .where(
            AdaptationEnrollment.archived.is_(False),
            AdaptationEnrollment.closed.is_(False),
            Employee.date_fired.is_not(None),
        )
    )
    for enrollment in terminated_result.scalars().all():
        enrollment.archived = True
        enrollment.archive_reason = "Автоматически: сотрудник уволен"
    cp_result = await db.execute(
        select(AdaptationCheckpoint)
        .options(
            selectinload(AdaptationCheckpoint.answers),
            selectinload(AdaptationCheckpoint.participant_forms),
            selectinload(AdaptationCheckpoint.enrollment).selectinload(AdaptationEnrollment.employee),
            selectinload(AdaptationCheckpoint.enrollment).selectinload(AdaptationEnrollment.temporary_employee),
        )
        .join(AdaptationEnrollment)
        .where(
            AdaptationEnrollment.archived.is_(False),
            AdaptationCheckpoint.closed.is_(False),
            AdaptationCheckpoint.forced_completed_at.is_(None),
            AdaptationCheckpoint.plan_date <= moment.astimezone(tz).date() + timedelta(days=1),
        )
        .execution_options(populate_existing=True)
    )
    checkpoints = list(cp_result.scalars().unique().all())
    await _create_missing_deliveries(
        db,
        checkpoints,
        tz=tz,
        overdue_enabled=settings.overdue_enabled,
        overdue_time=settings.overdue_time,
        now=moment,
    )
    await db.flush()
    due_result = await db.execute(
        select(AdaptationNotificationDelivery)
        .where(
            AdaptationNotificationDelivery.status.in_(["pending", "failed"]),
            AdaptationNotificationDelivery.scheduled_at <= moment,
            AdaptationNotificationDelivery.attempts < MAX_AUTOMATIC_ATTEMPTS,
        )
        .order_by(AdaptationNotificationDelivery.scheduled_at, AdaptationNotificationDelivery.id)
        # PostgreSQL is the final concurrency guard when several Huey replicas
        # run or Redis locking is temporarily unavailable.
        .with_for_update(skip_locked=True)
    )
    sent = failed = cancelled = 0
    for delivery in due_result.scalars().all():
        # Also protects installations that already contain pending historical
        # rows created by an earlier application version.
        if is_stale_delivery(delivery.scheduled_at, moment):
            delivery.status = "cancelled"
            delivery.last_error = "Пропущено как устаревшее уведомление"
            cancelled += 1
            continue
        delivery.attempts += 1
        try:
            await _publish_delivery(db, delivery)
            if delivery.status == "cancelled":
                cancelled += 1
            else:
                sent += 1
        except Exception as exc:
            delivery.status = "failed"
            delivery.last_error = str(exc)[:2000]
            # Avoid retrying a failing broker/recipient every minute. Explicit
            # retry from the UI resets attempts and schedules delivery now.
            delivery.scheduled_at = moment + timedelta(
                minutes=min(30, 2 ** delivery.attempts)
            )
            failed += 1
    await db.commit()
    return {"sent": sent, "failed": failed, "cancelled": cancelled}
