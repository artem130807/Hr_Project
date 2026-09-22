"""Ролевые уведомления по событиям адаптации."""
from __future__ import annotations

from typing import Any

from app.app_logging import logger
from app.domain.adaptation_events import AdaptationTalkHRRequestedEvent
from app.messaging.channel_events import resolve_notification_role_ids
from app.messaging.message_event_producer import get_message_event_producer


async def publish_adaptation_talk_hr(detail: dict[str, Any]) -> None:
    checkpoint_id = int(detail.get("id") or 0)
    if checkpoint_id <= 0:
        logger.warning("adaptation talk HR notification skipped: empty checkpoint id")
        return
    role_ids = await resolve_notification_role_ids(("hr",))
    if not role_ids:
        logger.warning("adaptation talk HR notification skipped: HR role not resolved")
        return

    employee_name = str(detail.get("full_name") or "Сотрудник").strip()
    topic = str(detail.get("talk_hr_topic") or "").strip()
    lines = [f"{employee_name} просит конфиденциально поговорить с HR", f"Этап адаптации: #{checkpoint_id}"]
    if topic:
        lines.append(f"Тема: {topic}")
    await get_message_event_producer().publish(
        AdaptationTalkHRRequestedEvent(
            checkpoint_id=checkpoint_id,
            text="\n".join(lines),
            target_role_ids=tuple(role_ids),
        )
    )
