from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.contact_directory import normalize_contact, resolve_adaptation_recipient
from app.schemas.v1.contact_directory import ContactPointIn
from app.schemas.v1.adaptation import AdaptationRotateTokenIn
from app.db.v1.models import ContactPoint


def contact(cid, usage, *, primary=False, priority=100, active=True, allowed=True, verified=True, owner="employee"):
    return SimpleNamespace(
        id=cid, contact_type="telegram", usage_type=usage, owner_type=owner,
        is_primary=primary, priority=priority, is_active=active,
        allow_adaptation=allowed, verified_at=datetime.now(timezone.utc) if verified else None,
        telegram_chat_id=str(1000 + cid),
    )


def test_contact_normalization():
    assert normalize_contact("telegram", " @Ivan_Test ") == "ivan_test"
    assert normalize_contact("phone", "8 (999) 123-45-67") == "+79991234567"
    assert normalize_contact("email", " USER@Example.COM ") == "user@example.com"


@pytest.mark.parametrize("kind,value", [("telegram", "@x"), ("phone", "123"), ("email", "bad")])
def test_invalid_contacts_are_rejected(kind, value):
    with pytest.raises(ValueError):
        normalize_contact(kind, value)


def test_work_telegram_has_priority_and_shared_is_never_selected():
    result = resolve_adaptation_recipient([
        contact(1, "shared", primary=True, owner="department"),
        contact(2, "personal", primary=True),
        contact(3, "work_personal", primary=True),
    ], allow_personal_fallback=True, responsible_hr_user_id="hr-1")
    assert result.contact_id == 3
    assert result.reason == "work_personal_primary"


def test_personal_requires_explicit_fallback():
    contacts = [contact(2, "personal", primary=True)]
    denied = resolve_adaptation_recipient(contacts, allow_personal_fallback=False, responsible_hr_user_id="hr-1")
    allowed = resolve_adaptation_recipient(contacts, allow_personal_fallback=True, responsible_hr_user_id="hr-1")
    assert denied.recipient_type == "responsible_hr"
    assert denied.recipient_user_id == "hr-1"
    assert allowed.contact_id == 2


def test_missing_contact_falls_back_to_hr_role():
    result = resolve_adaptation_recipient([], allow_personal_fallback=False, responsible_hr_user_id=None)
    assert result.recipient_type == "hr_role"


def test_equal_priority_uses_stable_oldest_contact():
    result = resolve_adaptation_recipient([
        contact(9, "work_personal", priority=10),
        contact(4, "work_personal", priority=10),
    ], allow_personal_fallback=False, responsible_hr_user_id=None)
    assert result.contact_id == 4


def test_contact_schema_disallows_adaptation_for_email():
    with pytest.raises(ValueError):
        ContactPointIn(contact_type="email", value="a@example.com", usage_type="personal", allow_adaptation=True)


def test_rotate_token_requires_a_meaningful_reason():
    with pytest.raises(ValueError):
        AdaptationRotateTokenIn(confirmed=True, reason="x")
    assert AdaptationRotateTokenIn(confirmed=True, reason="утечка ссылки").confirmed is True


def test_contact_model_has_database_level_safety_indexes_and_checks():
    indexes = {index.name for index in ContactPoint.__table__.indexes}
    constraints = {constraint.name for constraint in ContactPoint.__table__.constraints}
    assert {"uq_contact_personal_active", "uq_contact_department_active_value", "uq_contact_employee_primary"} <= indexes
    assert {
        "ck_contact_type", "ck_contact_usage_type", "ck_contact_owner_type",
        "ck_contact_one_owner", "ck_department_contact_shared",
        "ck_contact_primary_employee", "ck_contact_adaptation_target",
    } <= constraints


def test_contact_and_adaptation_contract_routes_are_registered():
    from main import app

    routes = {(route.path, method) for route in app.routes for method in getattr(route, "methods", set())}
    assert ("/v1/employees/{employee_id}/contacts", "GET") in routes
    assert ("/v1/organization/departments/{department_id}", "GET") in routes
    assert ("/v1/adaptation/enrollments/{enrollment_id}/take-links", "GET") in routes
    assert ("/v1/adaptation/forms/{form_id}/rotate-token", "POST") in routes


def test_contact_directory_migration_is_applied_on_startup():
    from pathlib import Path

    main_source = Path(__file__).resolve().parents[1].joinpath("main.py").read_text(encoding="utf-8")
    migration = Path(__file__).resolve().parents[1].joinpath("migrations", "contact_directory.sql")
    assert migration.is_file()
    assert '"contact_directory.sql"' in main_source
    assert 'split("-- migrate:split")' in main_source
    assert migration.read_text(encoding="utf-8").count("-- migrate:split") >= 10
    assert "Contact directory migration failed" in main_source
