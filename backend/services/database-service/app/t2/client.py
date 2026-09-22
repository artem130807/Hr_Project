"""HTTP client for T2 ATS OpenAPI (call-records list + STT)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import httpx

from app.config import T2_ATS_AUTH_SCHEME, T2_ATS_BASE, T2_ATS_TIMEOUT, T2_CALL_SYNC_PAGE_SIZE


class T2AtsError(Exception):
    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class T2AtsClient:
    def __init__(
        self,
        *,
        access_token: str,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        auth_scheme: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        token = (access_token or "").strip()
        if not token:
            raise T2AtsError("T2 access token is empty")
        self.access_token = token
        self.base_url = (base_url or T2_ATS_BASE).rstrip("/")
        self.timeout = timeout if timeout is not None else T2_ATS_TIMEOUT
        self.auth_scheme = (auth_scheme if auth_scheme is not None else T2_ATS_AUTH_SCHEME).strip()
        self._transport = transport

    def _auth_header(self) -> str:
        token = self.access_token
        if token.lower().startswith("bearer "):
            return token
        if self.auth_scheme:
            return f"{self.auth_scheme} {token}"
        return token

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": self._auth_header(),
        }

    def _url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        suffix = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{suffix}"

    async def _get(self, path: str, params: Optional[dict] = None) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                transport=self._transport,
            ) as client:
                response = await client.get(self._url(path), headers=self._headers(), params=params)
            return response
        except httpx.RequestError as exc:
            raise T2AtsError(f"T2 request failed: {exc}") from exc

    @staticmethod
    def _iso(dt: datetime) -> str:
        if dt.tzinfo is None:
            return dt.isoformat()
        return dt.isoformat()

    @staticmethod
    def unwrap_records(payload: Any) -> list[dict]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        for key in ("content", "items", "data", "records", "callRecords"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if payload.get("filename") or payload.get("recordFileName") or payload.get("uuid"):
            return [payload]
        return []

    async def list_call_records(
        self,
        *,
        start: datetime,
        end: datetime,
        page: int = 0,
        size: Optional[int] = None,
        is_recorded: bool = True,
    ) -> list[dict]:
        params = {
            "start": self._iso(start),
            "end": self._iso(end),
            "page": page,
            "size": size or T2_CALL_SYNC_PAGE_SIZE,
            "is_recorded": str(is_recorded).lower(),
            "sort": "date,DESC",
        }
        response = await self._get("/call-records/info", params=params)
        if response.status_code >= 400:
            raise T2AtsError(
                f"T2 call-records/info failed ({response.status_code}): {response.text[:500]}",
                status_code=response.status_code,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise T2AtsError("T2 call-records/info returned non-JSON") from exc
        return self.unwrap_records(payload)

    async def get_transcript(self, filename: str) -> list[dict]:
        if not filename:
            return []
        response = await self._get("/call-records/file/stt", params={"filename": filename})
        if response.status_code == 404:
            return []
        if response.status_code >= 400:
            raise T2AtsError(
                f"T2 call-records/file/stt failed ({response.status_code}): {response.text[:500]}",
                status_code=response.status_code,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise T2AtsError("T2 STT returned non-JSON") from exc
        from app.t2.mapping import extract_transcript_words

        return extract_transcript_words(payload)
