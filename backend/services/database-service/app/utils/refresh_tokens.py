"""Local HR refresh tokens removed — sessions are owned by erp-backend."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

REFRESH_TOKEN_BYTES = 32


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_refresh_token_active(token: object) -> bool:
    revoked_at = getattr(token, "revoked_at", None)
    expires_at = getattr(token, "expires_at", None)
    if revoked_at is not None:
        return False
    if expires_at is None:
        return False
    now = datetime.now(timezone.utc)
    if getattr(expires_at, "tzinfo", None) is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > now


async def issue_refresh_token(*args, **kwargs):
    raise RuntimeError("Local refresh tokens removed; use ERP auth proxy")


async def rotate_refresh_token(*args, **kwargs):
    raise RuntimeError("Local refresh tokens removed; use ERP auth proxy")


async def revoke_refresh_token(*args, **kwargs):
    return None


async def revoke_all_user_refresh_tokens(*args, **kwargs):
    return None
