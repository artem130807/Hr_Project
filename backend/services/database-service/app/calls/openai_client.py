"""OpenAI Chat Completions client for WhisperAi (httpx, no SDK)."""
from __future__ import annotations

from typing import Any, Optional

import httpx

from app.calls.whisper import WHISPER_SYSTEM_PROMPT, parse_whisper_payload
from app.config import CALL_WHISPER_MODEL, CALL_WHISPER_TIMEOUT, OPENAI_API_BASE, OPENAI_API_TOKEN


class WhisperAiError(Exception):
    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class WhisperAiClient:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.api_key = (api_key if api_key is not None else OPENAI_API_TOKEN).strip()
        if not self.api_key:
            raise WhisperAiError("OPENAI_API_TOKEN is empty")
        self.base_url = (base_url or OPENAI_API_BASE).rstrip("/")
        self.model = (model or CALL_WHISPER_MODEL).strip() or "gpt-4o-mini"
        self.timeout = timeout if timeout is not None else CALL_WHISPER_TIMEOUT
        self._transport = transport

    async def classify(self, user_prompt: str) -> dict:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": WHISPER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as client:
                response = await client.post(url, headers=headers, json=body)
        except httpx.RequestError as exc:
            raise WhisperAiError(f"OpenAI network error: {exc}") from exc

        if response.status_code >= 400:
            raise WhisperAiError(
                f"OpenAI error ({response.status_code}): {response.text[:400]}",
                status_code=response.status_code,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise WhisperAiError("OpenAI returned non-JSON") from exc
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise WhisperAiError("OpenAI response missing choices") from exc
        return parse_whisper_payload(content or "")
