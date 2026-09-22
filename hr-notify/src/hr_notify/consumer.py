"""RabbitMQ consumer: hr.event.notify → Huey schedule → Telegram."""
from __future__ import annotations

import logging
import os
import signal
import sys
import time

import pika

from hr_notify.handler import schedule_hr_notification
from hr_notify.schemas import parse_hr_event_notify
from hr_notify.tasks import send_hr_telegram_notification

logger = logging.getLogger(__name__)


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def process_delivery_body(body: bytes) -> str:
    """Parse payload and schedule Huey task. Returns schedule mode."""
    payload = parse_hr_event_notify(body)
    return schedule_hr_notification(payload, send_hr_telegram_notification)


def run_consumer() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [hr-notify-consumer] %(message)s",
    )
    rabbit_url = _env("RABBITMQ_URL")
    queue = _env("RABBITMQ_QUEUE_HR_NOTIFY", "hr.event.notify")
    if not rabbit_url:
        logger.error("RABBITMQ_URL is not set")
        sys.exit(1)

    params = pika.URLParameters(rabbit_url)
    params.heartbeat = 30
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=queue, durable=True)
    channel.basic_qos(prefetch_count=1)

    stop = {"flag": False}

    def _stop(*_args) -> None:
        stop["flag"] = True
        try:
            channel.stop_consuming()
        except Exception:
            pass

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    def on_message(ch, method, _properties, body: bytes) -> None:
        try:
            payload = parse_hr_event_notify(body)
            mode = schedule_hr_notification(payload, send_hr_telegram_notification)
            logger.info(
                "accepted hr.event.notify mode=%s hr_event_id=%s type=%s "
                "event_date=%s remind_before=%s notify_at=%s user_id=%s "
                "content_preview=%r",
                mode,
                payload.hr_event_id,
                payload.type,
                payload.event_date,
                payload.remind_before,
                payload.notify_at,
                payload.user_id,
                (payload.content or "")[:120],
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            logger.exception(
                "failed to process hr.event.notify; nack without requeue body=%r",
                (body or b"")[:300],
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_consume(queue=queue, on_message_callback=on_message)
    logger.info("consuming queue=%s", queue)
    try:
        channel.start_consuming()
    finally:
        if connection.is_open:
            connection.close()
        # Keep process alive briefly for graceful shutdown logs.
        time.sleep(0.05)


if __name__ == "__main__":
    run_consumer()
