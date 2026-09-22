"""Publish HR calendar / hiring-request rows to RabbitMQ (message.entity_changed)."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from app.app_logging import logger
from app.config import ERP_BASE
from app.domain.hr_events import HrEventCreatedEvent
from app.domain.hr_hiring_request_events import HrHiringRequestCreatedEvent, actor_display_name
from app.erp.client import ErpClient
from app.erp.mapper import find_erp_user_id_by_telegram
from app.messaging.channel_events import hiring_request_created_text
from app.messaging.message_event_producer import get_message_event_producer


async def resolve_recipient_user_id(telegram_user: str | None) -> str | None:
    if not telegram_user or not str(telegram_user).strip():
        return None
    if not ERP_BASE:
        logger.warning("resolve recipient user_id skipped: ERP_BASE is not configured")
        return None
    try:
        raw_users = await ErpClient().list_users()
    except Exception as exc:
        logger.warning("resolve recipient user_id: ERP list_users failed: %s", exc)
        return None
    return find_erp_user_id_by_telegram(raw_users, telegram_user)


async def publish_hr_calendar_event(
    event: Any,
    *,
    occurrence: str = "initial",
    event_date: Optional[date] = None,
    remind_before: Optional[int] = None,
) -> bool:
    recipient_user_id = await resolve_recipient_user_id(getattr(event, "telegram_user", None))
    if getattr(event, "telegram_user", None) and not recipient_user_id:
        logger.warning(
            "HR event %s: telegram_user=%r not mapped to ERP user_id — "
            "in-app message skipped, Telegram channel notify still published",
            getattr(event, "id", None),
            event.telegram_user,
        )
    domain = HrEventCreatedEvent.from_orm(
        event,
        user_id=recipient_user_id,
        occurrence=occurrence,
        event_date_override=event_date,
        remind_before_override=remind_before,
    )
    return await get_message_event_producer().publish(domain)


async def publish_hr_hiring_request_created(
    req: Any,
    *,
    actor_user_id: Any = None,
    actor_name: Optional[str] = None,
) -> bool:
    """Доменное событие заявки на подбор → тот же путь, что hr.event.created."""
    try:
        req_id = int(getattr(req, "id", None) or 0)
    except (TypeError, ValueError):
        req_id = 0
    if req_id <= 0:
        logger.warning("hr hiring_request publish skipped: empty id")
        return False
    actor_id = str(actor_user_id).strip() if actor_user_id is not None else None
    if not actor_id:
        actor_id = None
    name = actor_display_name(req, actor_name)
    text = hiring_request_created_text(req, actor_name=name)
    event = HrHiringRequestCreatedEvent.from_orm(
        req,
        text=text,
        actor_user_id=actor_id,
        actor_name=name,
    )
    return await get_message_event_producer().publish(event)
