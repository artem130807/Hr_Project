from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zipfile import ZipFile
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import configure_mappers

from app.adaptation.access import (
    AdaptationPrincipal,
    redact_checkpoint,
    require_enrollment_access,
)
from app.adaptation.documents import (
    build_zip,
    content_hash,
    document_types_for_kind,
    render_document,
    render_filename,
)
from app.adaptation.notifications import (
    DELIVERY_GRACE_PERIOD,
    MAX_AUTOMATIC_ATTEMPTS,
    _create_missing_deliveries,
    _schedule,
    _should_cancel,
    is_stale_delivery,
    stage_display_name,
)
from app.adaptation.rules import assess_risk, compute_status
from app.db.v1.models import AdaptationCheckpoint


def test_notification_stage_uses_human_readable_name():
    assert stage_display_name("month_1") == "1 месяц"
    assert stage_display_name("custom_stage") == "custom_stage"


def test_old_notifications_are_not_backfilled_after_deploy():
    now = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    assert is_stale_delivery(now - DELIVERY_GRACE_PERIOD - timedelta(seconds=1), now)
    assert not is_stale_delivery(now - DELIVERY_GRACE_PERIOD, now)
    assert MAX_AUTOMATIC_ATTEMPTS == 3


def test_force_completed_checkpoint_cancels_remaining_notifications():
    checkpoint = SimpleNamespace(
        closed=False,
        forced_completed_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
        enrollment=SimpleNamespace(archived=False),
    )
    delivery = SimpleNamespace(role="employee", event="reminder")
    assert _should_cancel(checkpoint, delivery)


@pytest.mark.asyncio
async def test_historical_checkpoint_deliveries_start_cancelled():
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    added = []
    db.add = added.append
    checkpoint = SimpleNamespace(
        id=8,
        kind="week_1",
        plan_date=date(2026, 8, 1),
        answers=[],
        participant_forms=[
            SimpleNamespace(role="employee"),
            SimpleNamespace(role="hr"),
        ],
        closed=False,
        forced_completed_at=None,
        enrollment=SimpleNamespace(archived=False),
    )

    await _create_missing_deliveries(
        db,
        [checkpoint],
        tz=ZoneInfo("Europe/Samara"),
        overdue_enabled=True,
        overdue_time=time(9),
        now=datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
    )

    assert added
    assert {delivery.status for delivery in added} == {"cancelled"}


def _document_row():
    return {
        "full_name": "Иванов Иван Иванович",
        "position": "Инженер",
        "kind": "month_2",
        "kind_label": "2 месяца",
        "plan_date": date(2026, 9, 10),
        "fact_date": date(2026, 9, 10),
        "outcome": "Стабильно",
        "risk": "low",
        "risk_label": "Низкий",
        "risk_signals": {"strong": [], "medium": [], "protective": ["core_e1"]},
        "answers": [
            {"role": "employee", "payload": {"core_e1": 5, "comment": "Всё понятно"}},
            {"role": "hr", "payload": {"hr_comment": "Без замечаний"}},
        ],
    }


def test_sqlalchemy_adaptation_mappers_are_valid():
    configure_mappers()


def test_intention_to_leave_alone_is_not_critical():
    result = assess_risk(
        {"core_e1": 5, "core_e2": 5, "core_e3": 5, "core_e4": 5, "core_e5": 5, "m2_stay": 1},
        kind="month_2",
    )
    assert result["risk"] == "medium"
    assert "intention_to_leave" in result["strong"]


def test_multiple_independent_strong_signals_are_critical():
    result = assess_risk(
        {"core_e1": 1, "core_e2": 1, "core_e3": 1, "core_e4": 5, "core_e5": 5},
        kind="month_2",
    )
    assert result["risk"] == "critical"


def test_risk_thresholds_can_be_tuned_without_schema_changes():
    payload = {"core_e1": 1, "core_e2": 1, "core_e3": 4, "core_e4": 4, "core_e5": 4}
    assert assess_risk(payload, kind="month_2")["risk"] == "high"
    assert assess_risk(payload, kind="month_2", config={"critical_min_strong": 2})["risk"] == "critical"


def test_manager_cannot_receive_private_answers_or_links():
    principal = AdaptationPrincipal("manager-1", "leader")
    row = {
        "answers": [{"role": "employee"}, {"role": "manager"}, {"role": "hr"}],
        "form": {"employee": []},
        "form_links": [{"token": "secret"}],
        "employee_take_token": "secret",
        "core_history": {"core_e1": 1},
    }
    safe = redact_checkpoint(row, principal)
    assert safe["answers"] == [{"role": "manager"}]
    assert "form" not in safe and "form_links" not in safe and "core_history" not in safe
    assert "employee_take_token" not in safe


def test_manager_access_is_scoped_to_assigned_enrollment():
    enrollment = SimpleNamespace(manager_user_id="manager-2")
    with pytest.raises(HTTPException) as exc:
        require_enrollment_access(AdaptationPrincipal("manager-1", "leader"), enrollment)
    assert exc.value.status_code == 403


def test_overdue_schedule_uses_configured_time_and_can_be_disabled():
    checkpoint = SimpleNamespace(kind="week_1", plan_date=date(2026, 9, 10))
    tz = ZoneInfo("Europe/Samara")
    enabled = _schedule(checkpoint, tz, overdue_enabled=True, overdue_time=time(10, 30))
    next_day = next(at for role, event, at in enabled if role == "employee" and event == "next_day")
    assert next_day.astimezone(tz).time() == time(10, 30)
    disabled = _schedule(checkpoint, tz, overdue_enabled=False, overdue_time=time(10, 30))
    assert all(event not in {"next_day", "overdue_12"} for _, event, _ in disabled)


def test_overdue_status_uses_module_switch_and_time():
    now = datetime(2026, 9, 11, 5, 30, tzinfo=timezone.utc)  # 09:30 Samara
    assert compute_status(kind="week_1", plan_date=date(2026, 9, 10), answers=[], now=now, overdue_enabled=False) == "collecting"
    assert compute_status(kind="week_1", plan_date=date(2026, 9, 10), answers=[], now=now, overdue_time=time(10, 0)) == "collecting"
    assert compute_status(kind="week_1", plan_date=date(2026, 9, 10), answers=[], now=now, overdue_time=time(9, 0)) == "overdue"


def test_document_matrix_and_safe_filename():
    assert "conclusion" in document_types_for_kind("month_2")
    assert document_types_for_kind("control_2m") == []
    name = render_filename("{ФИО}/{Тип}_v{Версия}", {"ФИО": "Иванов", "Тип": "Отчёт", "Версия": 2}, extension="pdf")
    assert name == "Иванов_Отчёт_v2.pdf"


def test_real_docx_pdf_generation_and_zip_versions():
    pytest.importorskip("docx")
    pytest.importorskip("reportlab")
    row = _document_row()
    docx = render_document(row, "employee_answers", "docx", [])
    pdf = render_document(row, "manager_safe", "pdf", ["HR"])
    assert docx.startswith(b"PK")
    assert pdf.startswith(b"%PDF")
    assert len(content_hash(pdf)) == 64
    archive = build_zip([("report.pdf", pdf), ("report.pdf", pdf)])
    with ZipFile(BytesIO(archive)) as zipped:
        assert zipped.namelist() == ["report.pdf", "report_2.pdf"]
