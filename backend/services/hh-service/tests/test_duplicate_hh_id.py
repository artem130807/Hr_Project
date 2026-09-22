"""Unit tests for HH vacancy publish helpers."""
from app.endpoints.v1.vacancies import _extract_duplicate_hh_id, _sanitize_hh_payload


def test_extract_duplicate_hh_id_from_api_error():
    detail = (
        'HH API Error {"errors":[{"value":"duplicate","found":1,'
        '"items":[{"id":136168977}],"type":"vacancies"}],"request_id":"1786527701"}'
    )
    assert _extract_duplicate_hh_id(detail) == "136168977"


def test_extract_duplicate_hh_id_missing():
    assert _extract_duplicate_hh_id("HH API Error {\"errors\":[]}") is None
    assert _extract_duplicate_hh_id("Could not validate credentials") is None


def test_sanitize_omits_type_and_billing_on_create():
    payload = {
        "name": "Dev",
        "area": {"id": "1"},
        "description": "x" * 200,
        "employment": {"id": "full"},
        "schedule": {"id": "fullDay"},
        "experience": {"id": "noExperience"},
        "professional_roles": [{"id": "10"}],
        "type": {"id": "standard"},
        "billing_type": {"id": "standard"},
        "contacts": {"name": "HR", "phones": []},
    }
    out = _sanitize_hh_payload(payload, for_update=False)
    assert "type" not in out
    assert "billing_type" not in out
    assert out["vacancy_properties"]["properties"][0]["property_type"] == "HH_STANDARD"


def test_sanitize_update_strips_type_and_properties():
    payload = {
        "name": "Dev",
        "area": {"id": "1"},
        "description": "x" * 200,
        "employment": {"id": "full"},
        "schedule": {"id": "fullDay"},
        "experience": {"id": "noExperience"},
        "professional_roles": [{"id": "10"}],
        "type": {"id": "open"},
        "billing_type": {"id": "standard"},
        "vacancy_properties": {"properties": [{"property_type": "HH_STANDARD"}]},
        "contacts": {"name": "HR", "phones": []},
    }
    out = _sanitize_hh_payload(payload, for_update=True)
    assert "type" not in out
    assert "billing_type" not in out
    assert "vacancy_properties" not in out
