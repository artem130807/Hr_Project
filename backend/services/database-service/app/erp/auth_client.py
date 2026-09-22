"""HTTP client for erp-backend auth endpoints (login / refresh / logout / me)."""
from __future__ import annotations

from typing import Any, Optional

import httpx
from fastapi import HTTPException, status

from app.app_logging import logger
from app.config import (
    ERP_AUTH_LOGOUT_PATH,
    ERP_AUTH_ME_PATH,
    ERP_AUTH_REFRESH_PATH,
    ERP_AUTH_TOKEN_PATH,
    ERP_BASE,
    ERP_HTTP_TIMEOUT,
)


class ErpAuthError(Exception):
    def __init__(self, message: str, status_code: int = 502, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail if detail is not None else message


def _auth_base() -> str:
    if not ERP_BASE:
        raise ErpAuthError("ERP_BASE is not configured", status_code=503)
    return ERP_BASE.rstrip("/")


def _path(configured: str) -> str:
    return configured if configured.startswith("/") else f"/{configured}"


def _raise_from_response(response: httpx.Response, action: str) -> None:
    detail: Any
    try:
        detail = response.json()
    except Exception:
        detail = response.text or f"ERP {action} failed"
    if isinstance(detail, dict) and "detail" in detail:
        detail = detail["detail"]
    code = response.status_code
    if code in (401, 403, 404):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(detail) if not isinstance(detail, str) else detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
    raise ErpAuthError(f"ERP {action} failed ({code})", status_code=502, detail=detail)


async def erp_login(
    username: str,
    password: str,
    *,
    user_agent: Optional[str] = None,
    ip: Optional[str] = None,
    timeout: Optional[float] = None,
) -> dict:
    url = f"{_auth_base()}{_path(ERP_AUTH_TOKEN_PATH)}"
    headers = {"Accept": "application/json"}
    if user_agent:
        headers["User-Agent"] = user_agent
    if ip:
        headers["X-Forwarded-For"] = ip
    data = {"username": username, "password": password, "grant_type": "password"}
    try:
        async with httpx.AsyncClient(timeout=timeout or ERP_HTTP_TIMEOUT) as client:
            response = await client.post(url, data=data, headers=headers)
    except httpx.HTTPError as exc:
        logger.error(f"ERP login transport error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ERP auth service unavailable",
        ) from exc

    if response.status_code >= 400:
        logger.warning(f"ERP login rejected: {response.status_code}")
        _raise_from_response(response, "login")
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ERP login returned invalid payload",
        )
    return payload


async def erp_refresh(
    refresh_token: str,
    *,
    timeout: Optional[float] = None,
) -> dict:
    url = f"{_auth_base()}{_path(ERP_AUTH_REFRESH_PATH)}"
    try:
        async with httpx.AsyncClient(timeout=timeout or ERP_HTTP_TIMEOUT) as client:
            response = await client.post(url, json={"refresh_token": refresh_token})
    except httpx.HTTPError as exc:
        logger.error(f"ERP refresh transport error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ERP auth service unavailable",
        ) from exc

    if response.status_code >= 400:
        _raise_from_response(response, "refresh")
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ERP refresh returned invalid payload",
        )
    return payload


async def erp_logout(
    refresh_token: str,
    *,
    timeout: Optional[float] = None,
) -> None:
    url = f"{_auth_base()}{_path(ERP_AUTH_LOGOUT_PATH)}"
    try:
        async with httpx.AsyncClient(timeout=timeout or ERP_HTTP_TIMEOUT) as client:
            response = await client.post(url, json={"refresh_token": refresh_token})
    except httpx.HTTPError as exc:
        logger.warning(f"ERP logout transport error (ignored): {exc}")
        return

    if response.status_code >= 400:
        logger.warning(f"ERP logout rejected: {response.status_code} {response.text[:200]}")


async def erp_me(
    access_token: str,
    *,
    timeout: Optional[float] = None,
) -> dict:
    url = f"{_auth_base()}{_path(ERP_AUTH_ME_PATH)}"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=timeout or ERP_HTTP_TIMEOUT) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        logger.error(f"ERP /me transport error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ERP auth service unavailable",
        ) from exc

    if response.status_code >= 400:
        _raise_from_response(response, "me")
    payload = response.json()
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ERP /me returned invalid payload",
        )
    return payload
