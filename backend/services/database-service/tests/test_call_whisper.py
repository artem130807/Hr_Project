from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.calls.openai_client import WhisperAiClient, WhisperAiError
from app.calls.whisper import (
    build_user_prompt,
    heuristic_without_transcript,
    map_status,
    normalize_description,
    parse_whisper_payload,
)
from app.db.v1.enums import CallConversationStatus

ALLOWED_LINE = "+79020013728"


def _pending_row(**kwargs):
    defaults = dict(
        caller_number=ALLOWED_LINE,
        operator_number="+79007654321",
        payload={"transcript": []},
        duration=90,
        ats_status="ANSWERED",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_map_status_accepts_codes_and_russian():
    assert map_status("interested") == "interested"
    assert map_status("Интерес") == "interested"
    assert map_status("собеседование") == "interview"
    assert map_status("Перезвон") == "callback"
    assert map_status("Отказ") == "rejected"
    assert map_status("Сброс") == "dropped"
    assert map_status("pending") is None
    assert map_status("не интересно") is None


def test_parse_whisper_payload_and_description_style():
    parsed = parse_whisper_payload(
        '{"status":"rejected","description":"Отказ: не готов к ночным сменам и выездам на линию"}'
    )
    assert parsed["status"] == CallConversationStatus.rejected.value
    assert parsed["description"] == "Отказ: не готов к ночным сменам и выездам на линию."

    fenced = parse_whisper_payload(
        '```json\n{"status":"callback","description":"Перезвон: уточняла удалёнку. Попросила перезвонить после 18:00."}\n```'
    )
    assert fenced["status"] == "callback"
    assert "18:00" in fenced["description"]


def test_normalize_description_fallback_and_trim():
    text = normalize_description("", status="dropped")
    assert text.startswith("Сброс:")
    long = "слово " * 80
    trimmed = normalize_description(long, status="interested")
    assert len(trimmed) <= 181
    assert trimmed.endswith("…") or trimmed.endswith(".")


def test_heuristic_dropped_without_transcript():
    unanswered = SimpleNamespace(payload={"transcript": []}, duration=40, ats_status="NOT_ANSWERED_COMMON")
    short = SimpleNamespace(payload={"transcript": []}, duration=5, ats_status="ANSWERED")
    waiting = SimpleNamespace(payload={"transcript": []}, duration=90, ats_status="ANSWERED")
    with_words = SimpleNamespace(
        payload={"transcript": [{"channel": "A", "word": "алло", "startTime": 0, "endTime": 1}]},
        duration=5,
        ats_status="ANSWERED",
    )
    assert heuristic_without_transcript(unanswered)["status"] == "dropped"
    assert heuristic_without_transcript(short)["status"] == "dropped"
    assert heuristic_without_transcript(waiting) is None
    assert heuristic_without_transcript(with_words) is None


def test_build_user_prompt_contains_turns():
    row = SimpleNamespace(
        duration=120,
        ats_status="ANSWERED",
        direction="incoming",
        payload={
            "transcript": [
                {"channel": "B", "startTime": 0.3, "endTime": 1.0, "word": "добрый"},
                {"channel": "B", "startTime": 1.0, "endTime": 1.4, "word": "день"},
                {"channel": "A", "startTime": 3.0, "endTime": 3.8, "word": "перезвоните"},
                {"channel": "A", "startTime": 3.8, "endTime": 4.5, "word": "вечером"},
            ]
        },
    )
    prompt = build_user_prompt(row)
    assert "HR:" in prompt
    assert "Кандидат:" in prompt
    assert "перезвоните" in prompt


@pytest.mark.asyncio
async def test_openai_client_posts_chat_completions():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["Authorization"]
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"status":"interview","description":"Перенос вчерашней встречи на 12:00 из-за медкомиссии."}'
                        }
                    }
                ]
            },
        )

    client = WhisperAiClient(
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        transport=httpx.MockTransport(handler),
    )
    result = await client.classify("диалог")
    assert captured["url"].endswith("/chat/completions")
    assert captured["auth"] == "Bearer sk-test"
    assert "WhisperAi" in captured["body"] or "json_object" in captured["body"]
    assert result["status"] == "interview"
    assert "медкомиссии" in result["description"]


