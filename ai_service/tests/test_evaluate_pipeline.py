from unittest.mock import AsyncMock, patch

import pytest

from app.evaluate.pipeline import (
    _summary_from_api,
    handle_evaluate_request,
)
from app.messaging.rabbit import PermanentHandlerError, decode_message_payload
from app.schemas.v1.candidates import CandidateEvaluateResponse


def test_summary_from_api_uses_text_field_not_dict_repr():
    assert _summary_from_api({"id": 3, "text": " резюме "}) == "резюме"
    assert _summary_from_api({"id": 3}) == ""
    assert _summary_from_api(None) == ""
    assert _summary_from_api("plain") == "plain"


def test_decode_message_payload_rejects_poison():
    class Msg:
        def __init__(self, body):
            self.body = body

    assert decode_message_payload(Msg('{"score": 1}')) == {"score": 1}
    with pytest.raises(PermanentHandlerError):
        decode_message_payload(Msg("not-json"))
    with pytest.raises(PermanentHandlerError):
        decode_message_payload(Msg("[1,2]"))


@pytest.mark.asyncio
async def test_handle_missing_correlation_is_poison():
    with pytest.raises(PermanentHandlerError):
        await handle_evaluate_request({"candidate_id": 1})


@pytest.mark.asyncio
async def test_handle_skips_openai_when_result_already_queued():
    payload = {"correlation_id": "c1", "candidate_id": 1, "vacancy_id": 2}
    with patch("app.evaluate.pipeline._result_already_queued", AsyncMock(return_value=True)), patch(
        "app.evaluate.pipeline.candidate_service.evaluate_candidate", AsyncMock()
    ) as evaluate:
        result = await handle_evaluate_request(payload)
    assert result is None
    evaluate.assert_not_called()


@pytest.mark.asyncio
async def test_handle_writes_failed_outbox_without_summaries():
    payload = {"correlation_id": "c2", "candidate_id": 1, "vacancy_id": 2}
    with patch("app.evaluate.pipeline._result_already_queued", AsyncMock(return_value=False)), patch(
        "app.evaluate.pipeline._load_summaries", AsyncMock(return_value=("", "", "", ""))
    ), patch("app.evaluate.pipeline._enqueue_result", AsyncMock()) as enqueue:
        result = await handle_evaluate_request(payload)
    assert result is None
    enqueue.assert_awaited()
    extra = enqueue.await_args.args[1]
    assert extra["status"] == "failed"


@pytest.mark.asyncio
async def test_handle_does_not_fail_outbox_on_transient_summary_error():
    payload = {"correlation_id": "c4"}
    with patch("app.evaluate.pipeline._result_already_queued", AsyncMock(return_value=False)), patch(
        "app.evaluate.pipeline._load_summaries",
        AsyncMock(side_effect=RuntimeError("candidate summary unavailable")),
    ), patch("app.evaluate.pipeline._enqueue_result", AsyncMock()) as enqueue:
        with pytest.raises(RuntimeError):
            await handle_evaluate_request(payload)
    enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_handle_writes_completed_outbox():
    payload = {"correlation_id": "c3", "evaluation_id": 9}
    scored = CandidateEvaluateResponse(score=77, comment="ok")
    with patch("app.evaluate.pipeline._result_already_queued", AsyncMock(return_value=False)), patch(
        "app.evaluate.pipeline._load_summaries",
        AsyncMock(return_value=("cand", "vac", "co", "dep")),
    ), patch(
        "app.evaluate.pipeline.candidate_service.evaluate_candidate",
        AsyncMock(return_value=scored),
    ), patch("app.evaluate.pipeline._enqueue_result", AsyncMock()) as enqueue:
        result = await handle_evaluate_request(payload)
    assert result is scored
    extra = enqueue.await_args.args[1]
    assert extra["status"] == "completed"
    assert extra["score"] == 77
