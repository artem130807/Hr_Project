"""Extra coverage: unviewed detection + resume completeness for auto-reject."""
from app.utils.vacancy_filter_match import (
    is_unviewed_negotiation,
    resume_has_filter_fields,
)


class TestIsUnviewedNegotiation:
    def test_has_updates_wins(self):
        assert is_unviewed_negotiation({"viewed_by_opponent": True, "has_updates": True}) is True

    def test_explicitly_viewed_skipped(self):
        assert is_unviewed_negotiation(
            {"viewed_by_opponent": True, "employer_state": {"id": "response"}}
        ) is False

    def test_explicitly_unviewed(self):
        assert is_unviewed_negotiation({"viewed_by_opponent": False}) is True

    def test_employer_state_response_when_viewed_unknown(self):
        assert is_unviewed_negotiation({"employer_state": {"id": "response"}}) is True
        assert is_unviewed_negotiation({"employer_state": "response"}) is True
        assert is_unviewed_negotiation({"employer_state": {"id": "consider"}}) is False

    def test_invalid_payload(self):
        assert is_unviewed_negotiation(None) is False
        assert is_unviewed_negotiation("x") is False


class TestResumeHasFilterFields:
    def test_requires_id_and_signal(self):
        assert resume_has_filter_fields({"id": "r1", "age": 30}) is True
        assert resume_has_filter_fields({"id": "r1"}) is False
        assert resume_has_filter_fields({"age": 30}) is False
        assert resume_has_filter_fields(None) is False
