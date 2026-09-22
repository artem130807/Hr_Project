from typing import Optional
from urllib.parse import unquote

from fastapi import Header


def actor_from_headers(
    actor_id: Optional[str] = Header(None, alias="X-Actor-Id"),
    actor_name: Optional[str] = Header(None, alias="X-Actor-Name"),
) -> tuple[Optional[str], Optional[str]]:
    aid = (actor_id or "").strip() or None
    if aid and len(aid) > 36:
        aid = aid[:36]
    raw_name = (actor_name or "").strip()
    aname = unquote(raw_name).strip() if raw_name else None
    if aname and len(aname) > 200:
        aname = aname[:200]
    return aid, aname or None
