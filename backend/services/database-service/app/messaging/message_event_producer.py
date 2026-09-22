"""Публикация доменных событий в RabbitMQ (очередь message-service)."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from app.app_logging import logger
from app.config import RABBITMQ_QUEUE_MESSAGE_ENTITY_CHANGED, RABBITMQ_URL
from app.domain.domain_event import DomainEvent


class MessageEventProducer:
    """Публикует доменные события в очередь ``message.entity_changed``.

    Тот же брокер/очередь, что erp-backend → message-service.
    Best-effort: ошибки брокера логируются и не роняют HTTP-запрос.
    """

    def __init__(self, *, rabbit_url: Optional[str] = None, queue: Optional[str] = None):
        self._rabbit_url = (rabbit_url if rabbit_url is not None else RABBITMQ_URL) or ""
        self._queue = (queue if queue is not None else RABBITMQ_QUEUE_MESSAGE_ENTITY_CHANGED) or ""

    async def publish(self, event: DomainEvent) -> bool:
        if not self._rabbit_url:
            logger.debug(
                "MessageEventProducer: skip %s — RABBITMQ_URL не задан",
                event.event_type,
            )
            return False

        payload = event.to_dict()
        try:
            await asyncio.to_thread(self._publish_sync, payload, event.event_type)
            logger.info(
                "MessageEventProducer: published %s → queue=%s event_id=%s "
                "hr_event_id=%s event_date=%s remind_before=%s remind_at_time=%s user_id=%s",
                event.event_type,
                self._queue,
                payload.get("event_id"),
                payload.get("hr_event_id"),
                payload.get("event_date"),
                payload.get("remind_before"),
                payload.get("remind_at_time"),
                payload.get("user_id") or payload.get("userId"),
            )
            return True
        except Exception as exc:
            logger.warning(
                "MessageEventProducer: failed to publish %s: %s",
                event.event_type,
                exc,
            )
            return False

    def _publish_sync(self, payload: dict[str, Any], event_type: str) -> None:
        from kombu import Connection, Producer, Queue

        queue_name = self._queue
        queue = Queue(queue_name, durable=True)
        body = json.dumps(payload, ensure_ascii=False, default=str)
        with Connection(self._rabbit_url) as conn:
            with conn.channel() as channel:
                queue.declare(channel=channel)
                producer = Producer(channel)
                producer.publish(
                    body,
                    exchange="",
                    routing_key=queue_name,
                    content_type="application/json",
                    headers={"event_type": event_type},
                    declare=[queue],
                    retry=True,
                )


_default_producer: Optional[MessageEventProducer] = None


def get_message_event_producer() -> MessageEventProducer:
    global _default_producer
    if _default_producer is None:
        _default_producer = MessageEventProducer()
    return _default_producer
