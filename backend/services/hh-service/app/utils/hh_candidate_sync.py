from __future__ import annotations

import re
from typing import Optional

from app.clients.hh.simple_hh_client import SimpleHHClient
from app.app_logging import logger

_RESUME_PATH_RE = re.compile(r"/(?:resume|resumes)/([^/?#]+)", re.I)

PREFERRED_COLLECTIONS = (
    "response",
    "consider",
    "phone_interview",
    "interview",
    "assessment",
    "offer",
    "hired",
    "discard",
)


def normalize_hh_resume_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    match = _RESUME_PATH_RE.search(s)
    if match:
        s = match.group(1)
    s = s.split(".")[0].strip().lower()
    return s or None


def resume_ids_match(left: Optional[str], right: Optional[str]) -> bool:
    a = normalize_hh_resume_id(left)
    b = normalize_hh_resume_id(right)
    if not a or not b:
        return False
    return a == b or a.startswith(b) or b.startswith(a)


def _item_resume_id(item: dict) -> Optional[str]:
    resume = item.get("resume")
    if isinstance(resume, dict):
        if resume.get("id"):
            found = normalize_hh_resume_id(str(resume.get("id")))
            if found:
                return found
        for key in ("alternate_url", "url"):
            found = normalize_hh_resume_id(resume.get(key))
            if found:
                return found
    elif isinstance(resume, str):
        found = normalize_hh_resume_id(resume)
        if found:
            return found
    for key in ("resume_id", "resumeId"):
        found = normalize_hh_resume_id(item.get(key))
        if found:
            return found
    return None


async def find_negotiation_id_for_resume(
    hh: SimpleHHClient,
    hh_vacancy_id: str,
    resume_id: str,
    *,
    max_pages: int = 8,
    per_page: int = 50,
) -> Optional[str]:
    """Find HH negotiation id for a resume on a vacancy (scans collections)."""
    want = normalize_hh_resume_id(resume_id)
    if not want or not hh_vacancy_id:
        return None
    meta = await hh.get_negotiations_meta(str(hh_vacancy_id))
    if not isinstance(meta, dict):
        return None
    collections = [c for c in (meta.get("collections") or []) if isinstance(c, dict) and c.get("url")]
    if not collections:
        return None

    def _sort_key(coll: dict) -> tuple[int, str]:
        cid = str(coll.get("id") or "")
        try:
            order = PREFERRED_COLLECTIONS.index(cid)
        except ValueError:
            order = 99
        return (order, cid)

    collections.sort(key=_sort_key)

    for coll in collections:
        total = ((coll.get("counters") or {}) if isinstance(coll.get("counters"), dict) else {}).get("total")
        if total == 0:
            continue
        url = str(coll.get("url") or "")
        for page in range(max_pages):
            try:
                page_data = await hh.list_negotiations_collection(url, page=page, per_page=per_page)
            except Exception as exc:
                logger.warning(
                    "Failed to scan HH collection %s page %s: %s",
                    coll.get("id"),
                    page,
                    exc,
                )
                break
            if not isinstance(page_data, dict):
                break
            items = page_data.get("items") or []
            for item in items:
                if not isinstance(item, dict):
                    continue
                if resume_ids_match(_item_resume_id(item), want) and item.get("id"):
                    return str(item["id"])
            if len(items) < per_page:
                break
            pages = page_data.get("pages")
            if pages is not None and page + 1 >= int(pages or 0):
                break
    return None
