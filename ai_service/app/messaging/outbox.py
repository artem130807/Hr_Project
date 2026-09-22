from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OutboxMessage
from app.messaging.rabbit import publish_json


async def enqueue_outbox(
    session: AsyncSession,
    *,
    event_type: str,
    correlation_id: str,
    payload: dict[str, Any],
    aggregate_id: str = "",
    aggregate_type: str = "candidate_evaluation",
) -> OutboxMessage:
    existing = (
        await session.execute(
            select(OutboxMessage).where(OutboxMessage.correlation_id == correlation_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    row = OutboxMessage(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id or ""),
        correlation_id=correlation_id,
        payload=payload,
        status="pending",
    )
    session.add(row)
    await session.flush()
    return row


async def list_pending(
    session: AsyncSession,
    *,
    limit: int = 20,
    event_type: str | None = None,
) -> Sequence[OutboxMessage]:
    stmt = select(OutboxMessage).where(OutboxMessage.status == "pending")
    if event_type:
        stmt = stmt.where(OutboxMessage.event_type == event_type)
    result = await session.execute(stmt.order_by(OutboxMessage.id.asc()).limit(limit))
    return result.scalars().all()


async def mark_published(session: AsyncSession, row: OutboxMessage) -> None:
    row.status = "published"
    row.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
    row.last_error = None
    await session.flush()


async def mark_failed(session: AsyncSession, row: OutboxMessage, error: str) -> None:
    row.attempts = int(row.attempts or 0) + 1
    row.last_error = (error or "")[:2000]
    if row.attempts >= 12:
        row.status = "failed"
    await session.flush()


async def relay_pending(
    *,
    rabbit_url: str,
    queue_name: str,
    session: AsyncSession,
    limit: int = 20,
    event_type: str = "hr.candidate.evaluate.completed",
) -> int:
    rows = await list_pending(session, limit=limit, event_type=event_type)
    published = 0
    for row in rows:
        try:
            publish_json(
                rabbit_url=rabbit_url,
                queue_name=queue_name,
                payload=row.payload if isinstance(row.payload, dict) else {},
                event_type=row.event_type,
            )
            await mark_published(session, row)
            published += 1
        except Exception as exc:
            await mark_failed(session, row, str(exc))
    await session.commit()
    return published
