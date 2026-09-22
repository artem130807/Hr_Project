from __future__ import annotations

import json
from queue import Empty
from typing import Any, Callable

from kombu import Connection, Producer, Queue

from app.app_logging import logger


class PermanentHandlerError(Exception):
    """Do not requeue: the message cannot succeed on retry."""


def decode_message_payload(message: Any) -> dict[str, Any]:
    raw = getattr(message, "body", message)
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PermanentHandlerError(f"invalid message encoding: {exc}") from exc
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PermanentHandlerError(f"invalid json: {exc}") from exc
    else:
        payload = raw
    if not isinstance(payload, dict):
        raise PermanentHandlerError("payload is not an object")
    return payload



def publish_json(*, rabbit_url: str, queue_name: str, payload: dict[str, Any], event_type: str) -> None:
    queue = Queue(queue_name, durable=True)
    body = json.dumps(payload, ensure_ascii=False, default=str)
    with Connection(rabbit_url) as conn:
        with conn.channel() as channel:
            queue.declare(channel=channel)
            Producer(channel).publish(
                body,
                exchange="",
                routing_key=queue_name,
                content_type="application/json",
                delivery_mode=2,
                headers={"event_type": event_type},
                declare=[queue],
                retry=True,
            )


def drain_queue(
    *,
    rabbit_url: str,
    queue_name: str,
    handler: Callable[[dict[str, Any]], None],
    limit: int = 20,
) -> int:
    processed = 0
    with Connection(rabbit_url) as conn:
        queue = conn.SimpleQueue(queue_name)
        try:
            for _ in range(max(1, limit)):
                try:
                    message = queue.get(block=False)
                except Empty:
                    break
                try:
                    payload = decode_message_payload(message)
                    handler(payload)
                    message.ack()
                    processed += 1
                except PermanentHandlerError as exc:
                    logger.warning("Dropping poison AI eval result: %s", exc)
                    try:
                        message.reject(requeue=False)
                    except Exception:
                        logger.exception("Failed to drop poison AI eval result")
                    processed += 1
                except Exception as exc:
                    logger.warning("AI eval result handler failed: %s", exc)
                    try:
                        message.reject(requeue=True)
                    except Exception:
                        logger.exception("Failed to requeue AI eval result")
                    break
        finally:
            queue.close()
    return processed
