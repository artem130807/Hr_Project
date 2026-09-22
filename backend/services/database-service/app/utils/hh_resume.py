from __future__ import annotations

import re
from typing import Optional

_RESUME_PATH_RE = re.compile(r"/resume/([^/?#]+)", re.I)


def normalize_hh_resume_id(value: Optional[str]) -> Optional[str]:
    """HH resume id from raw id or https://hh.ru/resume/<id>."""
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


def candidate_link_matches_resume_id(hh_resume_link: Optional[str], resume_id: Optional[str]) -> bool:
    rid = normalize_hh_resume_id(resume_id)
    if not rid:
        return False
    link = (hh_resume_link or "").strip().lower()
    if not link:
        return False
    link_id = normalize_hh_resume_id(hh_resume_link)
    if link_id and (link_id == rid or link_id.startswith(rid) or rid.startswith(link_id)):
        return True
    return rid in link
