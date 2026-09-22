"""Unit tests for HH vacancy publish/update/delete helpers and routes."""
from app.endpoints.v1.vacancies import _ensure_vacancy_properties, router


def test_ensure_vacancy_properties_adds_hh_standard():
    payload = _ensure_vacancy_properties({"name": "Dev"})
    assert payload["vacancy_properties"]["properties"][0]["property_type"] == "HH_STANDARD"


def test_ensure_vacancy_properties_keeps_existing():
    original = {
        "vacancy_properties": {
            "properties": [{"property_type": "HH_PREMIUM"}]
        }
    }
    payload = _ensure_vacancy_properties(original)
    assert payload["vacancy_properties"]["properties"][0]["property_type"] == "HH_PREMIUM"


def test_vacancy_router_has_publish_update_delete():
    by_path = {}
    for route in router.routes:
        path = getattr(route, "path", None)
        methods = set(getattr(route, "methods", set()) or [])
        if not path:
            continue
        by_path.setdefault(path, set()).update(methods)

    assert "POST" in by_path.get("/vacancy/{vacancy_id}", set())
    assert "PUT" in by_path.get("/vacancy/{vacancy_id}", set())
    assert "DELETE" in by_path.get("/vacancy/{vacancy_id}", set())


def test_internal_router_aliases_vacancy_crud():
    from app.endpoints.v1.vacancies import internal_router

    by_path = {}
    for route in internal_router.routes:
        path = getattr(route, "path", None)
        methods = set(getattr(route, "methods", set()) or [])
        if not path:
            continue
        by_path.setdefault(path, set()).update(methods)

    assert "POST" in by_path.get("/vacancy/{vacancy_id}", set())
    assert "PUT" in by_path.get("/vacancy/{vacancy_id}", set())
    assert "DELETE" in by_path.get("/vacancy/{vacancy_id}", set())
