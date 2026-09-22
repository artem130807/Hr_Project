"""Canonical public links for adaptation participant forms."""
from __future__ import annotations

import os
from urllib.parse import quote, urlsplit, urlunsplit


def _frontend_origin() -> str:
    raw = (os.getenv("HR_FRONTEND_BASE_URL") or os.getenv("FRONTEND_URL") or "").strip()
    if not raw:
        return ""
    value = raw.rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


def public_adaptation_form_path(token: str) -> str:
    return f"/adaptation/forms/{quote(str(token), safe='')}"


def public_adaptation_form_url(token: str) -> str:
    path = public_adaptation_form_path(token)
    origin = _frontend_origin()
    return f"{origin}{path}" if origin else path
