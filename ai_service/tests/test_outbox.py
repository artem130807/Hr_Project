"""Outbox helpers with mocked session / publisher."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.db.models import OutboxMessage
from app.messaging.outbox import enqueue_outbox, relay_pending


@pytest.mark.asyncio
async def test_enqueue_outbox_is_idempotent_by_correlation_id():
    existing = OutboxMessage(
        id=1,
        event_type="hr.candidate.evaluate.completed",
        correlation_id="abc",
        payload={"score": 1},
        status="pending",
    )

    class Session:
        async def execute(self, stmt):
            return SimpleNamespace(scalar_one_or_none=lambda: existing)

        def add(self, row):
            raise AssertionError("must not insert a duplicate")

        async def flush(self):
            return None

    row = await enqueue_outbox(
        Session(),
        event_type="hr.candidate.evaluate.completed",
        correlation_id="abc",
        payload={"score": 2},
    )
    assert row is existing


@pytest.mark.asyncio
async def test_relay_pending_publishes_and_marks():
    row = OutboxMessage(
        id=3,
        event_type="hr.candidate.evaluate.completed",
        correlation_id="c1:result",
        payload={"score": 90, "comment": "ok"},
        status="pending",
        attempts=0,
    )

    class Session:
        async def execute(self, stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [row]))

        async def flush(self):
            return None

        async def commit(self):
            return None

    with patch("app.messaging.outbox.publish_json") as publish:
        count = await relay_pending(
            rabbit_url="amqp://guest:guest@localhost//",
            queue_name="hr.candidate.evaluate.completed",
            session=Session(),
        )
    assert count == 1
    assert row.status == "published"
    publish.assert_called_once()


@pytest.mark.asyncio
async def test_consume_and_relay_skip_without_rabbit(monkeypatch):
    from app import runtime

    monkeypatch.setattr(runtime, "RABBITMQ_URL", "")
    assert await runtime.consume_once() == 0
    assert await runtime.relay_once() == 0

