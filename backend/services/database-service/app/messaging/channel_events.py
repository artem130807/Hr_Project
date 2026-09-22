"""События HR → message-service (заявки на подбор).

Паттерн как erp-backend ``services.message_notify.channel_events``:
бэкенд собирает текст сам и публикует в очередь ``message.entity_changed``.
message-service создаёт отдельные уведомления для целевых ERP-ролей.
"""
from __future__ import annotations

from typing import Any, Optional

from app.app_logging import logger
from app.domain.hiring_request_events import HiringRequestCreatedEvent
from app.messaging.message_event_producer import get_message_event_producer
from app.erp.client import ErpClient
from app.erp.mapper import map_role


HIRING_REQUEST_NOTIFICATION_ROLES = ("admin", "leader", "hr")


async def resolve_notification_role_ids(role_names: tuple[str, ...]) -> list[int]:
    """Resolve canonical ERP role names to stable numeric IDs used by message-service."""
    roles = await ErpClient().list_roles()
    wanted = set(role_names)
    role_ids: list[int] = []
    found: set[str] = set()
    for raw in roles:
        mapped = map_role(raw)
        if mapped not in wanted or mapped in found:
            continue
        try:
            role_id = int(raw.get("id"))
        except (TypeError, ValueError, AttributeError):
            continue
        if role_id <= 0:
            continue
        found.add(mapped)
        role_ids.append(role_id)
    missing = [role for role in role_names if role not in found]
    if missing:
        logger.warning("notification roles not resolved: %s", ", ".join(missing))
    return role_ids


def _safe(value: Any, default: str = "") -> str:
    if value is None:
        return default
    raw = getattr(value, "value", value)
    text = str(raw).strip()
    return text if text and text != "None" else default


def hiring_request_created_text(req: Any, *, actor_name: Optional[str] = None) -> str:
    """Текст ролевого уведомления о новой заявке на подбор."""
    req_id = getattr(req, "id", None)
    code = f"З-{req_id}" if req_id is not None else "новая заявка"
    position = _safe(getattr(req, "position", None), "должность не указана")
    department = _safe(getattr(req, "department", None))
    headcount = getattr(req, "headcount", None)
    initiator = _safe(
        getattr(req, "initiator_name", None) or getattr(req, "manager_name", None)
    )
    created_by = _safe(actor_name)
    lines = [f"Создана заявка на подбор {code}", f"Должность: {position}"]
    if department:
        lines.append(f"Отдел: {department}")
    try:
        n = int(headcount)
        if n > 0:
            lines.append(f"Нужно: {n} чел.")
    except (TypeError, ValueError):
        pass
    if initiator:
        lines.append(f"Инициатор: {initiator}")
    if created_by and created_by != initiator:
        lines.append(f"Создал: {created_by}")
    return "\n".join(lines)


def _actor_str(actor_user_id: Any) -> Optional[str]:
    if actor_user_id is None:
        return None
    text = str(actor_user_id).strip()
    return text or None


async def publish_hiring_request_created(
    req: Any,
    *,
    actor_user_id: Any = None,
    actor_name: Optional[str] = None,
) -> None:
    try:
        req_id = int(getattr(req, "id", None) or 0)
    except (TypeError, ValueError):
        req_id = 0
    if req_id <= 0:
        logger.warning("channel publish skipped [hiring_request.create]: empty id")
        return
    role_ids = await resolve_notification_role_ids(HIRING_REQUEST_NOTIFICATION_ROLES)
    if not role_ids:
        logger.warning("hiring request role notification skipped: no target role ids")
        return
    text = hiring_request_created_text(req, actor_name=actor_name)
    await get_message_event_producer().publish(
        HiringRequestCreatedEvent(
            hiring_request_id=req_id,
            text=text,
            target_role_ids=tuple(role_ids),
            actor_user_id=_actor_str(actor_user_id),
        )
    )


async def safe_channel_publish(coro, *, context: str) -> None:
    """Не ронять бизнес-операцию из‑за сбоя публикации канального события."""
    try:
        await coro
    except Exception as exc:
        logger.warning("channel publish failed [%s]: %s", context, exc)
