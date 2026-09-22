"""Safe reports: internal HR slice vs manager-facing text vs probation conclusion."""
from __future__ import annotations

from typing import Any

from app.adaptation.rules import (
    KIND_LABELS,
    OUTCOME_LABELS,
    RISK_LABELS,
    STATUS_LABELS,
    outcome_label,
)


_MANAGER_SAFE_KEYS = {"hr_notes", "hr_recommend"}


def _answer_payload(answers: list[dict], role: str) -> dict:
    for item in answers:
        if item.get("role") == role:
            return dict(item.get("payload") or {})
    return {}


def internal_slice(row: dict) -> dict:
    """Full HR view: all roles, risk, raw comments."""
    return {
        "employee": row.get("full_name"),
        "department": row.get("department"),
        "position": row.get("position"),
        "plan_date": row.get("plan_date"),
        "fact_date": row.get("fact_date"),
        "enrollment_id": row.get("enrollment_id"),
        "stage": KIND_LABELS.get(row.get("kind"), row.get("kind")),
        "status": STATUS_LABELS.get(row.get("status"), row.get("status")),
        "risk": RISK_LABELS.get(row.get("risk"), row.get("risk")),
        "outcome": row.get("outcome"),
        "answers": row.get("answers") or [],
    }


def manager_safe_report(row: dict) -> dict:
    """No raw employee free-text; only HR-approved notes and scores."""
    hr = _answer_payload(row.get("answers") or [], "hr")
    notes = hr.get("manager_summary") or "Комментарий для руководителя не заполнен."
    return {
        "employee": row.get("full_name"),
        "stage": KIND_LABELS.get(row.get("kind"), row.get("kind")),
        "status": STATUS_LABELS.get(row.get("status"), row.get("status")),
        "risk": RISK_LABELS.get(row.get("risk"), row.get("risk")),
        "hr_notes": notes,
        "recommendation": hr.get("hr_recommend"),
    }


def probation_conclusion(rows: list[dict]) -> dict:
    """Uses the 2-month checkpoint if present, else the latest completed."""
    month2 = [r for r in rows if r.get("kind") == "month_2"]
    control = [r for r in rows if r.get("kind") == "control_2m"]
    chosen = month2[-1] if month2 else (control[-1] if control else (rows[-1] if rows else None))
    if not chosen:
        return {"decision": "insufficient_data", "text": "Нет срезов для заключения."}
    risk = chosen.get("risk") or "uncalculated"
    rec = _answer_payload(chosen.get("answers") or [], "hr").get("hr_recommend")
    if rec is not None:
        try:
            rec_n = int(rec)
        except (TypeError, ValueError):
            rec_n = None
    else:
        rec_n = None
    if rec_n is not None and rec_n <= 2:
        decision = "not_confirmed"
    elif rec_n is not None and rec_n >= 4:
        decision = "confirmed"
    elif risk == "high":
        decision = "not_confirmed"
    elif risk == "low":
        decision = "confirmed"
    else:
        decision = "attention"
    return {
        "decision": decision,
        "risk": risk,
        "outcome": chosen.get("outcome") or outcome_label(risk, kind=chosen.get("kind") or "month_2", employee_submitted=True),
        "stage": KIND_LABELS.get(chosen.get("kind"), chosen.get("kind")),
        "text": OUTCOME_LABELS.get(risk, "Не рассчитан"),
    }


def build_reports(rows: list[Any]) -> dict:
    normalized = [dict(r) if not isinstance(r, dict) else r for r in rows]
    active = [row for row in normalized if not row.get("date_fired")]
    terminated = [row for row in normalized if row.get("date_fired")]
    return {
        "internal": [internal_slice(r) for r in active],
        "terminated": [internal_slice(r) for r in terminated],
        "manager_safe": [manager_safe_report(r) for r in normalized],
        "probation": probation_conclusion(normalized),
    }
