from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai_eval.service import apply_evaluation_result, enqueue_candidate_evaluation
from app.db.v1.models import CandidateAiEvaluation, OutboxMessage


@pytest.mark.asyncio
async def test_enqueue_candidate_evaluation_writes_outbox_and_row():
    added = []
    vacancy = SimpleNamespace(id=8, department=SimpleNamespace(value="логистический"))

    class Session:
        async def execute(self, stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: None))

        async def get(self, model, pk):
            return vacancy

        def add(self, obj):
            added.append(obj)
            if isinstance(obj, CandidateAiEvaluation):
                obj.id = 42

        async def flush(self):
            return None

    row = await enqueue_candidate_evaluation(Session(), candidate_id=3, vacancy_id=8, source="test")
    assert row.id == 42
    assert any(isinstance(x, OutboxMessage) for x in added)
    outbox = next(x for x in added if isinstance(x, OutboxMessage))
    assert outbox.event_type == "hr.candidate.evaluate.requested"
    assert outbox.payload["candidate_id"] == 3
    assert outbox.payload["department"] == "логистический"


@pytest.mark.asyncio
async def test_enqueue_skips_without_vacancy():
    class Session:
        def add(self, obj):
            raise AssertionError("must not enqueue")

    assert await enqueue_candidate_evaluation(Session(), candidate_id=1, vacancy_id=None) is None


@pytest.mark.asyncio
async def test_apply_evaluation_result_updates_candidate():
    evaluation = CandidateAiEvaluation(
        id=5,
        candidate_id=11,
        vacancy_id=8,
        correlation_id="corr",
        source="test",
        status="pending",
    )
    candidate = SimpleNamespace(id=11, ai_score=None, ai_comment=None)

    class Session:
        async def get(self, model, pk):
            name = getattr(model, "__name__", "")
            if name == "CandidateAiEvaluation" or model is CandidateAiEvaluation:
                return evaluation
            return candidate

        async def commit(self):
            return None

    ok = await apply_evaluation_result(
        Session(),
        {"evaluation_id": 5, "correlation_id": "corr", "score": 88.4, "comment": "сильный водитель"},
    )
    assert ok is True
    assert evaluation.status == "completed"
    assert evaluation.score == 88
    assert candidate.ai_score == 88
    assert candidate.ai_comment == "сильный водитель"


@pytest.mark.asyncio
async def test_apply_evaluation_result_skips_already_completed():
    evaluation = CandidateAiEvaluation(
        id=5,
        candidate_id=11,
        vacancy_id=8,
        correlation_id="corr",
        source="test",
        status="completed",
        score=10,
        comment="old",
    )

    class Session:
        async def get(self, model, pk):
            return evaluation

        async def commit(self):
            raise AssertionError("must not rewrite a completed evaluation")

    ok = await apply_evaluation_result(
        Session(),
        {"evaluation_id": 5, "score": 99, "comment": "new"},
    )
    assert ok is True
    assert evaluation.score == 10
    assert evaluation.comment == "old"


@pytest.mark.asyncio
async def test_run_ai_eval_relay_skips_without_rabbit(monkeypatch):
    from app.worker import jobs

    monkeypatch.setattr(jobs, "AI_EVAL_RELAY_ENABLED", True)
    monkeypatch.setattr(jobs, "RABBITMQ_URL", "")
    stats = await jobs.run_ai_eval_relay()
    assert stats["skipped_reason"] == "no_rabbitmq"


@pytest.mark.asyncio
async def test_enqueue_returns_existing_pending():
    pending = CandidateAiEvaluation(
        id=7,
        candidate_id=3,
        vacancy_id=8,
        correlation_id="old",
        source="test",
        status="pending",
    )

    class Session:
        async def execute(self, stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: pending))

        def add(self, obj):
            raise AssertionError("must not enqueue a second pending evaluation")

    row = await enqueue_candidate_evaluation(Session(), candidate_id=3, vacancy_id=8)
    assert row is pending


@pytest.mark.asyncio
async def test_apply_evaluation_result_failed_status():
    evaluation = CandidateAiEvaluation(
        id=5,
        candidate_id=11,
        vacancy_id=8,
        correlation_id="corr",
        source="test",
        status="pending",
    )

    class Session:
        async def get(self, model, pk):
            return evaluation

        async def commit(self):
            return None

    ok = await apply_evaluation_result(
        Session(),
        {"evaluation_id": 5, "status": "failed", "error": "no summaries"},
    )
    assert ok is True
    assert evaluation.status == "failed"
    assert evaluation.error == "no summaries"


@pytest.mark.asyncio
async def test_apply_evaluation_result_missing_or_bad_id():
    class Session:
        async def get(self, model, pk):
            return None

        async def execute(self, stmt):
            return SimpleNamespace(scalar_one_or_none=lambda: None)

        async def commit(self):
            raise AssertionError("must not commit")

    assert await apply_evaluation_result(Session(), {"evaluation_id": "x", "correlation_id": ""}) is False
    assert await apply_evaluation_result(Session(), {"evaluation_id": 99, "correlation_id": "gone"}) is False


