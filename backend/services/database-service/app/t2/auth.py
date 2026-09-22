"""Refresh T2 ATS OpenAPI access tokens (24h access / 7d refresh)."""
from __future__ import annotations

from typing import Optional

import httpx

from app.app_logging import logger
from app.config import (
    T2_ATS_AUTH_SCHEME,
    T2_ATS_BASE,
    T2_ATS_REFRESH_PATH,
    T2_ATS_TIMEOUT,
)
from app.repositories.t2_oauth_token_repository import T2OAuthTokenRepository
from app.t2.tokens import (
    T2TokenError,
    access_token_of,
    is_definitive_refresh_failure,
    merge_refreshed_payload,
    refresh_token_of,
    should_refresh_access,
)


def _auth_header(token: str) -> str:
    raw = (token or "").strip()
    if raw.lower().startswith("bearer "):
        return raw
    scheme = (T2_ATS_AUTH_SCHEME or "").strip()
    if scheme:
        return f"{scheme} {raw}"
    return raw


def _refresh_url() -> str:
    base = (T2_ATS_BASE or "").rstrip("/")
    path = T2_ATS_REFRESH_PATH if T2_ATS_REFRESH_PATH.startswith("/") else f"/{T2_ATS_REFRESH_PATH}"
    return f"{base}{path}"


async def request_t2_token_refresh(
    refresh_token: str,
    *,
    timeout: Optional[float] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> dict:
    token = (refresh_token or "").strip()
    if not token:
        raise T2TokenError("T2 refresh_token is empty")
    if not T2_ATS_BASE:
        raise T2TokenError("T2_ATS_BASE is empty")

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": _auth_header(token),
    }
    try:
        async with httpx.AsyncClient(timeout=timeout or T2_ATS_TIMEOUT, transport=transport) as client:
            response = await client.put(_refresh_url(), headers=headers)
    except httpx.RequestError as exc:
        logger.warning("T2 token refresh network error (tokens kept): %s", exc)
        raise T2TokenError(f"T2 token refresh network error: {exc}", keep_tokens=True) from exc

    if response.status_code >= 400:
        text = response.text[:500]
        keep = not is_definitive_refresh_failure(response.status_code, text)
        logger.error("T2 token refresh failed: %s %s", response.status_code, text)
        raise T2TokenError(
            f"T2 token refresh failed ({response.status_code}): {text}",
            status_code=response.status_code,
            keep_tokens=keep,
        )
    try:
        body = response.json()
    except ValueError as exc:
        raise T2TokenError("T2 token refresh returned non-JSON", keep_tokens=True) from exc
    if not isinstance(body, dict):
        raise T2TokenError("T2 token refresh returned unexpected payload", keep_tokens=True)
    return body


async def ensure_access_token(
    repo: T2OAuthTokenRepository,
    *,
    force: bool = False,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Optional[str]:
    """Return a live access token, refreshing via ATS when expired or near expiry."""
    row = await repo.get()
    payload = row.payload if row is not None and isinstance(row.payload, dict) else None
    access = access_token_of(payload)
    refresh = refresh_token_of(payload)
    if not should_refresh_access(payload, force=force):
        return access
    if not refresh:
        return access

    logger.info("T2 access token refresh started")
    body = await request_t2_token_refresh(refresh, transport=transport)
    merged = merge_refreshed_payload(payload, body)
    await repo.upsert(merged)
    logger.info("T2 access token refreshed")
    return access_token_of(merged)
