"""Normalized contacts and deterministic, side-effect-free adaptation routing."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.v1.models import ContactPoint


def normalize_contact(contact_type: str, value: str) -> str:
    raw = str(value or "").strip()
    if contact_type == "telegram":
        username = raw.removeprefix("@").strip().lower()
        if not re.fullmatch(r"[a-z0-9_]{5,32}", username):
            raise ValueError("Некорректный Telegram username")
        return username
    if contact_type == "phone":
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        if len(digits) != 11 or not digits.startswith("7"):
            raise ValueError("Телефон должен быть российским номером из 11 цифр")
        return f"+{digits}"
    if contact_type == "email":
        email = raw.lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ValueError("Некорректный email")
        return email
    raise ValueError("Неподдерживаемый тип контакта")


async def ensure_contact_available(db: AsyncSession, *, contact_type: str, normalized: str, usage_type: str, exclude_id: int | None = None):
    stmt = select(ContactPoint).where(
        ContactPoint.contact_type == contact_type,
        ContactPoint.normalized_value == normalized,
        ContactPoint.is_active.is_(True),
    )
    if exclude_id:
        stmt = stmt.where(ContactPoint.id != exclude_id)
    rows = list((await db.execute(stmt)).scalars().all())
    if rows and usage_type != "shared":
        raise ValueError("Этот контакт уже закреплён за другим владельцем")
    if any(row.usage_type != "shared" for row in rows):
        raise ValueError("Контакт уже используется как персональный")


async def clear_other_primary(db: AsyncSession, contact: ContactPoint) -> None:
    if not contact.is_primary or not contact.employee_id:
        return
    result = await db.execute(select(ContactPoint).where(
        ContactPoint.employee_id == contact.employee_id,
        ContactPoint.contact_type == contact.contact_type,
        ContactPoint.usage_type == contact.usage_type,
        ContactPoint.id != contact.id,
        ContactPoint.is_primary.is_(True),
    ))
    for row in result.scalars().all():
        row.is_primary = False


@dataclass(frozen=True)
class RoutingResolution:
    recipient_type: str
    reason: str
    contact_id: int | None = None
    recipient_user_id: str | None = None


def resolve_adaptation_recipient(
    contacts: Iterable[ContactPoint], *, allow_personal_fallback: bool,
    responsible_hr_user_id: str | None,
) -> RoutingResolution:
    eligible = [c for c in contacts if c.contact_type == "telegram" and c.is_active and c.allow_adaptation and c.verified_at and c.telegram_chat_id]
    work = sorted((c for c in eligible if c.usage_type == "work_personal" and c.owner_type == "employee"), key=lambda c: (not c.is_primary, c.priority, c.id))
    if work:
        return RoutingResolution("employee_telegram", "work_personal_primary" if work[0].is_primary else "work_personal_priority", work[0].id)
    personal = sorted((c for c in eligible if c.usage_type == "personal" and c.owner_type == "employee"), key=lambda c: (not c.is_primary, c.priority, c.id))
    if allow_personal_fallback and personal:
        return RoutingResolution("employee_telegram", "personal_fallback", personal[0].id)
    if responsible_hr_user_id:
        return RoutingResolution("responsible_hr", "no_eligible_employee_telegram", recipient_user_id=responsible_hr_user_id)
    return RoutingResolution("hr_role", "no_eligible_employee_telegram")