@pytest.mark.asyncio
async def test_list_pending_outbox_filters_request_event_type():
    from app.ai_eval.service import list_pending_outbox

    captured = {}

    class Session:
        async def execute(self, stmt):
            captured["sql"] = str(stmt.compile(compile_kwargs={"literal_binds": True}))
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    await list_pending_outbox(Session())
    assert "hr.candidate.evaluate.requested" in captured["sql"]


@pytest.mark.asyncio
async def test_run_ai_eval_relay_publishes_and_drains(monkeypatch):
    from app.worker import jobs
    from app.db.v1.models import OutboxMessage as Outbox

    row = Outbox(
        event_type="hr.candidate.evaluate.requested",
        correlation_id="c",
        payload={"correlation_id": "c"},
        status="pending",
        attempts=0,
    )
    row.id = 1

    class Sess:
        async def commit(self):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class Lock:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return True

        async def __aexit__(self, *a):
            return False

    published = []

    async def fake_list(db, *, limit=25, event_type=None):
        assert event_type == "hr.candidate.evaluate.requested"
        return [row]

    def fake_publish(**kwargs):
        published.append(kwargs)

    monkeypatch.setattr(jobs, "AI_EVAL_RELAY_ENABLED", True)
    monkeypatch.setattr(jobs, "RABBITMQ_URL", "amqp://guest:guest@localhost//")
    monkeypatch.setattr(jobs, "DistributedLock", Lock)
    monkeypatch.setattr(jobs, "AsyncSessionLocal", lambda: Sess())
    monkeypatch.setattr("app.ai_eval.service.list_pending_outbox", fake_list)
    monkeypatch.setattr("app.ai_eval.service.mark_outbox_published", AsyncMock())
    monkeypatch.setattr("app.messaging.rabbitmq.publish_json", fake_publish)
    monkeypatch.setattr("app.messaging.rabbitmq.drain_queue", lambda **k: 3)

    stats = await jobs.run_ai_eval_relay()
    assert stats["published"] == 1
    assert stats["consumed"] == 3
    assert published[0]["queue_name"] == jobs.RABBITMQ_QUEUE_CANDIDATE_EVALUATE_REQUEST


def test_decode_hr_message_payload_drops_poison():
    from app.messaging.rabbitmq import PermanentHandlerError, decode_message_payload

    class Msg:
        def __init__(self, body):
            self.body = body

    assert decode_message_payload(Msg(b'{"score": 12}')) == {"score": 12}
    with pytest.raises(PermanentHandlerError):
        decode_message_payload(Msg("{{{"))


@pytest.mark.asyncio
async def test_outbox_payload_roundtrip_to_candidate_score():
    added = []
    vacancy = SimpleNamespace(id=8, department=SimpleNamespace(value="логистический"))

    class EnqueueSession:
        async def execute(self, stmt):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: None))

        async def get(self, model, pk):
            return vacancy

        def add(self, obj):
            added.append(obj)
            if isinstance(obj, CandidateAiEvaluation):
                obj.id = 42

        async def flush(self):
            return None

    evaluation = await enqueue_candidate_evaluation(
        EnqueueSession(), candidate_id=11, vacancy_id=8, source="candidate.assigned"
    )
    request = next(x for x in added if isinstance(x, OutboxMessage)).payload
    assert request["event_type"] == "hr.candidate.evaluate.requested"
    assert set(request) >= {
        "correlation_id",
        "evaluation_id",
        "candidate_id",
        "vacancy_id",
        "department",
    }

    candidate = SimpleNamespace(id=11, ai_score=None, ai_comment=None)

    class ApplySession:
        async def get(self, model, pk):
            name = getattr(model, "__name__", "")
            if name == "CandidateAiEvaluation" or model is CandidateAiEvaluation:
                return evaluation
            return candidate

        async def commit(self):
            return None

    result_payload = {
        "event_type": "hr.candidate.evaluate.completed",
        "correlation_id": request["correlation_id"],
        "evaluation_id": request["evaluation_id"],
        "candidate_id": request["candidate_id"],
        "vacancy_id": request["vacancy_id"],
        "status": "completed",
        "score": 91,
        "comment": "совпадает с вакансией",
    }
    assert await apply_evaluation_result(ApplySession(), result_payload) is True
    assert candidate.ai_score == 91
    assert evaluation.status == "completed"


def test_ai_http_proxy_paths_match_ai_service_v1_base():
    from pathlib import Path

    src = Path(__file__).resolve().parents[1].joinpath("app", "endpoints", "v1", "ai.py").read_text(encoding="utf-8")
    assert 'ai.post("/v1/' not in src
    assert 'ai.post("/vacancy/description-salary-combine"' in src
    assert 'ai.post("/test/generate"' in src

