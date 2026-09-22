"""Server-side authorization and response shaping for adaptation data."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status


FULL_ACCESS_ROLES = frozenset({
    "superadmin", "admin", "manager", "senior_manager",
    "hr", "owner", "dev", "tech_admin", "director",
})
MANAGER_ROLES = frozenset({"leader", "dept_leader"})


@dataclass(frozen=True)
class AdaptationPrincipal:
    user_id: str
    role: str
    name: str = ""
    service: bool = False

    @property
    def full_access(self) -> bool:
        return self.service or self.role in FULL_ACCESS_ROLES


def principal_from_claims(claims: Any) -> AdaptationPrincipal:
    if not isinstance(claims, dict):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Необходима авторизация")
    user_id = str(
        claims.get("erp_user_id")
        or claims.get("user_id")
        or claims.get("id")
        or claims.get("sub")
        or ""
    ).strip()
    role = str(claims.get("role") or "").strip().lower()
    name = str(claims.get("full_name") or claims.get("name") or claims.get("sub") or "").strip()
    service = str(claims.get("type") or "").lower() == "service"
    return AdaptationPrincipal(user_id=user_id, role=role, name=name, service=service)


def require_hr(principal: AdaptationPrincipal) -> None:
    if not principal.full_access:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Действие доступно только HR или администратору")


def can_manage_enrollment(principal: AdaptationPrincipal, enrollment: Any) -> bool:
    if principal.full_access:
        return True
    return principal.role in MANAGER_ROLES and principal.user_id and (
        principal.user_id == str(getattr(enrollment, "manager_user_id", "") or "")
    )


def require_enrollment_access(principal: AdaptationPrincipal, enrollment: Any) -> None:
    if not can_manage_enrollment(principal, enrollment):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к этому кейсу адаптации")


def redact_checkpoint(row: dict, principal: AdaptationPrincipal) -> dict:
    """Managers receive only their answer and HR-approved safe summary."""
    if principal.full_access:
        return row
    safe = dict(row)
    safe["answers"] = [
        answer for answer in (row.get("answers") or []) if answer.get("role") == "manager"
    ]
    safe.pop("form", None)
    safe.pop("form_links", None)
    safe.pop("employee_take_token", None)
    safe.pop("employee_take_path", None)
    safe.pop("core_history", None)
    safe.pop("risk_signals", None)
    safe["talk_hr"] = False
    return safe
