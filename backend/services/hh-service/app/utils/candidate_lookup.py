from __future__ import annotations

from typing import Any, Optional

from app.clients.db_client import APICLient


async def lookup_existing_candidates(
    db: APICLient,
    *,
    resume_ids: list[str] | None = None,
    phone: str | None = None,
    email: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    ids = [str(x).strip() for x in (resume_ids or []) if x and str(x).strip()]
    if ids:
        params["resume_id"] = ids
    if phone and str(phone).strip():
        params["phone"] = str(phone).strip()
    if email and str(email).strip():
        params["email"] = str(email).strip()
    if not params:
        return []
    data = await db.get("/candidates/by-hh-resume", params=params)
    if isinstance(data, dict):
        items = data.get("items")
        return items if isinstance(items, list) else []
    return []


async def find_existing_candidate_id(
    db: APICLient,
    *,
    resume_id: str | None = None,
    phone: str | None = None,
    email: str | None = None,
) -> Optional[int]:
    items = await lookup_existing_candidates(
        db,
        resume_ids=[resume_id] if resume_id else None,
        phone=phone,
        email=email,
    )
    if not items:
        return None
    cid = items[0].get("candidate_id")
    try:
        return int(cid)
    except (TypeError, ValueError):
        return None
