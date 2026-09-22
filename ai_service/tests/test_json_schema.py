"""Unit tests for OpenAI JSON Schema sanitizer."""
from app.agent.v1.json_schema import openai_json_schema
from app.schemas.v1.candidates import CandidateEvaluateResponse
from app.schemas.v1.vacancies import VacancyDescriptionSalaryCombineResponse
from app.schemas.v1.tests import TestGenerateResponse


def test_candidate_schema_is_strict_object():
    schema = openai_json_schema(CandidateEvaluateResponse)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"comment", "score"}
    assert "$defs" not in schema
    assert "$ref" not in str(schema)


def test_salary_optional_fields_are_required_keys():
    schema = openai_json_schema(VacancyDescriptionSalaryCombineResponse)
    assert set(schema["required"]) == {"description", "salary_from", "salary_to"}
    assert schema["additionalProperties"] is False


def test_nested_questions_inlined():
    schema = openai_json_schema(TestGenerateResponse)
    questions = schema["properties"]["questions"]
    items = questions.get("items") or {}
    assert items.get("type") == "object"
    assert items.get("additionalProperties") is False
    assert "text" in items.get("properties", {})


def test_salary_schema_keeps_description_property():
    schema = openai_json_schema(VacancyDescriptionSalaryCombineResponse)
    assert "description" in schema["properties"]
    assert schema["properties"]["description"].get("type") == "string"
