"""Helpers for hiring-request / vacancy deadline UX (TZ)."""
from __future__ import annotations

from datetime import date, datetime, timezone


def deadline_state(planned: date | None, today: date | None = None) -> str | None:
    if not planned:
        return None
    day = today or date.today()
    delta = (planned - day).days
    if delta < 0:
        return "overdue"
    if delta <= 3:
        return "warning"
    return "ok"


def days_in_status(
    status_changed_at: datetime | None,
    created_at: datetime | None,
    now: datetime | None = None,
) -> int | None:
    anchor = status_changed_at or created_at
    if not anchor:
        return None
    current = now or datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return max(0, (current - anchor).days)


def enrich_hiring_request(req) -> dict:
    """Build response dict with computed TZ fields."""
    data = {
        c.name: getattr(req, c.name)
        for c in req.__table__.columns
    }
    data["public_code"] = f"З-{req.id}"
    data["days_in_status"] = days_in_status(
        getattr(req, "status_changed_at", None),
        getattr(req, "created_at", None),
    )
    data["deadline_state"] = deadline_state(getattr(req, "planned_close_date", None))
    return data


def vacancy_public_code(vacancy_id: int) -> str:
    return f"В-{vacancy_id}"
