"""ERP users API client (list + admin create via caller JWT)."""
from __future__ import annotations

from typing import Any, Optional

import httpx
from fastapi import HTTPException

from app.config import (
    ERP_API_KEY,
    ERP_API_KEY_HEADER,
    ERP_BASE,
    ERP_BEARER_TOKEN,
    ERP_HTTP_TIMEOUT,
    ERP_USERS_PATH,
)
from app.app_logging import logger
from app.erp.mapper import map_role


class ErpClient:
    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        self.base_url = (base_url or ERP_BASE).rstrip("/")
        self.timeout = timeout if timeout is not None else ERP_HTTP_TIMEOUT

    def _headers(self, *, access_token: Optional[str] = None) -> dict:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        token = (access_token or "").strip() or ERP_BEARER_TOKEN
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if ERP_API_KEY:
            headers[ERP_API_KEY_HEADER] = ERP_API_KEY
        return headers

    def _users_url(self) -> str:
        if not self.base_url:
            raise RuntimeError("ERP_BASE is not configured")
        path = ERP_USERS_PATH if ERP_USERS_PATH.startswith("/") else f"/{ERP_USERS_PATH}"
        if not path.endswith("/"):
            path = f"{path}/"
        return f"{self.base_url}{path}"

    def _roles_url(self) -> str:
        return f"{self._users_url().rstrip('/')}/roles"

    def _normalize_page(self, payload: Any) -> tuple[list, Optional[str]]:
        if isinstance(payload, list):
            return payload, None
        if not isinstance(payload, dict):
            return [], None
        for key in ("results", "items", "data", "users"):
            if isinstance(payload.get(key), list):
                nxt = payload.get("next") or payload.get("next_url")
                return payload[key], str(nxt) if nxt else None
        return [], None

    def _raise_erp(self, response: httpx.Response, action: str) -> None:
        detail: Any
        try:
            detail = response.json()
        except Exception:
            detail = response.text or f"ERP {action} failed"
        if isinstance(detail, dict) and "detail" in detail:
            detail = detail["detail"]
        code = response.status_code
        if code in (400, 401, 403, 404, 409, 422):
            raise HTTPException(status_code=code, detail=detail)
        raise HTTPException(
            status_code=502,
            detail=f"ERP {action} failed ({code}): {detail}",
        )

    async def list_users(self, *, access_token: Optional[str] = None) -> list[dict]:
        url = self._users_url()
        users: list[dict] = []
        pages = 0
        max_pages = 50

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._headers(access_token=access_token),
        ) as client:
            while url and pages < max_pages:
                pages += 1
                logger.info(f"Fetching ERP users page {pages}: {url}")
                response = await client.get(url)
                response.raise_for_status()
                page_users, next_url = self._normalize_page(response.json())
                users.extend([u for u in page_users if isinstance(u, dict)])
                if next_url and next_url.startswith("http"):
                    url = next_url
                elif next_url:
                    url = f"{self.base_url}{next_url if next_url.startswith('/') else '/' + next_url}"
                else:
                    url = None

        logger.info(f"ERP returned {len(users)} user records across {pages} page(s)")
        return users

    async def list_roles(self, *, access_token: Optional[str] = None) -> list[dict]:
        url = self._roles_url()
        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._headers(access_token=access_token),
        ) as client:
            response = await client.get(url)
        if response.status_code >= 400:
            self._raise_erp(response, "list roles")
        payload = response.json()
        if isinstance(payload, list):
            return [r for r in payload if isinstance(r, dict)]
        return []

    async def resolve_role_id(
        self,
        role_key: Optional[str],
        *,
        access_token: Optional[str] = None,
    ) -> Optional[int]:
        """Map HR panel role slug (hr, manager, …) to ERP role_id."""
        key = (role_key or "").strip().lower()
        if not key:
            return None
        roles = await self.list_roles(access_token=access_token)
        for raw in roles:
            rid = raw.get("id")
            if rid is None:
                continue
            mapped = map_role(raw)
            if mapped == key:
                return int(rid)
            name = str(raw.get("name") or "").strip().lower()
            if name == key:
                return int(rid)
        return None

    def _require_user_token(self, access_token: Optional[str], action: str) -> str:
        token = (access_token or "").strip() or (ERP_BEARER_TOKEN or "").strip()
        if not token:
            raise HTTPException(
                503,
                f"Нужен ERP access token пользователя (или ERP_BEARER_TOKEN) для {action}",
            )
        return token

    async def create_user(
        self,
        payload: dict,
        *,
        access_token: Optional[str] = None,
    ) -> dict:
        """POST /api/v2/users/ — requires callers with users.admin (ERP JWT)."""
        url = self._users_url()
        token = self._require_user_token(access_token, "создания учётки")
        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._headers(access_token=token),
        ) as client:
            response = await client.post(url, json=payload)
        if response.status_code >= 400:
            self._raise_erp(response, "create user")
        data = response.json()
        if not isinstance(data, dict):
            raise HTTPException(502, "ERP create user returned invalid payload")
        return data

    async def update_user(
        self,
        user_id: str,
        payload: dict,
        *,
        access_token: Optional[str] = None,
    ) -> dict:
        """PUT /api/v2/users/{id} — admin update (name, email, role_id, …)."""
        uid = str(user_id or "").strip()
        if not uid:
            raise HTTPException(400, "user_id is required")
        url = f"{self._users_url().rstrip('/')}/{uid}"
        token = self._require_user_token(access_token, "редактирования учётки")
        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._headers(access_token=token),
        ) as client:
            response = await client.put(url, json=payload)
        if response.status_code >= 400:
            self._raise_erp(response, "update user")
        data = response.json()
        if not isinstance(data, dict):
            raise HTTPException(502, "ERP update user returned invalid payload")
        return data

    async def reset_user_password(
        self,
        user_id: str,
        *,
        access_token: Optional[str] = None,
    ) -> dict:
        """POST /api/v2/users/{id}/reset-password."""
        uid = str(user_id or "").strip()
        if not uid:
            raise HTTPException(400, "user_id is required")
        url = f"{self._users_url().rstrip('/')}/{uid}/reset-password"
        token = self._require_user_token(access_token, "сброса пароля")
        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._headers(access_token=token),
        ) as client:
            response = await client.post(url)
        if response.status_code >= 400:
            self._raise_erp(response, "reset password")
        data = response.json()
        if not isinstance(data, dict):
            raise HTTPException(502, "ERP reset password returned invalid payload")
        return data
