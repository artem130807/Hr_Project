"""Parse and merge T2 ATS OpenAPI token payloads."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.config import T2_ACCESS_TTL_SECONDS, T2_REFRESH_SKEW_SECONDS


class T2TokenError(Exception):
    def __init__(self, message: str, *, status_code: Optional[int] = None, keep_tokens: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.keep_tokens = keep_tokens


def _as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_expires(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def jwt_exp(token: str) -> Optional[datetime]:
    parts = (token or "").split(".")
    if len(parts) != 3:
        return None
    payload = parts[1]
    pad = "=" * (-len(payload) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(payload + pad))
    except (ValueError, json.JSONDecodeError):
        return None
    exp = data.get("exp") if isinstance(data, dict) else None
    if exp is None:
        return None
    try:
        return datetime.fromtimestamp(int(exp), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def access_token_of(payload: Optional[dict]) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    return _as_str(payload.get("access_token") or payload.get("accessToken"))


def refresh_token_of(payload: Optional[dict]) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    return _as_str(payload.get("refresh_token") or payload.get("refreshToken"))


def access_expires_at(payload: Optional[dict]) -> Optional[datetime]:
    if not isinstance(payload, dict):
        return None
    expires = parse_expires(payload.get("token_expires") or payload.get("tokenExpires"))
    if expires is not None:
        return expires
    access = access_token_of(payload)
    return jwt_exp(access) if access else None


def seconds_until_expiry(payload: Optional[dict], *, now: Optional[datetime] = None) -> Optional[float]:
    expires = access_expires_at(payload)
    if expires is None:
        return None
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return (expires - current).total_seconds()


def should_refresh_access(
    payload: Optional[dict],
    *,
    now: Optional[datetime] = None,
    skew_seconds: Optional[int] = None,
    force: bool = False,
) -> bool:
    if not refresh_token_of(payload):
        return False
    if force:
        return True
    remaining = seconds_until_expiry(payload, now=now)
    if remaining is None:
        return True
    skew = T2_REFRESH_SKEW_SECONDS if skew_seconds is None else skew_seconds
    return remaining <= skew


def merge_refreshed_payload(
    previous: Optional[dict],
    body: dict,
    *,
    now: Optional[datetime] = None,
) -> dict:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    access = _as_str(body.get("accessToken") or body.get("access_token"))
    refresh = _as_str(body.get("refreshToken") or body.get("refresh_token"))
    if not access:
        raise T2TokenError("T2 refresh response has no accessToken")
    expires = parse_expires(body.get("token_expires") or body.get("expiresAt"))
    if expires is None:
        expires_in = body.get("expires_in") or body.get("expiresIn")
        if expires_in is not None:
            try:
                expires = current + timedelta(seconds=int(expires_in))
            except (TypeError, ValueError):
                expires = None
    if expires is None:
        expires = jwt_exp(access) or (current + timedelta(seconds=T2_ACCESS_TTL_SECONDS))
    merged = dict(previous) if isinstance(previous, dict) else {}
    merged["access_token"] = access
    merged["refresh_token"] = refresh or refresh_token_of(previous) or ""
    merged["token_expires"] = expires.isoformat()
    return merged


def is_definitive_refresh_failure(status_code: int, text: str) -> bool:
    if status_code not in (400, 401, 403):
        return False
    msg = (text or "").lower()
    needles = (
        "token is expired",
        "bad token",
        "invalid token type",
        "authorization header required",
        "object not found",
    )
    return any(n in msg for n in needles)
