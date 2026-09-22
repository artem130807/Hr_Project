"""Adaptation module: checkpoint kinds, roles, overdue and risk rules.

Spec sources: adaptacia/README (опросники, формы, отчёты) and the approved
prototype table (statuses, progress C/R/H, overdue from 09:00 next day).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

SAMARA = timezone(timedelta(hours=4))
OVERDUE_HOUR = 9

KIND_WEEK_1 = "week_1"
KIND_MONTH_1 = "month_1"
KIND_MONTH_2 = "month_2"
KIND_CONTROL_2M = "control_2m"
KIND_EXTRA = "extra"

ROLE_EMPLOYEE = "employee"
ROLE_MANAGER = "manager"
ROLE_HR = "hr"

STATUS_PLANNED = "planned"
STATUS_COLLECTING = "collecting"
STATUS_OVERDUE = "overdue"
STATUS_DATA_COLLECTED = "data_collected"
STATUS_DRAFT_READY = "draft_ready"
STATUS_COMPLETED = "completed"
STATUS_FORCED_COMPLETED = "forced_completed"

RISK_NONE = "uncalculated"
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"

KIND_LABELS = {
    KIND_WEEK_1: "1 неделя",
    KIND_MONTH_1: "1 месяц",
    KIND_MONTH_2: "2 месяца",
    KIND_CONTROL_2M: "Контроль 2 месяца",
    KIND_EXTRA: "Доп. точка",
}

STATUS_LABELS = {
    STATUS_PLANNED: "Запланирован",
    STATUS_COLLECTING: "Сбор ответов",
    STATUS_OVERDUE: "Просрочен",
    STATUS_DATA_COLLECTED: "Данные собраны",
    STATUS_DRAFT_READY: "Черновик сформирован",
    STATUS_COMPLETED: "Завершен",
    STATUS_FORCED_COMPLETED: "Завершен принудительно",
}

RISK_LABELS = {
    RISK_NONE: "Не рассчитан",
    RISK_LOW: "Низкий",
    RISK_MEDIUM: "Средний",
    RISK_HIGH: "Высокий",
    RISK_CRITICAL: "Критический",
}

OUTCOME_LABELS = {
    RISK_HIGH: "Критическая ситуация",
    RISK_CRITICAL: "Критическая ситуация",
    RISK_MEDIUM: "Требует внимания",
    RISK_LOW: "Стабильно",
    RISK_NONE: "Не рассчитан",
}

NEGATIVE_ITEM_IDS = frozenset()

KINDS_WITHOUT_MANAGER = frozenset({KIND_WEEK_1, KIND_CONTROL_2M, KIND_EXTRA})
KINDS_HR_ONLY = frozenset({KIND_CONTROL_2M})

CORE_EMPLOYEE_IDS = ("core_e1", "core_e2", "core_e3", "core_e4", "core_e5")
STAY_SIGNAL_IDS = ("m1_stay", "m2_stay")

STANDARD_KINDS = (KIND_WEEK_1, KIND_MONTH_1, KIND_MONTH_2)


def roles_for_kind(kind: str) -> tuple[str, ...]:
    if kind in KINDS_HR_ONLY:
        return (ROLE_HR,)
    if kind in KINDS_WITHOUT_MANAGER:
        return (ROLE_EMPLOYEE, ROLE_HR)
    return (ROLE_EMPLOYEE, ROLE_MANAGER, ROLE_HR)


def next_business_day(value: date) -> date:
    shifted = value
    while shifted.weekday() >= 5:
        shifted += timedelta(days=1)
    return shifted


def plan_date_for(kind: str, hired: date, extra_on: Optional[date] = None) -> date:
    if kind == KIND_WEEK_1:
        planned = hired + timedelta(days=7)
    elif kind == KIND_MONTH_1:
        planned = hired + relativedelta(months=1)
    elif kind in (KIND_MONTH_2, KIND_CONTROL_2M):
        planned = hired + relativedelta(months=2)
    elif kind == KIND_EXTRA:
        if extra_on is None:
            raise ValueError("Для доп. точки нужна дата")
        planned = extra_on
    else:
        raise ValueError(f"Неизвестный этап адаптации: {kind}")
    return next_business_day(planned)


def overdue_starts_at(
    plan: date,
    *,
    overdue_time: time = time(OVERDUE_HOUR, 0),
    timezone_name: str = "Europe/Samara",
) -> datetime:
    """Overdue starts at 09:00 Samara on the calendar day after the plan date."""
    nxt = plan + timedelta(days=1)
    if timezone_name == "Europe/Samara":
        tz = SAMARA
    else:
        try:
            tz = ZoneInfo(timezone_name)
        except Exception:
            tz = SAMARA
    return datetime.combine(nxt, overdue_time, tzinfo=tz)


def aware(now: Optional[datetime] = None) -> datetime:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(SAMARA)


def submitted_roles(answers: Iterable[Any]) -> set[str]:
    roles: set[str] = set()
    for item in answers or []:
        role = item.get("role") if isinstance(item, dict) else getattr(item, "role", None)
        if role:
            roles.add(str(role))
    return roles


def compute_status(
    *,
    kind: str,
    plan_date: date,
    answers: Iterable[Any],
    now: Optional[datetime] = None,
    closed: bool = False,
    forced_completed: bool = False,
    draft_ready: bool = False,
    overdue_enabled: bool = True,
    overdue_time: time = time(OVERDUE_HOUR, 0),
    timezone_name: str = "Europe/Samara",
    required_roles: Optional[Iterable[str]] = None,
) -> str:
    if forced_completed:
        return STATUS_FORCED_COMPLETED
    if closed:
        return STATUS_COMPLETED
    if draft_ready:
        return STATUS_DRAFT_READY
    roles = tuple(required_roles) if required_roles is not None else roles_for_kind(kind)
    done = submitted_roles(answers)
    required_pre_hr = [r for r in roles if r != ROLE_HR]
    employee_required = ROLE_EMPLOYEE in roles
    employee_done = ROLE_EMPLOYEE in done
    pre_hr_done = all(r in done for r in required_pre_hr)
    hr_required = ROLE_HR in roles
    hr_done = ROLE_HR in done
    if pre_hr_done and (not hr_required or hr_done):
        return STATUS_COMPLETED
    moment = aware(now)
    if pre_hr_done and hr_required and not hr_done and (required_pre_hr or moment.date() >= plan_date):
        return STATUS_DATA_COLLECTED
    if employee_required and not employee_done and overdue_enabled and moment >= overdue_starts_at(
        plan_date, overdue_time=overdue_time, timezone_name=timezone_name
    ):
        return STATUS_OVERDUE
    if moment.date() >= plan_date:
        return STATUS_COLLECTING
    return STATUS_PLANNED


def _scale_values(payload: dict) -> list[int]:
    values = []
    for key, raw in (payload or {}).items():
        if key.startswith("_"):
            continue
        if isinstance(raw, bool):
            number = 5 if raw else 1
        else:
            try:
                number = int(raw)
            except (TypeError, ValueError):
                continue
        if not (1 <= number <= 5):
            continue
        if key in NEGATIVE_ITEM_IDS:
            number = 6 - number
        values.append(number)
    return values


def _int_score(raw) -> Optional[int]:
    try:
        number = int(raw)
    except (TypeError, ValueError):
        return None
    if 1 <= number <= 5:
        return number
    return None


def assess_risk(
    employee_payload: Optional[dict],
    *,
    kind: str,
    history: Optional[dict[str, list[int]]] = None,
    manager_payload: Optional[dict] = None,
    config: Optional[dict] = None,
) -> dict[str, Any]:
    if kind == KIND_CONTROL_2M:
        return {"risk": RISK_NONE, "strong": [], "medium": [], "protective": []}
    payload = employee_payload or {}
    cores = [_int_score(payload.get(qid)) for qid in CORE_EMPLOYEE_IDS]
    cores = [v for v in cores if v is not None]
    if not cores:
        values = _scale_values(payload)
        if not values:
            return {"risk": RISK_NONE, "strong": [], "medium": [], "protective": []}
        avg = sum(values) / len(values)
        if avg >= 4.0:
            return {"risk": RISK_LOW, "strong": [], "medium": [], "protective": ["positive_scores"]}
        risk = RISK_MEDIUM if avg >= 3.0 else RISK_HIGH
        return {"risk": risk, "strong": [], "medium": ["low_average"], "protective": []}

    strong: list[str] = [qid for qid in CORE_EMPLOYEE_IDS if _int_score(payload.get(qid)) in (1, 2)]
    medium: list[str] = [qid for qid in CORE_EMPLOYEE_IDS if _int_score(payload.get(qid)) == 3]
    protective: list[str] = [qid for qid in CORE_EMPLOYEE_IDS if (_int_score(payload.get(qid)) or 0) >= 4]
    for qid, previous_values in (history or {}).items():
        current = _int_score(payload.get(qid))
        previous = _int_score(previous_values[-1]) if previous_values else None
        if current is None or previous is None:
            continue
        delta = current - previous
        if delta <= -2:
            strong.append(f"{qid}:drop2")
        elif delta == -1:
            medium.append(f"{qid}:drop1")
        elif delta > 0:
            protective.append(f"{qid}:improved")

    conflict = str(payload.get("w_conflict") or "").lower()
    if "существен" in conflict:
        strong.append("explicit_conflict")
    elif "незначитель" in conflict:
        medium.append("minor_conflict")
    load = str(payload.get("w_load") or payload.get("m1_load") or payload.get("m2_load") or "").lower()
    if "очень высок" in load or "перегруз" in load:
        strong.append("overload")
    elif "высок" in load:
        medium.append("high_load")

    manager = manager_payload or {}
    if manager and any("риск" in str(v).lower() and "нет" not in str(v).lower() for v in manager.values()):
        medium.append("manager_risk")

    intention_low = False
    for sid in STAY_SIGNAL_IDS:
        stay = _int_score(payload.get(sid))
        if stay is not None and stay <= 2:
            strong.append("intention_to_leave")
            intention_low = True
            break
    distinct_strong = list(dict.fromkeys(strong))
    other_strong = [item for item in distinct_strong if item != "intention_to_leave"]
    thresholds = config or {}
    def _threshold(name: str, default: int, minimum: int) -> int:
        try:
            return max(minimum, int(thresholds.get(name, default)))
        except (TypeError, ValueError):
            return default

    critical_min = _threshold("critical_min_strong", 3, 2)
    high_min = _threshold("high_min_strong", 2, 1)
    medium_min = _threshold("medium_min_signals", 2, 1)
    if len(distinct_strong) >= critical_min and (not intention_low or len(other_strong) >= critical_min - 1):
        risk = RISK_CRITICAL
    elif len(distinct_strong) >= high_min or (len(distinct_strong) == 1 and any(":drop" in x for x in distinct_strong)):
        risk = RISK_HIGH
    elif len(distinct_strong) == 1 or len(set(medium)) >= medium_min:
        risk = RISK_MEDIUM
    else:
        risk = RISK_LOW
    return {"risk": risk, "strong": distinct_strong, "medium": list(dict.fromkeys(medium)), "protective": list(dict.fromkeys(protective))}


def compute_risk(employee_payload: Optional[dict], *, kind: str) -> str:
    """Backward-compatible scalar API used by existing callers and tests."""
    return assess_risk(employee_payload, kind=kind)["risk"]


def outcome_label(risk: str, *, kind: str, employee_submitted: bool) -> str:
    if kind == KIND_CONTROL_2M and employee_submitted:
        return "Без анкеты" if risk == RISK_NONE else OUTCOME_LABELS[risk]
    return OUTCOME_LABELS.get(risk, OUTCOME_LABELS[RISK_NONE])


def attention_bucket(status: str, plan_date: date, week_start: date, week_end: date) -> Optional[str]:
    if status == STATUS_OVERDUE:
        return "overdue"
    if status == STATUS_DATA_COLLECTED:
        return "ready_hr"
    # Prototype strip: «на этой неделе» = ещё не начатый план в текущей ISO-неделе.
    if status == STATUS_PLANNED and week_start <= plan_date <= week_end:
        return "this_week"
    return None
