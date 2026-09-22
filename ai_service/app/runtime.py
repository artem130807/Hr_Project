"""Background loops: consume evaluate requests, relay outbox to RabbitMQ."""
from __future__ import annotations

import asyncio

from app.app_logging import logger
from app.config import (
    AI_EVALUATE_CONSUMER_ENABLED,
    AI_OUTBOX_POLL_SECONDS,
    RABBITMQ_QUEUE_CANDIDATE_EVALUATE_REQUEST,
    RABBITMQ_QUEUE_CANDIDATE_EVALUATE_RESULT,
    RABBITMQ_URL,
)
from app.db.session import get_session_factory, init_outbox_schema
from app.evaluate.pipeline import handle_evaluate_request
from app.messaging.outbox import relay_pending
from app.messaging.rabbit import drain_queue


def _handle_sync(payload: dict) -> None:
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(handle_evaluate_request(payload))
    finally:
        loop.close()


async def consume_once(limit: int = 5) -> int:
    if not RABBITMQ_URL:
        return 0
    return await asyncio.to_thread(
        drain_queue,
        rabbit_url=RABBITMQ_URL,
        queue_name=RABBITMQ_QUEUE_CANDIDATE_EVALUATE_REQUEST,
        handler=_handle_sync,
        limit=limit,
    )


async def relay_once(limit: int = 20) -> int:
    if not RABBITMQ_URL:
        return 0
    async with get_session_factory()() as session:
        return await relay_pending(
            rabbit_url=RABBITMQ_URL,
            queue_name=RABBITMQ_QUEUE_CANDIDATE_EVALUATE_RESULT,
            session=session,
            limit=limit,
        )


async def run_loops(stop: asyncio.Event) -> None:
    await init_outbox_schema()
    if not AI_EVALUATE_CONSUMER_ENABLED:
        logger.info("AI evaluate consumer disabled")
        return
    if not RABBITMQ_URL:
        logger.warning("AI evaluate consumer skipped — RABBITMQ_URL is empty")
        return
    logger.info(
        "AI evaluate loops started request=%s result=%s",
        RABBITMQ_QUEUE_CANDIDATE_EVALUATE_REQUEST,
        RABBITMQ_QUEUE_CANDIDATE_EVALUATE_RESULT,
    )
    while not stop.is_set():
        try:
            consumed = await consume_once()
            published = await relay_once()
            if consumed or published:
                logger.info("AI evaluate tick consumed=%s published=%s", consumed, published)
        except Exception:
            logger.exception("AI evaluate loop error")
        try:
            await asyncio.wait_for(stop.wait(), timeout=AI_OUTBOX_POLL_SECONDS)
        except asyncio.TimeoutError:
            continue