@pytest.mark.asyncio
async def test_openai_client_raises_on_429():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate")

    client = WhisperAiClient(api_key="sk-test", transport=httpx.MockTransport(handler))
    with pytest.raises(WhisperAiError) as exc:
        await client.classify("x")
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_classify_pending_uses_heuristic_and_api(monkeypatch):
    from app.calls import classify as classify_mod

    rows = [
        _pending_row(id=1, payload={"transcript": []}, duration=3, ats_status="ANSWERED"),
        _pending_row(
            id=2,
            duration=80,
            ats_status="ANSWERED",
            direction="incoming",
            payload={
                "transcript": [
                    {"channel": "A", "startTime": 0, "endTime": 1, "word": "не"},
                    {"channel": "A", "startTime": 1, "endTime": 2, "word": "подходит"},
                    {"channel": "A", "startTime": 2, "endTime": 3, "word": "ночь"},
                ]
            },
        ),
        _pending_row(id=3, payload={"transcript": []}, duration=90, ats_status="ANSWERED"),
    ]

    class Repo:
        def __init__(self, db):
            pass

        async def list_pending(self, *, limit=8):
            return rows[:limit]

        async def apply_whisper_result(self, conversation_id, *, status, description):
            return True

    class FakeAi:
        async def classify(self, prompt):
            assert "ночь" in prompt
            return {
                "status": "rejected",
                "description": "Отказ: не готов к ночным сменам и выездам на линию.",
            }

    monkeypatch.setattr(classify_mod, "CallConversationRepository", Repo)
    monkeypatch.setattr(classify_mod.asyncio, "sleep", AsyncMock())
    stats = await classify_mod.classify_pending_conversations(
        MagicMock(),
        client=FakeAi(),
        delay_seconds=0.01,
    )
    assert stats["fetched"] == 3
    assert stats["heuristic"] == 1
    assert stats["classified"] == 2
    assert stats["waiting_stt"] == 1


@pytest.mark.asyncio
async def test_classify_stops_on_rate_limit(monkeypatch):
    from app.calls import classify as classify_mod

    class Repo:
        def __init__(self, db):
            pass

        async def list_pending(self, *, limit=8):
            return [
                _pending_row(
                    id=n,
                    duration=30,
                    ats_status="ANSWERED",
                    payload={"transcript": [{"channel": "A", "word": "привет", "startTime": 0, "endTime": 1}]},
                )
                for n in (1, 2)
            ]

        async def apply_whisper_result(self, *a, **k):
            return True

    class FakeAi:
        async def classify(self, prompt):
            raise WhisperAiError("rate", status_code=429)

    monkeypatch.setattr(classify_mod, "CallConversationRepository", Repo)
    stats = await classify_mod.classify_pending_conversations(MagicMock(), client=FakeAi(), delay_seconds=0)
    assert stats["errors"] == 1
    assert stats["classified"] == 0


@pytest.mark.asyncio
async def test_classify_skips_calls_without_company_line(monkeypatch):
    from app.calls import classify as classify_mod

    classified_ids = []

    class Repo:
        def __init__(self, db):
            pass

        async def list_pending(self, *, limit=8):
            return [
                _pending_row(
                    id=1,
                    caller_number="+79992140831",
                    operator_number="+79000000000",
                    duration=40,
                    payload={"transcript": [{"channel": "A", "word": "алло", "startTime": 0, "endTime": 1}]},
                ),
                _pending_row(
                    id=2,
                    caller_number="+7 903 551-77-02",
                    operator_number="+7 902 001 37 28",
                    duration=40,
                    payload={"transcript": [{"channel": "A", "word": "вахта", "startTime": 0, "endTime": 1}]},
                ),
            ]

        async def apply_whisper_result(self, conversation_id, *, status, description):
            classified_ids.append(conversation_id)
            return True

    class FakeAi:
        async def classify(self, prompt):
            assert "вахта" in prompt
            assert "алло" not in prompt
            return {"status": "interested", "description": "Интерес: уточнял вахту."}

    monkeypatch.setattr(classify_mod, "CallConversationRepository", Repo)
    stats = await classify_mod.classify_pending_conversations(
        MagicMock(), client=FakeAi(), delay_seconds=0
    )
    assert stats["skipped_phone"] == 1
    assert stats["classified"] == 1
    assert classified_ids == [2]


@pytest.mark.asyncio
async def test_repository_list_pending_and_apply():
    from app.repositories.call_conversation_repository import CallConversationRepository

    pending = SimpleNamespace(
        id=7,
        status="pending",
        description=None,
        caller_number=ALLOWED_LINE,
        operator_number="+79007654321",
    )
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [pending]
    db.execute = AsyncMock(return_value=result)
    db.get = AsyncMock(return_value=pending)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    repo = CallConversationRepository(db)
    listed = await repo.list_pending(limit=4)
    assert listed[0].id == 7
    ok = await repo.apply_whisper_result(7, status="callback", description="Перезвон: после 18:00.")
    assert ok is True
    assert pending.status == "callback"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_apply_whisper_skips_non_pending():
    from app.repositories.call_conversation_repository import CallConversationRepository

    row = SimpleNamespace(id=7, status="rejected", description="уже")
    db = MagicMock()
    db.get = AsyncMock(return_value=row)
    db.commit = AsyncMock()
    repo = CallConversationRepository(db)
    assert await repo.apply_whisper_result(7, status="interested", description="x") is False
    db.commit.assert_not_called()
    assert row.status == "rejected"


@pytest.mark.asyncio
async def test_apply_whisper_skips_unrelated_phone():
    from app.repositories.call_conversation_repository import CallConversationRepository

    row = SimpleNamespace(
        id=7,
        status="pending",
        description=None,
        caller_number="+79992140831",
        operator_number="+79000000000",
    )
    db = MagicMock()
    db.get = AsyncMock(return_value=row)
    db.commit = AsyncMock()
    repo = CallConversationRepository(db)
    assert await repo.apply_whisper_result(7, status="interested", description="x") is False
    db.commit.assert_not_called()
    assert row.status == "pending"
