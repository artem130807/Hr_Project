from types import SimpleNamespace
import pytest
from fastapi import Depends, HTTPException
from app.adaptation.access import principal_from_claims, require_hr, require_enrollment_access, redact_checkpoint


@pytest.mark.parametrize("claims", [None, [], "admin", 1, Depends()])
def test_malformed_identity_never_grants_privileged_access(claims):
    with pytest.raises(HTTPException) as exc:
        principal_from_claims(claims)
    assert exc.value.status_code == 401


@pytest.mark.parametrize("claims", [{}, {"role": "employee"}, {"role": "leader", "user_id": "a"}])
def test_non_hr_cannot_administer_documents_or_adaptation(claims):
    with pytest.raises(HTTPException) as exc:
        require_hr(principal_from_claims(claims))
    assert exc.value.status_code == 403


def test_manager_scope_and_sensitive_answer_redaction():
    principal = principal_from_claims({"role": "leader", "user_id": "a"})
    require_enrollment_access(principal, SimpleNamespace(manager_user_id="a"))
    with pytest.raises(HTTPException):
        require_enrollment_access(principal, SimpleNamespace(manager_user_id="b"))
    original = {"answers": [{"role": "employee", "payload": "private"}, {"role": "hr"}, {"role": "manager"}],
                "form_links": ["secret"], "employee_take_token": "secret", "core_history": {"private": 5}, "talk_hr": True}
    safe = redact_checkpoint(original, principal)
    assert safe["answers"] == [{"role": "manager"}]
    assert "employee_take_token" not in safe and "form_links" not in safe and "core_history" not in safe
    assert safe["talk_hr"] is False
    assert len(original["answers"]) == 3
