"""AIClient unit tests with mocked OpenAI (no real API calls)."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from openai import BadRequestError

from app.agent.v1.errors import AIGenerationError
from app.agent.v1.ai_client import AIClient
from app.schemas.v1.vacancies import VacancyDescriptionResponse


def _fake_completion(content: str):
    choice = MagicMock()
    choice.message.content = content
    usage = MagicMock(total_tokens=10, prompt_tokens=4, completion_tokens=6)
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


@pytest.mark.asyncio
async def test_generate_text_success():
    with patch("app.agent.v1.ai_client.AsyncOpenAI") as MockOA:
        mock_client = MockOA.return_value
        mock_client.chat.completions.create = AsyncMock(
            return_value=_fake_completion("hello")
        )
        with patch("app.agent.v1.ai_client.get_outbound_proxy_url", return_value=None):
            ai = AIClient(api_key="k", model="gpt-4o-mini")
        result = await ai.generate("say hi")
    assert result == "hello"


@pytest.mark.asyncio
async def test_generate_structured_success():
    payload = {"description": "x" * 220}
    with patch("app.agent.v1.ai_client.AsyncOpenAI") as MockOA:
        mock_client = MockOA.return_value
        mock_client.chat.completions.create = AsyncMock(
            return_value=_fake_completion(json.dumps(payload))
        )
        with patch("app.agent.v1.ai_client.get_outbound_proxy_url", return_value=None):
            ai = AIClient(api_key="k", model="gpt-4o-mini")
        result = await ai.generate("desc", output_model=VacancyDescriptionResponse)
    assert isinstance(result, VacancyDescriptionResponse)
    assert result.description.startswith("x")
    fmt = mock_client.chat.completions.create.await_args.kwargs["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True


@pytest.mark.asyncio
async def test_generate_web_search_prefixes_prompt():
    with patch("app.agent.v1.ai_client.AsyncOpenAI") as MockOA:
        mock_client = MockOA.return_value
        mock_client.chat.completions.create = AsyncMock(
            return_value=_fake_completion("ok")
        )
        with patch("app.agent.v1.ai_client.get_outbound_proxy_url", return_value=None):
            ai = AIClient(api_key="k", model="gpt-4o-mini")
        await ai.generate("base", use_web_search=True)
    sent = mock_client.chat.completions.create.await_args.kwargs["messages"][0]["content"]
    assert "веб-источники" in sent
    assert "base" in sent


@pytest.mark.asyncio
async def test_generate_bad_request_raises():
    err = BadRequestError(
        message="bad",
        response=MagicMock(status_code=400, headers={}),
        body=None,
    )
    with patch("app.agent.v1.ai_client.AsyncOpenAI") as MockOA:
        mock_client = MockOA.return_value
        mock_client.chat.completions.create = AsyncMock(side_effect=err)
        with patch("app.agent.v1.ai_client.get_outbound_proxy_url", return_value=None):
            ai = AIClient(api_key="k", model="gpt-4o-mini")
        with pytest.raises(AIGenerationError):
            await ai.generate("x", output_model=VacancyDescriptionResponse)


@pytest.mark.asyncio
async def test_generate_invalid_json_raises():
    with patch("app.agent.v1.ai_client.AsyncOpenAI") as MockOA:
        mock_client = MockOA.return_value
        mock_client.chat.completions.create = AsyncMock(
            return_value=_fake_completion("not-json{{{")
        )
        with patch("app.agent.v1.ai_client.get_outbound_proxy_url", return_value=None):
            ai = AIClient(api_key="k", model="gpt-4o-mini")
        with pytest.raises(AIGenerationError):
            await ai.generate("x", output_model=VacancyDescriptionResponse)


@pytest.mark.asyncio
async def test_generate_empty_content_raises():
    with patch("app.agent.v1.ai_client.AsyncOpenAI") as MockOA:
        mock_client = MockOA.return_value
        mock_client.chat.completions.create = AsyncMock(
            return_value=_fake_completion("")
        )
        with patch("app.agent.v1.ai_client.get_outbound_proxy_url", return_value=None):
            ai = AIClient(api_key="k", model="gpt-4o-mini")
        with pytest.raises(AIGenerationError):
            await ai.generate("x", output_model=VacancyDescriptionResponse)


@pytest.mark.asyncio
async def test_generate_retries_json_object_when_schema_rejected():
    err = BadRequestError(
        message="Invalid schema",
        response=MagicMock(status_code=400, headers={}),
        body=None,
    )
    payload = {"description": "x" * 220}
    with patch("app.agent.v1.ai_client.AsyncOpenAI") as MockOA:
        mock_client = MockOA.return_value
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[err, _fake_completion(json.dumps(payload))]
        )
        with patch("app.agent.v1.ai_client.get_outbound_proxy_url", return_value=None):
            ai = AIClient(api_key="k", model="gpt-4o-mini")
        result = await ai.generate("desc", output_model=VacancyDescriptionResponse)
    assert result.description.startswith("x")
    assert mock_client.chat.completions.create.await_count == 2
    second = mock_client.chat.completions.create.await_args_list[1].kwargs["response_format"]
    assert second == {"type": "json_object"}
