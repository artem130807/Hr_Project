"""Persistence helpers for adaptation enrollments and checkpoints."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time as clock_time, timedelta, timezone
from inspect import isawaitable
import secrets
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import NO_VALUE

from app.adaptation.catalog import CORE_MANAGER_IDS, catalog, form_for, form_public_title
from app.adaptation.links import public_adaptation_form_url
from app.app_logging import logger
from app.adaptation.reports import build_reports
from app.adaptation.rules import (
    CORE_EMPLOYEE_IDS,
    KIND_CONTROL_2M,
    KIND_EXTRA,
    KIND_LABELS,
    KIND_MONTH_2,
    RISK_LABELS,
    ROLE_EMPLOYEE,
    ROLE_HR,
    ROLE_MANAGER,
    STANDARD_KINDS,
    STATUS_COMPLETED,
    STATUS_LABELS,
    STATUS_OVERDUE,
    attention_bucket,
    aware,
    assess_risk,
    compute_status,
    next_business_day,
    outcome_label,
    plan_date_for,
    roles_for_kind,
)
from app.db.v1.enums import Departments
from app.db.v1.models import (
    AdaptationAnswer,
    AdaptationAnswerVersion,
    AdaptationActionRecord,
    AdaptationCheckpoint,
    AdaptationEnrollment,
    AdaptationParticipantForm,
    AdaptationNotificationDelivery,
    AdaptationModuleSettings,
    TemporaryEmployee,
    Employee,
    EmployeeRequest,
)
from app.erp.client import ErpClient
from app.erp.mapper import map_erp_directory_user, map_erp_user

ROLE_LABELS = {
    ROLE_EMPLOYEE: "С",
    ROLE_MANAGER: "Р",
    ROLE_HR: "H",
}
TAKE_ROLE_LABELS = {
    ROLE_EMPLOYEE: "Сотрудник",
    ROLE_MANAGER: "Руководитель",
    ROLE_HR: "HR",
}


def _loaded_relation(instance: Any, name: str, default: Any = None) -> Any:
    """Read an ORM relationship without ever starting implicit database I/O."""
    state = sa_inspect(instance, raiseerr=False)
    if state is None:
        return getattr(instance, name, default)
    attribute = state.attrs.get(name)
    if attribute is None or attribute.loaded_value is NO_VALUE:
        return default
    return attribute.loaded_value


def wants_hr_talk(payload: dict) -> bool:
    for key, raw in (payload or {}).items():
        if "talk" not in str(key):
            continue
        value = str(raw).strip().lower()
        if value in {"да", "yes", "true", "1"}:
            return True
    return False


def _answer_condition_matches(rule: dict, payload: dict, history: dict) -> bool:
    field = str(rule.get("field") or "")
    raw = payload.get(field)
    if "lte" in rule:
        try:
            return float(raw) <= float(rule["lte"])
        except (TypeError, ValueError):
            return False
    if "eq" in rule:
        return str(raw) == str(rule["eq"])
    if "in" in rule:
        return raw in (rule.get("in") or [])
    if "not_in" in rule:
        return raw not in (rule.get("not_in") or [])
    if "not_only" in rule:
        values = raw if isinstance(raw, list) else ([] if raw in (None, "") else [raw])
        return bool(values) and not (
            len(values) == 1 and values[0] in (rule.get("not_only") or [])
        )
    if "delta_gte" in rule:
        try:
            return abs(float(raw) - float(history.get(field))) >= float(rule["delta_gte"])
        except (TypeError, ValueError):
            return False
    return True


def _answer_question_visible(question: dict, payload: dict, history: dict) -> bool:
    rule = question.get("show_if")
    if not isinstance(rule, dict):
        return True
    alternatives = rule.get("any")
    if isinstance(alternatives, list):
        return any(
            _answer_condition_matches(item, payload, history)
            for item in alternatives
            if isinstance(item, dict)
        )
    return _answer_condition_matches(rule, payload, history)


def validate_answer_payload(
    kind: str,
    role: str,
    payload: dict,
    *,
    core_history: Optional[dict] = None,
) -> dict:
    """Validate the server-owned questionnaire, never trusting browser checks."""
    if not isinstance(payload, dict):
        raise ValueError("Некорректный формат ответов")
    questions = form_for(kind, role)
    allowed_ids = {str(question["id"]) for question in questions}
    unknown = sorted(str(key) for key in payload if str(key) not in allowed_ids)
    if unknown:
        raise ValueError("Форма устарела. Обновите страницу и заполните её повторно")

    normalized: dict = {}
    history = core_history or {}
    for question in questions:
        qid = str(question["id"])
        if not _answer_question_visible(question, payload, history):
            continue
        raw = payload.get(qid)
        blank = (
            raw is None
            or (isinstance(raw, str) and not raw.strip())
            or (isinstance(raw, list) and not raw)
        )
        if blank:
            if question.get("required", True):
                raise ValueError(f"Заполните обязательное поле: {question['text']}")
            continue
        qtype = question.get("type")
        if qtype in {"scale_1_5", "scale_na", "scale_obs"}:
            special_options = [
                str(option.get("value"))
                for option in (question.get("special_options") or [])
                if isinstance(option, dict) and option.get("value")
            ]
            if raw in special_options:
                normalized[qid] = raw
            elif raw == "na" and special_options:
                # Совместимость со ссылками, открытыми до разделения значений
                # «не применимо» и «недостаточно наблюдений».
                normalized[qid] = special_options[0]
            elif (
                isinstance(raw, bool)
                or not isinstance(raw, (int, float))
                or not float(raw).is_integer()
                or not 1 <= raw <= 5
            ):
                raise ValueError(f"Некорректная оценка в поле: {question['text']}")
            else:
                normalized[qid] = int(raw)
        elif qtype == "choice":
            if raw not in (question.get("options") or []):
                raise ValueError(f"Некорректный вариант в поле: {question['text']}")
            normalized[qid] = raw
        elif qtype == "multi":
            options = set(question.get("options") or [])
            if not isinstance(raw, list) or any(item not in options for item in raw):
                raise ValueError(f"Некорректные варианты в поле: {question['text']}")
            unique_values = list(dict.fromkeys(raw))
            exclusive_options = set(question.get("exclusive_options") or [])
            if len(unique_values) > 1 and exclusive_options.intersection(unique_values):
                raise ValueError(
                    f"Взаимоисключающие варианты в поле: {question['text']}"
                )
            normalized[qid] = unique_values
        elif not isinstance(raw, str):
            raise ValueError(f"Некорректный текст в поле: {question['text']}")
        else:
            normalized[qid] = raw.strip()
    return normalized


def _week_bounds(today: date) -> tuple[date, date]:
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


def _status_options(settings: Optional[AdaptationModuleSettings]) -> dict:
    if not isinstance(settings, AdaptationModuleSettings):
        return {}
    timezone_name = str(settings.timezone or "Europe/Samara")
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.error(
            "Invalid adaptation timezone %r; Europe/Samara is used",
            timezone_name,
        )
        timezone_name = "Europe/Samara"
    overdue_clock = settings.overdue_time
    if not isinstance(overdue_clock, clock_time):
        logger.error(
            "Invalid adaptation overdue_time %r; 09:00 is used",
            overdue_clock,
        )
        overdue_clock = clock_time(9, 0)
    return {
        "overdue_enabled": bool(settings.overdue_enabled),
        "overdue_clock": overdue_clock,
        "timezone_name": timezone_name,
        "risk_rules": settings.risk_rules if isinstance(settings.risk_rules, dict) else {},
    }


def serialize_checkpoint(
    cp: AdaptationCheckpoint,
    employee: Any,
    *,
    now: Optional[datetime] = None,
    include_form: bool = False,
    overdue_enabled: bool = True,
    overdue_clock: clock_time = clock_time(9, 0),
    timezone_name: str = "Europe/Samara",
    risk_rules: Optional[dict] = None,
) -> dict:
    answers = list(_loaded_relation(cp, "answers", []) or [])
    answer_dicts = [
        {
            "id": a.id,
            "role": a.role,
            "payload": dict(a.payload or {}),
            "submitted_at": a.submitted_at,
            "actor_user_id": getattr(a, "actor_user_id", None),
            "actor_name": getattr(a, "actor_name", None),
            "version": getattr(a, "version", 1) or 1,
            "locked": bool(getattr(a, "locked", True)),
        }
        for a in answers
    ]
    form_roles = {form.role for form in (_loaded_relation(cp, "participant_forms", []) or [])}
    required_roles = form_roles if cp.kind == KIND_EXTRA and form_roles else None
    status = compute_status(
        kind=cp.kind,
        plan_date=cp.plan_date,
        answers=answer_dicts,
        now=now,
        closed=bool(cp.closed),
        forced_completed=bool(getattr(cp, "forced_completed_at", None)),
        draft_ready=bool(getattr(cp, "draft_ready_at", None)),
        overdue_enabled=overdue_enabled,
        overdue_time=overdue_clock,
        timezone_name=timezone_name,
        required_roles=required_roles,
    )
    enrollment = _loaded_relation(cp, "enrollment")
    risk_history: dict[str, list[int]] = {qid: [] for qid in CORE_EMPLOYEE_IDS}
    for previous_cp in sorted(_loaded_relation(enrollment, "checkpoints", []) or [], key=lambda item: (item.plan_date, item.id)):
        if previous_cp.id == cp.id or previous_cp.plan_date > cp.plan_date:
            continue
        previous_answers = _loaded_relation(previous_cp, "answers", []) or []
        previous_answer = next((answer for answer in previous_answers if answer.role == ROLE_EMPLOYEE), None)
        for qid in CORE_EMPLOYEE_IDS:
            value = (previous_answer.payload or {}).get(qid) if previous_answer else None
            if value not in (None, ""):
                risk_history[qid].append(value)
    emp_payload = next((d["payload"] for d in answer_dicts if d["role"] == ROLE_EMPLOYEE), None)
    manager_payload = next((d["payload"] for d in answer_dicts if d["role"] == ROLE_MANAGER), None)
    assessment = assess_risk(
        emp_payload,
        kind=cp.kind,
        history={key: values for key, values in risk_history.items() if values},
        manager_payload=manager_payload,
        config=risk_rules,
    )
    risk = getattr(cp, "risk_override", None) or assessment["risk"]
    employee_submitted = ROLE_EMPLOYEE in {d["role"] for d in answer_dicts}
    done_roles = {d["role"] for d in answer_dicts}
    participating = set(required_roles or roles_for_kind(cp.kind))
    progress = []
    for role in (ROLE_EMPLOYEE, ROLE_MANAGER, ROLE_HR):
        if role not in participating:
            progress.append({"role": role, "state": "muted", "label": ROLE_LABELS[role]})
        elif role in done_roles:
            progress.append({"role": role, "state": "done", "label": ROLE_LABELS[role]})
        else:
            progress.append({"role": role, "state": "waiting", "label": ROLE_LABELS[role]})
    dept = getattr(employee, "department", None)
    if hasattr(dept, "value"):
        dept = dept.value
    pos = getattr(employee, "position", None)
    row = {
        "id": cp.id,
        "enrollment_id": cp.enrollment_id,
        "employee_id": getattr(enrollment, "employee_id", None),
        "temporary_employee_id": getattr(enrollment, "temporary_employee_id", None),
        "full_name": employee.full_name or "",
        "department": str(dept or ""),
        "position": str(pos or ""),
        "photo_url": getattr(employee, "photo_url", None),
        "date_hired": getattr(enrollment, "start_date", None) or getattr(employee, "date_hired", None),
        "date_fired": getattr(employee, "date_fired", None),
        "kind": cp.kind,
        "kind_label": KIND_LABELS.get(cp.kind, cp.kind),
        "plan_date": cp.plan_date,
        "fact_date": cp.fact_date,
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "risk": risk,
        "risk_label": RISK_LABELS.get(risk, risk),
        "outcome": getattr(cp, "outcome_override", None) or outcome_label(risk, kind=cp.kind, employee_submitted=employee_submitted),
        "risk_signals": assessment,
        "progress": progress,
        "answers": answer_dicts,
        "talk_hr": wants_hr_talk(emp_payload or {}),
        "route": getattr(enrollment, "route", None) or ("control" if cp.kind == KIND_CONTROL_2M else "full"),
        "original_plan_date": getattr(cp, "original_plan_date", None) or cp.plan_date,
        "reschedule_reason": getattr(cp, "reschedule_reason", None),
        "forced_reason": getattr(cp, "forced_reason", None),
        "manager_user_id": getattr(enrollment, "manager_user_id", None),
        "manager_name": getattr(enrollment, "manager_name", None),
        "available_actions": ["reschedule", "force_complete", "finalize"],
        "archived": bool(getattr(enrollment, "archived", False)),
        "series_key": getattr(cp, "series_key", None),
        "recurrence_rule": getattr(cp, "recurrence_rule", None),
    }
    form_links = _form_links_payload(cp)
    if form_links:
        row["form_links"] = form_links
        employee_link = next((item for item in form_links if item["role"] == ROLE_EMPLOYEE), None)
        if employee_link:
            row["employee_take_token"] = employee_link["token"]
            row["employee_take_path"] = employee_link["path"]
    if include_form:
        row["form"] = {
            role: form_for(cp.kind, role)
            for role in (ROLE_EMPLOYEE, ROLE_MANAGER, ROLE_HR)
        }
        row["form_title"] = {
            role: form_public_title(cp.kind, role)
            for role in (ROLE_EMPLOYEE, ROLE_MANAGER, ROLE_HR)
        }
        row["core_history"] = {}
    return row


def public_form_path(token: str) -> str:
    return f"/adaptation/forms/{token}"


def _form_links_payload(cp: AdaptationCheckpoint) -> list[dict]:
    links = []
    for form in _loaded_relation(cp, "participant_forms", []) or []:
        if getattr(form, "revoked_at", None):
            continue
        links.append({
            "form_id": getattr(form, "id", None),
            "role": form.role,
            "token": form.token,
            "path": public_form_path(form.token),
            "url": public_adaptation_form_url(form.token),
            "sent_at": getattr(form, "sent_at", None),
            "submitted_at": getattr(form, "submitted_at", None),
            "locked": bool(getattr(form, "locked", False)),
        })
    return links


def _participant_user_id_for_role(enrollment: AdaptationEnrollment, role: str) -> Optional[str]:
    if role == ROLE_MANAGER:
        return (enrollment.manager_user_id or "").strip() or None
    if role == ROLE_EMPLOYEE:
        employee = _loaded_relation(enrollment, "employee")
        erp_id = getattr(employee, "erp_user_id", None) if employee is not None else None
        return str(erp_id).strip() if erp_id else None
    return None


async def ensure_participant_forms(db: AsyncSession, enrollment: AdaptationEnrollment) -> None:
    """Create missing public-form tokens so HR can copy a take link after enroll."""
    if getattr(enrollment, "archived", False) or getattr(enrollment, "closed", False):
        return
    checkpoints = _loaded_relation(enrollment, "checkpoints", []) or []
    for cp in checkpoints:
        if getattr(cp, "closed", False):
            continue
        forms = list(_loaded_relation(cp, "participant_forms", []) or [])
        existing = {form.role for form in forms if getattr(form, "revoked_at", None) is None}
        for role in roles_for_kind(cp.kind):
            if role in existing:
                continue
            revoked = next(
                (form for form in forms if form.role == role and getattr(form, "revoked_at", None)),
                None,
            )
            if revoked is not None:
                # Reading links must never reactivate a deliberately revoked token.
                existing.add(role)
                continue
            form = AdaptationParticipantForm(
                checkpoint_id=cp.id,
                role=role,
                participant_user_id=_participant_user_id_for_role(enrollment, role),
            )
            db.add(form)
            forms.append(form)
            if hasattr(cp, "participant_forms") and cp.participant_forms is not None:
                try:
                    cp.participant_forms.append(form)
                except Exception:
                    pass
    await db.flush()


async def take_links_for_enrollment(db: AsyncSession, enrollment_id: int) -> dict:
    stmt = (
        select(AdaptationEnrollment)
        .options(
            selectinload(AdaptationEnrollment.employee),
            selectinload(AdaptationEnrollment.temporary_employee),
            selectinload(AdaptationEnrollment.checkpoints).selectinload(AdaptationCheckpoint.participant_forms),
        )
        .where(AdaptationEnrollment.id == enrollment_id)
    )
    result = await db.execute(stmt)
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise LookupError("Enrollment not found")
    await ensure_participant_forms(db, enrollment)
    employee = enrollment.employee or enrollment.temporary_employee
    links = []
    for cp in sorted(enrollment.checkpoints or [], key=lambda item: (item.plan_date, item.id)):
        for form in _form_links_payload(cp):
            links.append({
                **form,
                "checkpoint_id": cp.id,
                "kind": cp.kind,
                "kind_label": KIND_LABELS.get(cp.kind, cp.kind),
                "plan_date": cp.plan_date,
                "role_label": TAKE_ROLE_LABELS.get(form["role"], form["role"]),
                "title": form_public_title(cp.kind, form["role"]),
                "valid": not any((getattr(enrollment, "archived", False),
                                  getattr(enrollment, "closed", False),
                                  getattr(cp, "closed", False))),
            })
    return {
        "enrollment_id": enrollment.id,
        "employee_id": enrollment.employee_id,
        "temporary_employee_id": enrollment.temporary_employee_id,
        "full_name": getattr(employee, "full_name", None),
        "route": enrollment.route,
        "links": links,
    }


def _checkpoint_kinds(*, include_control_2m: bool, extra_on: Optional[date], route: str = "full") -> list[str]:
    if str(route).strip().lower() == "control":
        kinds = [KIND_CONTROL_2M]
        if extra_on:
            kinds.append(KIND_EXTRA)
        return kinds
    kinds = list(STANDARD_KINDS)
    if include_control_2m:
        kinds = [k for k in kinds if k != KIND_MONTH_2]
        kinds.append(KIND_CONTROL_2M)
    if extra_on:
        kinds.append(KIND_EXTRA)
    return kinds


def _hired_from_erp(raw: dict) -> date:
    raw_dt = (raw or {}).get("create_dt") or (raw or {}).get("created_at")
    if isinstance(raw_dt, datetime):
        return raw_dt.date()
    if isinstance(raw_dt, date):
        return raw_dt
    if isinstance(raw_dt, str) and len(raw_dt) >= 10:
        try:
            return date.fromisoformat(raw_dt[:10])
        except ValueError:
            pass
    return date.today()


def _as_hire_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            pass
    return date.today()


def _erp_raw_id(raw: dict) -> str:
    return str((raw or {}).get("id") or "").strip()


def _staff_label(mapped: dict, raw: Optional[dict] = None) -> str:
    role_name = None
    if raw and isinstance(raw.get("role"), dict):
        role_name = raw["role"].get("name")
    elif raw:
        role_name = raw.get("role")
    label = (
        (mapped or {}).get("position")
        or (mapped or {}).get("department")
        or (mapped or {}).get("role")
        or role_name
        or "сотрудник"
    )
    return str(label).strip()[:200] or "сотрудник"


def _safe_department(label: str) -> str:
    """Prefer a value that still fits a leftover PostgreSQL departments enum."""
    raw = (label or "").strip()
    if not raw:
        return Departments.hr.value
    key = raw.lower()
    for member in Departments:
        if key in {member.value.lower(), member.name.lower()}:
            return member.value
    return raw


def _human_db_error(exc: Exception) -> str:
    orig = str(getattr(exc, "orig", None) or exc).replace("\n", " ").strip()
    text = orig.lower()
    if "undefinedtable" in text or "does not exist" in text and "relation" in text:
        base = "Таблицы адаптации не созданы. Перезапустите database-service."
    elif "function lower(" in text:
        base = "Ошибка поиска сотрудника по ERP id. Обновите database-service."
    elif "invalid input value for enum" in text or (
        "enum" in text and "invalid" in text
    ):
        base = (
            "Отдел сотрудника не входит в справочник БД. "
            "Перезапустите database-service, чтобы department стал текстом."
        )
    elif "unique" in text or "duplicate" in text:
        base = "Сотрудник уже есть в штате или уже на адаптации"
    elif "not-null" in text or "null value" in text:
        base = "Не хватает обязательных данных сотрудника для адаптации"
    else:
        base = "Не удалось сохранить адаптацию"
    extra = orig[:180] + ("…" if len(orig) > 180 else "")
    return f"{base}: {extra}" if extra else base


async def _rollback(db: AsyncSession) -> None:
    rollback = getattr(db, "rollback", None)
    if not callable(rollback):
        return
    maybe = rollback()
    if isawaitable(maybe):
        await maybe


async def _employee_by_erp_id(db: AsyncSession, eid: str) -> Optional[Employee]:
    found = await db.execute(select(Employee).where(Employee.erp_user_id == eid))
    return found.scalar_one_or_none()


async def resolve_staff_employee(
    db: AsyncSession,
    *,
    employee_id: Optional[int] = None,
    erp_user_id: Optional[str] = None,
) -> Employee:
    if employee_id is not None:
        employee = await db.get(Employee, employee_id)
        if not employee:
            raise LookupError("Сотрудник не найден в штате")
        return employee

    eid = str(erp_user_id or "").strip()[:36]
    if not eid:
        raise LookupError("Сотрудник не найден")

    employee = await _employee_by_erp_id(db, eid)
    if employee:
        return employee

    try:
        raw_users = await ErpClient().list_users()
    except Exception as exc:
        logger.warning("ERP list_users failed during adaptation enroll: %s", exc)
        raise LookupError("Не удалось загрузить сотрудников из ERP") from exc

    matched_raw = None
    mapped = None
    for raw in raw_users or []:
        raw_id = _erp_raw_id(raw)
        if raw_id != eid and raw_id[:36] != eid and raw_id.lower() != eid.lower():
            continue
        matched_raw = raw
        mapped = map_erp_user(raw) or map_erp_directory_user(raw)
        break
    if not matched_raw and not mapped:
        raise LookupError("Сотрудник не найден в ERP")

    mapped = mapped or {}
    label = _staff_label(mapped, matched_raw)
    full_name = (mapped.get("full_name") or mapped.get("username") or "Сотрудник ERP")[:200]
    hired = _hired_from_erp(matched_raw or {})
    dept = _safe_department(str(mapped.get("department") or label))

    async def _insert(department: str) -> Employee:
        row = Employee(
            erp_user_id=eid,
            full_name=full_name,
            department=department,
            position=label,
            date_hired=hired,
        )
        db.add(row)
        await db.flush()
        return row

    try:
        return await _insert(dept)
    except IntegrityError:
        await _rollback(db)
        employee = await _employee_by_erp_id(db, eid)
        if employee:
            return employee
        raise ValueError("Сотрудник уже есть в штате. Обновите страницу и выберите его снова.")
    except DBAPIError as exc:
        await _rollback(db)
        orig = str(getattr(exc, "orig", exc)).lower()
        if "invalid input value for enum" in orig or "enum" in orig:
            try:
                return await _insert(Departments.hr.value)
            except DBAPIError as exc2:
                await _rollback(db)
                raise ValueError(_human_db_error(exc2)) from exc2
        raise ValueError(_human_db_error(exc)) from exc


async def enroll_employee(
    db: AsyncSession,
    *,
    employee_id: Optional[int] = None,
    erp_user_id: Optional[str] = None,
    include_control_2m: bool = False,
    extra_on: Optional[date] = None,
    route: str = "full",
    start_date: Optional[date] = None,
    manager_user_id: Optional[str] = None,
    manager_name: Optional[str] = None,
    hiring_request_id: Optional[int] = None,
) -> AdaptationEnrollment:
    try:
        return await _enroll_employee(
            db,
            employee_id=employee_id,
            erp_user_id=erp_user_id,
            include_control_2m=include_control_2m,
            extra_on=extra_on,
            route=route,
            start_date=start_date,
            manager_user_id=manager_user_id,
            manager_name=manager_name,
            hiring_request_id=hiring_request_id,
        )
    except (LookupError, ValueError):
        raise
    except SQLAlchemyError as exc:
        await _rollback(db)
        raise ValueError(_human_db_error(exc)) from exc


async def _enroll_employee(
    db: AsyncSession,
    *,
    employee_id: Optional[int] = None,
    erp_user_id: Optional[str] = None,
    include_control_2m: bool = False,
    extra_on: Optional[date] = None,
    route: str = "full",
    start_date: Optional[date] = None,
    manager_user_id: Optional[str] = None,
    manager_name: Optional[str] = None,
    hiring_request_id: Optional[int] = None,
) -> AdaptationEnrollment:
    employee = await resolve_staff_employee(
        db, employee_id=employee_id, erp_user_id=erp_user_id
    )
    if str(route).strip().lower() == "control":
        include_control_2m = True
    if employee.date_fired is not None:
        raise ValueError("Нельзя поставить на адаптацию уволенного сотрудника")

    existing = await db.execute(
        select(AdaptationEnrollment)
        .where(
            AdaptationEnrollment.employee_id == employee.id,
            AdaptationEnrollment.closed.is_(False),
            AdaptationEnrollment.archived.is_(False),
        )
        .order_by(AdaptationEnrollment.id.desc())
    )
    if existing.scalar_one_or_none():
        raise ValueError("Сотрудник уже на адаптации")

    previous_result = await db.execute(
        select(AdaptationEnrollment)
        .where(AdaptationEnrollment.employee_id == employee.id)
        .order_by(AdaptationEnrollment.id.desc())
        .limit(1)
    )
    previous = previous_result.scalar_one_or_none()
    hired = _as_hire_date(start_date or employee.date_hired)

    enrollment = AdaptationEnrollment(
        employee_id=employee.id,
        previous_enrollment_id=getattr(previous, "id", None),
        start_date=hired,
        route="control" if str(route).strip().lower() == "control" else "full",
        manager_user_id=(manager_user_id or "").strip() or None,
        manager_name=(manager_name or "").strip() or None,
        hiring_request_id=hiring_request_id,
        include_control_2m=include_control_2m,
    )
    db.add(enrollment)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ValueError("Сотрудник уже на адаптации") from exc
    except DBAPIError as exc:
        raise ValueError(_human_db_error(exc)) from exc

    try:
        for kind in _checkpoint_kinds(
            include_control_2m=include_control_2m, extra_on=extra_on, route=route
        ):
            planned = plan_date_for(kind, hired, extra_on=extra_on)
            cp = AdaptationCheckpoint(
                enrollment_id=enrollment.id,
                kind=kind,
                plan_date=planned,
                original_plan_date=planned,
            )
            db.add(cp)
            await db.flush()
            for participant_role in roles_for_kind(kind):
                db.add(
                    AdaptationParticipantForm(
                        checkpoint_id=cp.id,
                        role=participant_role,
                        participant_user_id=(
                            str(getattr(employee, "erp_user_id", ""))
                            if participant_role == ROLE_EMPLOYEE and getattr(employee, "erp_user_id", None)
                            else manager_user_id if participant_role == ROLE_MANAGER else None
                        ),
                    )
                )
        await db.flush()
    except (IntegrityError, DBAPIError) as exc:
        raise ValueError(_human_db_error(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Не удалось построить план адаптации: {exc}") from exc
    return enrollment


async def add_extra_checkpoint(
    db: AsyncSession,
    *,
    enrollment_id: int,
    plan_date: date,
    kind: str = KIND_EXTRA,
    include_hr: bool = True,
) -> AdaptationCheckpoint:
    enrollment = await db.get(AdaptationEnrollment, enrollment_id)
    if not enrollment:
        raise LookupError("Enrollment not found")
    if enrollment.closed or enrollment.archived:
        raise ValueError("Нельзя добавить этап в завершённый или архивный кейс")
    if kind not in (KIND_EXTRA, KIND_CONTROL_2M):
        raise ValueError("Можно добавить только доп. точку или контроль 2 месяца")
    cp = AdaptationCheckpoint(
        enrollment_id=enrollment_id,
        kind=kind,
        plan_date=next_business_day(plan_date),
        original_plan_date=next_business_day(plan_date),
    )
    db.add(cp)
    try:
        await db.flush()
        participant_roles = roles_for_kind(kind)
        if kind == KIND_EXTRA and not include_hr:
            participant_roles = (ROLE_EMPLOYEE,)
        for participant_role in participant_roles:
            db.add(
                AdaptationParticipantForm(
                    checkpoint_id=cp.id,
                    role=participant_role,
                    participant_user_id=(
                        enrollment.manager_user_id
                        if participant_role == ROLE_MANAGER
                        else None
                    ),
                )
            )
        await db.flush()
    except (IntegrityError, DBAPIError) as exc:
        raise ValueError(_human_db_error(exc)) from exc
    return cp


async def create_temporary_employee_case(
    db: AsyncSession,
    *,
    full_name: str,
    position: str,
    department: str,
    start_date: date,
    route: str = "full",
    manager_user_id: Optional[str] = None,
    manager_name: Optional[str] = None,
    photo_url: Optional[str] = None,
) -> AdaptationEnrollment:
    temp = TemporaryEmployee(
        full_name=full_name.strip(),
        position=position.strip(),
        department=department.strip(),
        start_date=start_date,
        manager_user_id=(manager_user_id or "").strip() or None,
        manager_name=(manager_name or "").strip() or None,
        photo_url=(photo_url or "").strip() or None,
    )
    db.add(temp)
    await db.flush()
    normalized_route = "control" if route == "control" else "full"
    enrollment = AdaptationEnrollment(
        temporary_employee_id=temp.id,
        start_date=start_date,
        route=normalized_route,
        include_control_2m=normalized_route == "control",
        manager_user_id=temp.manager_user_id,
        manager_name=temp.manager_name,
    )
    db.add(enrollment)
    await db.flush()
    for kind in _checkpoint_kinds(include_control_2m=False, extra_on=None, route=normalized_route):
        planned = plan_date_for(kind, start_date)
        cp = AdaptationCheckpoint(
            enrollment_id=enrollment.id,
            kind=kind,
            plan_date=planned,
            original_plan_date=planned,
        )
        db.add(cp)
        await db.flush()
        for participant_role in roles_for_kind(kind):
            db.add(
                AdaptationParticipantForm(
                    checkpoint_id=cp.id,
                    role=participant_role,
                    participant_user_id=manager_user_id if participant_role == ROLE_MANAGER else None,
                )
            )
    await db.flush()
    return enrollment


async def link_temporary_employee(
    db: AsyncSession,
    *,
    temporary_employee_id: int,
    employee_id: int,
    actor_user_id: str,
) -> AdaptationEnrollment:
    temp = await db.get(TemporaryEmployee, temporary_employee_id)
    employee = await db.get(Employee, employee_id)
    if not temp or not employee:
        raise LookupError("Temporary employee or employee not found")
    if temp.linked_employee_id and temp.linked_employee_id != employee_id:
        raise ValueError("Временная карточка уже связана с другим сотрудником")
    result = await db.execute(
        select(AdaptationEnrollment).where(
            AdaptationEnrollment.temporary_employee_id == temporary_employee_id
        )
    )
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise LookupError("Adaptation case not found")
    duplicate = await db.execute(
        select(AdaptationEnrollment).where(
            AdaptationEnrollment.employee_id == employee_id,
            AdaptationEnrollment.closed.is_(False),
            AdaptationEnrollment.archived.is_(False),
            AdaptationEnrollment.id != enrollment.id,
        )
    )
    if duplicate.scalar_one_or_none():
        raise ValueError("У сотрудника уже есть активный кейс адаптации")
    enrollment.employee_id = employee_id
    temp.linked_employee_id = employee_id
    temp.link_status = "linked"
    temp.linked_at = datetime.now(timezone.utc)
    temp.linked_by = actor_user_id
    await db.flush()
    return enrollment


async def reschedule_checkpoint(
    db: AsyncSession,
    *,
    checkpoint_id: int,
    plan_date: date,
    reason: str,
    actor_user_id: str,
) -> AdaptationCheckpoint:
    cp = await db.get(AdaptationCheckpoint, checkpoint_id)
    if not cp:
        raise LookupError("Checkpoint not found")
    if cp.closed or cp.finalized_at or cp.forced_completed_at:
        raise ValueError("Завершённую точку нельзя переносить")
    if not reason.strip():
        raise ValueError("Укажите причину переноса")
    if cp.original_plan_date is None:
        cp.original_plan_date = cp.plan_date
    cp.plan_date = next_business_day(plan_date)
    cp.reschedule_reason = reason.strip()
    cp.rescheduled_by = actor_user_id
    cp.rescheduled_at = datetime.now(timezone.utc)
    # Unsent reminders use the stage date and must be regenerated by the worker.
    # Delete them instead of marking cancelled: cancelled deliveries represent a
    # terminal decision (answered/closed/disabled) and must not be reactivated.
    deliveries = await db.execute(
        select(AdaptationNotificationDelivery).where(
            AdaptationNotificationDelivery.checkpoint_id == checkpoint_id,
            AdaptationNotificationDelivery.status != "sent",
        )
    )
    for delivery in deliveries.scalars().all():
        await db.delete(delivery)
    await db.flush()
    return cp


async def force_complete_checkpoint(
    db: AsyncSession,
    *,
    checkpoint_id: int,
    reason: str,
    actor_user_id: str,
) -> AdaptationCheckpoint:
    cp = await db.get(AdaptationCheckpoint, checkpoint_id)
    if not cp:
        raise LookupError("Checkpoint not found")
    if cp.closed or cp.finalized_at:
        raise ValueError("Этап уже зафиксирован")
    if not reason.strip():
        raise ValueError("Укажите причину принудительного завершения")
    now = datetime.now(timezone.utc)
    cp.forced_completed_at = now
    cp.forced_completed_by = actor_user_id
    cp.forced_reason = reason.strip()
    cp.fact_date = aware(now).date()
    cp.closed = False  # participant links remain valid for a late answer
    deliveries = await db.execute(
        select(AdaptationNotificationDelivery).where(
            AdaptationNotificationDelivery.checkpoint_id == checkpoint_id,
            AdaptationNotificationDelivery.status.in_(["pending", "failed"]),
        )
    )
    for delivery in deliveries.scalars().all():
        delivery.status = "cancelled"
        delivery.last_error = "Этап завершён принудительно"
    await db.flush()
    return cp


async def finalize_checkpoint(
    db: AsyncSession,
    *,
    checkpoint_id: int,
    outcome: str,
    risk: str,
    comment: Optional[str],
    actor_user_id: str,
) -> AdaptationCheckpoint:
    result = await db.execute(
        select(AdaptationCheckpoint)
        .options(selectinload(AdaptationCheckpoint.answers))
        .where(AdaptationCheckpoint.id == checkpoint_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    cp = result.scalar_one_or_none()
    if not cp:
        raise LookupError("Checkpoint not found")
    if cp.closed or cp.finalized_at:
        raise ValueError("Этап уже зафиксирован")
    if outcome not in {"stable", "attention", "critical", "Стабильно", "Требует внимания", "Критическая ситуация"}:
        raise ValueError("Некорректный итог адаптации")
    if risk not in {"low", "medium", "high", "critical"}:
        raise ValueError("Некорректный риск")
    required_external = {item for item in roles_for_kind(cp.kind) if item != ROLE_HR}
    submitted = {answer.role for answer in cp.answers}
    if not cp.forced_completed_at and not required_external.issubset(submitted):
        raise ValueError(
            "Сначала соберите обязательные формы или завершите этап принудительно"
        )
    now = datetime.now(timezone.utc)
    cp.outcome_override = outcome
    cp.risk_override = risk
    cp.override_comment = (comment or "").strip() or None
    cp.finalized_at = now
    cp.finalized_by = actor_user_id
    cp.closed = True
    cp.fact_date = cp.fact_date or aware(now).date()
    forms = await db.execute(
        select(AdaptationParticipantForm).where(
            AdaptationParticipantForm.checkpoint_id == checkpoint_id,
            AdaptationParticipantForm.revoked_at.is_(None),
        )
    )
    for form in forms.scalars().all():
        form.revoked_at = now
    deliveries = await db.execute(
        select(AdaptationNotificationDelivery).where(
            AdaptationNotificationDelivery.checkpoint_id == checkpoint_id,
            AdaptationNotificationDelivery.status.in_(["pending", "failed"]),
        )
    )
    for delivery in deliveries.scalars().all():
        delivery.status = "cancelled"
        delivery.last_error = "Этап зафиксирован HR"
    await db.flush()
    return cp


async def finalize_enrollment(
    db: AsyncSession,
    *,
    enrollment_id: int,
    outcome: str,
    risk: str,
    comment: Optional[str],
    actor_user_id: str,
    credit_hiring_request: bool = False,
) -> AdaptationEnrollment:
    enrollment = await db.get(AdaptationEnrollment, enrollment_id)
    if not enrollment:
        raise LookupError("Enrollment not found")
    if outcome not in {
        "stable", "attention", "critical",
        "Стабильно", "Требует внимания", "Критическая ситуация",
    }:
        raise ValueError("Некорректный итог адаптации")
    if risk not in {"low", "medium", "high", "critical"}:
        raise ValueError("Некорректный риск")
    now = datetime.now(timezone.utc)
    enrollment.closed = True
    enrollment.finalized_at = now
    enrollment.finalized_by = actor_user_id
    enrollment.outcome = outcome
    enrollment.risk = risk
    enrollment.decision_comment = (comment or "").strip() or None
    if credit_hiring_request:
        if not enrollment.hiring_request_id:
            raise ValueError("Кейс не связан с заявкой на подбор")
        if outcome not in {"stable", "Стабильно"}:
            raise ValueError("Место можно зачесть только после успешной адаптации")
        already = await db.execute(
            select(AdaptationEnrollment).where(
                AdaptationEnrollment.employee_id == enrollment.employee_id,
                AdaptationEnrollment.hiring_request_id == enrollment.hiring_request_id,
                AdaptationEnrollment.quota_credited_at.is_not(None),
                AdaptationEnrollment.id != enrollment.id,
            )
        )
        if already.scalar_one_or_none():
            raise ValueError("Этот сотрудник уже зачтён в квоту заявки")
        request = await db.get(EmployeeRequest, enrollment.hiring_request_id)
        if not request:
            raise LookupError("Hiring request not found")
        enrollment.quota_credited_at = now
        enrollment.quota_credited_by = actor_user_id
    forms = await db.execute(
        select(AdaptationParticipantForm)
        .join(AdaptationCheckpoint)
        .where(
            AdaptationCheckpoint.enrollment_id == enrollment_id,
            AdaptationParticipantForm.revoked_at.is_(None),
        )
    )
    for form in forms.scalars().all():
        form.revoked_at = now
    await db.flush()
    return enrollment


async def change_enrollment_manager(
    db: AsyncSession,
    *,
    enrollment_id: int,
    manager_user_id: str,
    manager_name: Optional[str],
) -> AdaptationEnrollment:
    enrollment = await db.get(AdaptationEnrollment, enrollment_id)
    if not enrollment:
        raise LookupError("Enrollment not found")
    enrollment.manager_user_id = manager_user_id.strip()
    enrollment.manager_name = (manager_name or "").strip() or None
    forms = await db.execute(
        select(AdaptationParticipantForm)
        .join(AdaptationCheckpoint)
        .where(
            AdaptationCheckpoint.enrollment_id == enrollment_id,
            AdaptationParticipantForm.role == ROLE_MANAGER,
            AdaptationParticipantForm.submitted_at.is_(None),
        )
    )
    for form in forms.scalars().all():
        form.participant_user_id = enrollment.manager_user_id
        form.token = secrets.token_urlsafe(32)
        form.sent_at = None
    await db.flush()
    return enrollment


async def add_action_record(db: AsyncSession, *, enrollment_id: int, **values) -> AdaptationActionRecord:
    if not await db.get(AdaptationEnrollment, enrollment_id):
        raise LookupError("Enrollment not found")
    row = AdaptationActionRecord(enrollment_id=enrollment_id, **values)
    db.add(row)
    await db.flush()
    return row


async def list_action_records(db: AsyncSession, *, enrollment_id: int) -> list[AdaptationActionRecord]:
    if not await db.get(AdaptationEnrollment, enrollment_id):
        raise LookupError("Enrollment not found")
    result = await db.execute(
        select(AdaptationActionRecord)
        .where(AdaptationActionRecord.enrollment_id == enrollment_id)
        .order_by(AdaptationActionRecord.created_at.desc(), AdaptationActionRecord.id.desc())
    )
    return list(result.scalars().all())


async def update_action_record(
    db: AsyncSession, *, action_id: int, status: str, effect: Optional[str]
) -> AdaptationActionRecord:
    row = await db.get(AdaptationActionRecord, action_id)
    if not row:
        raise LookupError("Action record not found")
    row.status = status
    row.effect = (effect or "").strip() or None
    await db.flush()
    return row


async def archive_enrollment(
    db: AsyncSession, *, enrollment_id: int, reason: str
) -> AdaptationEnrollment:
    result = await db.execute(
        select(AdaptationEnrollment)
        .where(AdaptationEnrollment.id == enrollment_id)
        .with_for_update()
    )
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise LookupError("Enrollment not found")
    if not reason.strip():
        raise ValueError("Укажите причину архивирования")
    if enrollment.archived:
        return enrollment
    enrollment.archived = True
    enrollment.archive_reason = reason.strip()
    deliveries = await db.execute(
        select(AdaptationNotificationDelivery)
        .join(AdaptationCheckpoint)
        .where(
            AdaptationCheckpoint.enrollment_id == enrollment_id,
            AdaptationNotificationDelivery.status.in_(["pending", "failed"]),
        )
    )
    for delivery in deliveries.scalars().all():
        delivery.status = "cancelled"
    forms = await db.execute(
        select(AdaptationParticipantForm)
        .join(AdaptationCheckpoint)
        .where(
            AdaptationCheckpoint.enrollment_id == enrollment_id,
            AdaptationParticipantForm.revoked_at.is_(None),
        )
    )
    revoked_at = datetime.now(timezone.utc)
    for form in forms.scalars().all():
        form.revoked_at = revoked_at
    await db.flush()
    return enrollment


async def restart_enrollment(
    db: AsyncSession,
    *,
    enrollment_id: int,
    start_date: date,
    reason: str,
    route: str,
    actor_user_id: str,
) -> AdaptationEnrollment:
    """Close the current process and create a linked case after an HR-confirmed transfer."""
    source = await db.get(AdaptationEnrollment, enrollment_id)
    if not source or not source.employee_id:
        raise LookupError("Enrollment not found or not linked to ERP")
    if not reason.strip():
        raise ValueError("Укажите основание новой адаптации")
    now = datetime.now(timezone.utc)
    source.closed = True
    source.finalized_at = source.finalized_at or now
    source.finalized_by = source.finalized_by or actor_user_id
    source.decision_comment = reason.strip()
    forms = await db.execute(
        select(AdaptationParticipantForm)
        .join(AdaptationCheckpoint)
        .where(
            AdaptationCheckpoint.enrollment_id == enrollment_id,
            AdaptationParticipantForm.revoked_at.is_(None),
        )
    )
    for form in forms.scalars().all():
        form.revoked_at = now
    deliveries = await db.execute(
        select(AdaptationNotificationDelivery)
        .join(AdaptationCheckpoint)
        .where(
            AdaptationCheckpoint.enrollment_id == enrollment_id,
            AdaptationNotificationDelivery.status.in_(["pending", "failed"]),
        )
    )
    for delivery in deliveries.scalars().all():
        delivery.status = "cancelled"
    await db.flush()
    return await _enroll_employee(
        db,
        employee_id=source.employee_id,
        route=route,
        start_date=start_date,
        manager_user_id=source.manager_user_id,
        manager_name=source.manager_name,
    )


async def submit_answer(
    db: AsyncSession,
    *,
    checkpoint_id: int,
    role: str,
    payload: dict,
    now: Optional[datetime] = None,
    actor_user_id: Optional[str] = None,
    actor_name: Optional[str] = None,
) -> AdaptationAnswer:
    # A public form lookup has already placed this checkpoint in the identity
    # map without its answers. AsyncSession.get() may return that same object
    # without applying loader options; reading cp.answers then causes
    # MissingGreenlet. An explicit SELECT always executes and populate_existing
    # refreshes loader state on an identity-mapped checkpoint.
    result = await db.execute(
        select(AdaptationCheckpoint)
        .options(
            selectinload(AdaptationCheckpoint.answers),
            selectinload(AdaptationCheckpoint.enrollment)
            .selectinload(AdaptationEnrollment.checkpoints)
            .selectinload(AdaptationCheckpoint.answers),
            # populate_existing revisits the current checkpoint through this
            # collection. Load its back-reference in the same SQL statement so
            # the refreshed checkpoint cannot lose enrollment and lazy-load it.
            selectinload(AdaptationCheckpoint.enrollment)
            .selectinload(AdaptationEnrollment.checkpoints)
            .joinedload(AdaptationCheckpoint.enrollment),
        )
        .where(AdaptationCheckpoint.id == checkpoint_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    cp = result.scalar_one_or_none()
    if not cp:
        raise LookupError("Checkpoint not found")
    if cp.closed or cp.finalized_at:
        raise ValueError("Этап уже зафиксирован и не принимает ответы")
    if cp.enrollment.closed or cp.enrollment.archived:
        raise ValueError("Кейс адаптации завершён и не принимает ответы")
    allowed = roles_for_kind(cp.kind)
    if role not in allowed:
        raise ValueError(f"Роль {role} не участвует в этапе {cp.kind}")
    moment = now or datetime.now(timezone.utc)
    loaded_answers = list(cp.answers)
    existing = next((a for a in loaded_answers if a.role == role), None)
    late_after_force = bool(getattr(cp, "forced_completed_at", None))
    if existing and role != ROLE_HR and not late_after_force:
        raise ValueError("Ответы уже отправлены и заблокированы")
    normalized_payload = validate_answer_payload(
        cp.kind,
        role,
        payload,
        core_history=core_history_from_checkpoint(cp),
    )
    if existing:
        existing.version = int(getattr(existing, "version", 1) or 1) + 1
        existing.payload = normalized_payload
        existing.submitted_at = moment
        existing.actor_user_id = actor_user_id
        existing.actor_name = actor_name
        existing.locked = role != ROLE_HR
        answer = existing
    else:
        answer = AdaptationAnswer(
            checkpoint_id=checkpoint_id,
            role=role,
            payload=normalized_payload,
            submitted_at=moment,
            actor_user_id=actor_user_id,
            actor_name=actor_name,
            version=1,
            locked=role != ROLE_HR,
        )
        db.add(answer)
        cp.answers.append(answer)
        loaded_answers.append(answer)
    if role == ROLE_EMPLOYEE and cp.fact_date is None:
        cp.fact_date = aware(moment).date()
    try:
        await db.flush()
        db.add(
            AdaptationAnswerVersion(
                answer_id=answer.id,
                version=answer.version,
                payload=dict(answer.payload or {}),
                submitted_at=answer.submitted_at,
                actor_user_id=actor_user_id,
                actor_name=actor_name,
            )
        )
        form_result = await db.execute(
            select(AdaptationParticipantForm).where(
                AdaptationParticipantForm.checkpoint_id == checkpoint_id,
                AdaptationParticipantForm.role == role,
            ).with_for_update()
        )
        participant_form = form_result.scalar_one_or_none()
        if participant_form:
            participant_form.submitted_at = moment
            participant_form.locked = role != ROLE_HR
        required_external = {r for r in roles_for_kind(cp.kind) if r != ROLE_HR}
        submitted = {a.role for a in loaded_answers}
        if required_external.issubset(submitted):
            cp.fact_date = aware(moment).date()
        await db.flush()
    except IntegrityError as exc:
        raise ValueError("Ответы этой роли уже сохранены") from exc
    except DBAPIError as exc:
        raise ValueError(_human_db_error(exc)) from exc
    return answer


async def list_checkpoints(
    db: AsyncSession,
    *,
    year: int,
    month: int,
    q: Optional[str] = None,
    department: Optional[str] = None,
    kind: Optional[str] = None,
    risk: Optional[str] = None,
    route: Optional[str] = None,
    outcome: Optional[str] = None,
    status: Optional[str] = None,
    hide_completed: bool = False,
    archived: bool = False,
    page: int = 1,
    page_size: int = 100,
    now: Optional[datetime] = None,
) -> dict:
    last_day = monthrange(year, month)[1]
    period_start = date(year, month, 1)
    period_end = date(year, month, last_day)
    stmt = (
        select(AdaptationCheckpoint)
        .options(
            selectinload(AdaptationCheckpoint.answers),
            selectinload(AdaptationCheckpoint.participant_forms),
            selectinload(AdaptationCheckpoint.enrollment).selectinload(AdaptationEnrollment.employee),
            selectinload(AdaptationCheckpoint.enrollment).selectinload(AdaptationEnrollment.temporary_employee),
            selectinload(AdaptationCheckpoint.enrollment)
            .selectinload(AdaptationEnrollment.checkpoints)
            .selectinload(AdaptationCheckpoint.answers),
        )
        .join(AdaptationEnrollment, AdaptationCheckpoint.enrollment_id == AdaptationEnrollment.id)
        .where(AdaptationCheckpoint.plan_date <= period_end)
        .where(AdaptationEnrollment.archived.is_(archived))
        .order_by(AdaptationCheckpoint.plan_date.asc(), AdaptationCheckpoint.id.asc())
    )
    result = await db.execute(stmt)
    checkpoints = list(result.scalars().unique().all())

    moment = now or datetime.now(timezone.utc)
    today = aware(moment).date()
    week_start, week_end = _week_bounds(today)

    settings_result = await db.execute(
        select(AdaptationModuleSettings).order_by(AdaptationModuleSettings.id).limit(1)
    )
    settings = settings_result.scalar_one_or_none()
    status_options = _status_options(settings)
    serialized = []
    for cp in checkpoints:
        enrollment = _loaded_relation(cp, "enrollment")
        employee = None
        if enrollment is not None:
            employee = _loaded_relation(enrollment, "employee") or _loaded_relation(
                enrollment, "temporary_employee"
            )
        if employee is None:
            logger.error(
                "Adaptation checkpoint %s skipped: employee is not linked",
                cp.id,
            )
            continue
        try:
            serialized.append(
                serialize_checkpoint(cp, employee, now=moment, **status_options)
            )
        except Exception:
            # A malformed legacy answer must not make the entire adaptation
            # register unavailable. The checkpoint id in the log is sufficient
            # to repair that record separately.
            logger.exception(
                "Adaptation checkpoint %s cannot be serialized and was skipped",
                cp.id,
            )

    overdue = this_week = ready_hr = 0
    visible = []
    for row in serialized:
        in_period = period_start <= row["plan_date"] <= period_end
        # Active overdue stages remain visible until handled. Archive browsing
        # is deliberately bounded by the selected month.
        if in_period or (not archived and row["status"] == STATUS_OVERDUE):
            visible.append(row)
        bucket = attention_bucket(row["status"], row["plan_date"], week_start, week_end)
        if bucket == "overdue":
            overdue += 1
        elif in_period and bucket == "this_week":
            this_week += 1
        elif in_period and bucket == "ready_hr":
            ready_hr += 1

    items = visible
    needle = (q or "").strip().lower()
    if needle:
        items = [
            r
            for r in items
            if needle in (r["full_name"] or "").lower() or needle in (r["position"] or "").lower()
        ]
    if department:
        items = [r for r in items if r["department"] == department]
    if kind:
        items = [r for r in items if r["kind"] == kind]
    if risk:
        items = [r for r in items if r["risk"] == risk]
    if route:
        items = [r for r in items if r["route"] == route]
    if outcome:
        items = [r for r in items if r["outcome"] == outcome]
    if status:
        items = [r for r in items if r["status"] == status]
    if hide_completed:
        items = [r for r in items if r["status"] != STATUS_COMPLETED]

    horizon = today + timedelta(days=14)

    def _sort_key(row: dict):
        if row["status"] == STATUS_OVERDUE:
            return (0, row["plan_date"], row["id"])
        if row["status"] == STATUS_COMPLETED:
            return (3, row["plan_date"], row["id"])
        if row["plan_date"] <= horizon:
            return (1, row["plan_date"], row["id"])
        return (2, row["plan_date"], row["id"])

    items = sorted(items, key=_sort_key)
    total = len(items)
    safe_page = max(1, int(page))
    safe_page_size = min(500, max(1, int(page_size)))
    offset = (safe_page - 1) * safe_page_size
    items = items[offset:offset + safe_page_size]

    months_ru = (
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    )
    period_label = f"Этапы {months_ru[month - 1]}"
    return {
        "period_label": period_label,
        "year": year,
        "month": month,
        "attention": {"overdue": overdue, "this_week": this_week, "ready_hr": ready_hr},
        "items": items,
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
    }


async def get_checkpoint_detail(db: AsyncSession, checkpoint_id: int, *, now=None) -> dict:
    # Pending answers are flushed by the caller/autoflush. Re-populating this
    # cyclic graph expires already-loaded relationships while serializing it;
    # ordinary eager loading preserves the current session's updated objects.
    stmt = (
        select(AdaptationCheckpoint)
        .options(
            selectinload(AdaptationCheckpoint.answers),
            selectinload(AdaptationCheckpoint.participant_forms),
            selectinload(AdaptationCheckpoint.enrollment).selectinload(AdaptationEnrollment.employee),
            selectinload(AdaptationCheckpoint.enrollment).selectinload(AdaptationEnrollment.temporary_employee),
            selectinload(AdaptationCheckpoint.enrollment)
            .selectinload(AdaptationEnrollment.checkpoints)
            .selectinload(AdaptationCheckpoint.answers),
        )
        .where(AdaptationCheckpoint.id == checkpoint_id)
    )
    result = await db.execute(stmt)
    cp = result.scalar_one_or_none()
    if not cp:
        raise LookupError("Checkpoint not found")
    enrollment = cp.enrollment
    employee = (enrollment.employee or enrollment.temporary_employee) if enrollment else None
    if employee is None:
        raise LookupError("Checkpoint not found")
    settings_result = await db.execute(
        select(AdaptationModuleSettings).order_by(AdaptationModuleSettings.id).limit(1)
    )
    settings = settings_result.scalar_one_or_none()
    status_options = _status_options(settings)
    row = serialize_checkpoint(cp, employee, now=now, include_form=True, **status_options)
    row["core_history"] = core_history_from_checkpoint(cp)
    row["stage_history"] = [
        {"kind": point.kind, "plan_date": point.plan_date, "fact_date": point.fact_date,
         "forced_reason": point.forced_reason,
         "answers": [{"role": answer.role, "payload": dict(answer.payload or {})} for answer in point.answers]}
        for point in enrollment.checkpoints
        if point.plan_date <= cp.plan_date
    ]
    return row


def core_history_from_checkpoint(cp: AdaptationCheckpoint) -> dict:
    history = {}
    enrollment = _loaded_relation(cp, "enrollment")
    others = sorted(
        _loaded_relation(enrollment, "checkpoints", []) or [],
        key=lambda item: (item.plan_date, item.id),
    )
    for other in others:
        if other.id == cp.id:
            continue
        if other.plan_date > cp.plan_date:
            continue
        answers = _loaded_relation(other, "answers", []) or []
        emp = next((a for a in answers if a.role == ROLE_EMPLOYEE), None)
        payload = dict(emp.payload or {}) if emp else {}
        for qid in CORE_EMPLOYEE_IDS:
            if payload.get(qid) not in (None, ""):
                history[qid] = payload.get(qid)
        manager = next((a for a in answers if a.role == ROLE_MANAGER), None)
        manager_payload = dict(manager.payload or {}) if manager else {}
        for qid in CORE_MANAGER_IDS:
            if manager_payload.get(qid) not in (
                None,
                "",
                "na",
                "insufficient_observations",
            ):
                history[qid] = manager_payload.get(qid)
    return history


async def get_enrollment_detail(db: AsyncSession, enrollment_id: int, *, now=None) -> dict:
    stmt = (
        select(AdaptationCheckpoint)
        .options(
            selectinload(AdaptationCheckpoint.answers),
            selectinload(AdaptationCheckpoint.participant_forms),
            selectinload(AdaptationCheckpoint.enrollment).selectinload(AdaptationEnrollment.employee),
            selectinload(AdaptationCheckpoint.enrollment).selectinload(AdaptationEnrollment.temporary_employee),
            selectinload(AdaptationCheckpoint.enrollment)
            .selectinload(AdaptationEnrollment.checkpoints)
            .selectinload(AdaptationCheckpoint.answers),
        )
        .where(AdaptationCheckpoint.enrollment_id == enrollment_id)
        .order_by(AdaptationCheckpoint.plan_date.asc())
        .execution_options(populate_existing=True)
    )
    result = await db.execute(stmt)
    checkpoints = list(result.scalars().unique().all())
    if not checkpoints:
        raise LookupError("Enrollment not found")
    enrollment = checkpoints[0].enrollment
    employee = (enrollment.employee or enrollment.temporary_employee) if enrollment else None
    if employee is None:
        raise LookupError("Enrollment not found")
    rows = [serialize_checkpoint(cp, employee, now=now) for cp in checkpoints]
    cores = {qid: [] for qid in CORE_EMPLOYEE_IDS}
    manager_cores = {qid: [] for qid in CORE_MANAGER_IDS}
    for row in rows:
        payload = next((a.get("payload") or {} for a in row.get("answers") or [] if a.get("role") == ROLE_EMPLOYEE), {})
        for qid in CORE_EMPLOYEE_IDS:
            if payload.get(qid) not in (None, ""):
                cores[qid].append({"kind": row["kind"], "plan_date": row["plan_date"], "value": payload.get(qid)})
        manager_payload = next((a.get("payload") or {} for a in row.get("answers") or [] if a.get("role") == ROLE_MANAGER), {})
        for qid in CORE_MANAGER_IDS:
            if manager_payload.get(qid) not in (
                None,
                "",
                "na",
                "недостаточно наблюдений",
                "insufficient_observations",
            ):
                manager_cores[qid].append({"kind": row["kind"], "plan_date": row["plan_date"], "value": manager_payload.get(qid)})
    return {
        "enrollment_id": enrollment_id,
        "employee_id": enrollment.employee_id,
        "temporary_employee_id": enrollment.temporary_employee_id,
        "full_name": employee.full_name,
        "position": employee.position,
        "department": employee.department,
        "date_hired": getattr(enrollment, "start_date", None) or getattr(employee, "date_hired", None),
        "route": enrollment.route,
        "manager_user_id": enrollment.manager_user_id,
        "manager_name": enrollment.manager_name,
        "responsible_hr_user_id": enrollment.responsible_hr_user_id,
        "responsible_hr_name": enrollment.responsible_hr_name,
        "allow_personal_telegram_fallback": enrollment.allow_personal_telegram_fallback,
        "closed": enrollment.closed,
        "archived": enrollment.archived,
        "archive_reason": enrollment.archive_reason,
        "outcome": enrollment.outcome,
        "risk": enrollment.risk,
        "decision_comment": enrollment.decision_comment,
        "checkpoints": rows,
        "core_series": cores,
        "manager_core_series": manager_cores,
        "take_links": [
            {
                **link,
                "checkpoint_id": row["id"],
                "kind": row["kind"],
                "kind_label": row["kind_label"],
                "plan_date": row["plan_date"],
                "role_label": TAKE_ROLE_LABELS.get(link["role"], link["role"]),
            }
            for row in rows
            for link in (row.get("form_links") or [])
        ],
    }


async def reports_for_enrollment(db: AsyncSession, enrollment_id: int, *, now=None) -> dict:
    data = await get_enrollment_detail(db, enrollment_id, now=now)
    return build_reports(data["checkpoints"])


async def reports_for_period(db: AsyncSession, *, year: int, month: int, now=None) -> dict:
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    # Reports include archives, without operational overdue spillover or paging.
    result = await db.execute(select(AdaptationCheckpoint).where(
        AdaptationCheckpoint.plan_date.between(start, end),
    ).options(
        selectinload(AdaptationCheckpoint.answers),
        selectinload(AdaptationCheckpoint.participant_forms),
        selectinload(AdaptationCheckpoint.enrollment).selectinload(AdaptationEnrollment.employee),
        selectinload(AdaptationCheckpoint.enrollment).selectinload(AdaptationEnrollment.temporary_employee),
        selectinload(AdaptationCheckpoint.enrollment).selectinload(AdaptationEnrollment.checkpoints)
        .selectinload(AdaptationCheckpoint.answers),
    ).order_by(AdaptationCheckpoint.plan_date, AdaptationCheckpoint.id))
    rows = []
    for checkpoint in result.scalars().unique().all():
        enrollment = checkpoint.enrollment
        employee = enrollment.employee or enrollment.temporary_employee
        if employee is not None:
            if getattr(employee, "date_fired", None) and not checkpoint.fact_date:
                continue  # Preserve performed work, not cancelled future stages.
            rows.append(serialize_checkpoint(checkpoint, employee, now=now))
    report = build_reports(rows)
    report.pop("probation", None)
    return report


def catalog_payload() -> dict:
    return catalog()
