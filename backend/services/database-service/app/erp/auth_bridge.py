"""ERP JWT ↔ HR AuthResponse (no local user table)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt

from app.config import ERP_JWT_ALGORITHM, ERP_JWT_SECRET, REFRESH_TOKEN_EXPIRES
from app.erp.mapper import map_role


def decode_erp_access_token(token: str) -> dict:
    if not ERP_JWT_SECRET:
        raise jwt.InvalidTokenError("ERP_JWT_SECRET is not configured")
    return jwt.decode(token, ERP_JWT_SECRET, algorithms=[ERP_JWT_ALGORITHM])


def normalize_erp_access_payload(payload: dict) -> dict:
    """Flatten ERP JWT into HR-shaped claims (type=user, role string from ERP)."""
    out = dict(payload or {})
    role_raw = out.get("role")
    flat_role = map_role(role_raw) if role_raw is not None else map_role(None)
    out["role"] = flat_role
    out["type"] = "user"
    erp_id = out.get("user_id") or out.get("erp_user_id")
    if erp_id is not None:
        out["erp_user_id"] = str(erp_id)
    return out


def erp_pair_to_auth_response(pair: dict) -> dict:
    """Map ERP Token {expires_in} → HR AuthResponse {expires ISO, refresh_expires}."""
    expires_in = int(pair.get("expires_in") or 0)
    if expires_in <= 0:
        expires_in = 30 * 60
    now = datetime.now(timezone.utc)
    access_expires = now + timedelta(seconds=expires_in)
    refresh_ttl_min = int(REFRESH_TOKEN_EXPIRES or 20160)
    refresh_expires = now + timedelta(minutes=refresh_ttl_min)
    return {
        "access_token": pair["access_token"],
        "expires": access_expires.isoformat(),
        "token_type": pair.get("token_type") or "bearer",
        "refresh_token": pair.get("refresh_token"),
        "refresh_expires": refresh_expires.isoformat(),
    }


def _positive_int_id(value: Any) -> Optional[int]:
    if isinstance(value, dict):
        value = value.get("id")
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def me_from_erp(
    *,
    access_payload: dict,
    erp_me: Optional[dict] = None,
) -> dict[str, Any]:
    """Build /me response purely from ERP JWT + optional GET /users/me."""
    payload = normalize_erp_access_payload(access_payload)
    email = (erp_me or {}).get("email") or payload.get("sub")
    erp_user_id = None
    if erp_me and erp_me.get("id") is not None:
        erp_user_id = str(erp_me["id"])
    else:
        erp_user_id = payload.get("erp_user_id")
    role_src = (erp_me or {}).get("role") if erp_me else payload.get("role")
    role = map_role(role_src) if role_src is not None else payload.get("role")
    full_name = None
    if erp_me:
        full_name = erp_me.get("name") or erp_me.get("full_name")
    profile = erp_me or {}
    role_id = _positive_int_id(profile.get("role_id")) or _positive_int_id(profile.get("role"))
    if role_id is None:
        role_id = _positive_int_id(payload.get("role_id")) or _positive_int_id(
            access_payload.get("role") if isinstance(access_payload.get("role"), dict) else None
        )
    return {
        "id": erp_user_id or str(email or ""),
        "username": str(email or "").strip().lower(),
        "full_name": str(full_name).strip() if full_name else None,
        "role": role,
        "role_id": role_id,
        "department": None,
        "erp_user_id": erp_user_id,
    }
