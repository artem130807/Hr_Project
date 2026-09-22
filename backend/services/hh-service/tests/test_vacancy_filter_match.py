"""TDD: VacancyFilter ↔ HH resume matching."""
import pytest

from app.utils.vacancy_filter_match import (
    matches_vacancy_filter,
    extract_resume_city,
    extract_resume_age,
    extract_resume_experience,
    extract_resume_work_formats,
    EXPERIENCE_ORDER,
    map_hh_work_format,
)


def _resume(**overrides):
    base = {
        "id": "r1",
        "age": 30,
        "area": {"id": "1", "name": "Москва"},
        "total_experience": {"months": 24},
        "work_format": [{"id": "REMOTE", "name": "Удалённо"}],
    }
    base.update(overrides)
    return base


class TestExtractors:
    def test_city_from_area(self):
        assert extract_resume_city(_resume()) == "Москва"

    def test_city_missing(self):
        assert extract_resume_city({"area": None}) is None

    def test_age(self):
        assert extract_resume_age(_resume(age=42)) == 42

    def test_experience_bucket(self):
        assert extract_resume_experience(_resume(total_experience={"months": 5})) == "noExperience"
        assert extract_resume_experience(_resume(total_experience={"months": 14})) == "between1And3"
        assert extract_resume_experience(_resume(total_experience={"months": 40})) == "between3And6"
        assert extract_resume_experience(_resume(total_experience={"months": 80})) == "moreThan6"

    def test_work_formats(self):
        assert extract_resume_work_formats(_resume()) == {"REMOTE"}


class TestWorkFormatMapping:
    def test_platform_to_hh(self):
        assert map_hh_work_format("remote") == "REMOTE"
        assert map_hh_work_format("office") == "ON_SITE"
        assert map_hh_work_format("hybrid") == "HYBRID"
        assert map_hh_work_format("field") == "FIELD_WORK"
        assert map_hh_work_format("shift") is None


class TestMatchesVacancyFilter:
    def test_empty_filter_always_matches(self):
        assert matches_vacancy_filter(_resume(), {}) is True
        assert matches_vacancy_filter(_resume(), None) is True

    def test_city_match_case_insensitive(self):
        assert matches_vacancy_filter(_resume(), {"city": "москва"}) is True
        assert matches_vacancy_filter(_resume(), {"city": "Санкт-Петербург"}) is False

    def test_age_range(self):
        assert matches_vacancy_filter(_resume(age=30), {"age_from": 25, "age_to": 35}) is True
        assert matches_vacancy_filter(_resume(age=20), {"age_from": 25}) is False
        assert matches_vacancy_filter(_resume(age=40), {"age_to": 35}) is False

    def test_age_unknown_fails_when_range_set(self):
        assert matches_vacancy_filter(_resume(age=None), {"age_from": 25}) is False

    def test_experience_minimum(self):
        # 24 months → between1And3; filter asks between1And3 → ok
        assert matches_vacancy_filter(
            _resume(total_experience={"months": 24}),
            {"experience": "between1And3"},
        ) is True
        # no experience vs required 1-3 → reject
        assert matches_vacancy_filter(
            _resume(total_experience={"months": 3}),
            {"experience": "between1And3"},
        ) is False
        # moreThan6 meets between1And3 minimum
        assert matches_vacancy_filter(
            _resume(total_experience={"months": 100}),
            {"experience": "between1And3"},
        ) is True

    def test_experience_order_constant(self):
        assert EXPERIENCE_ORDER["noExperience"] < EXPERIENCE_ORDER["moreThan6"]

    def test_work_format_must_include(self):
        assert matches_vacancy_filter(_resume(), {"work_format": "remote"}) is True
        assert matches_vacancy_filter(_resume(), {"work_format": "office"}) is False

    def test_combined_all_must_pass(self):
        filt = {
            "city": "Москва",
            "age_from": 25,
            "age_to": 40,
            "experience": "between1And3",
            "work_format": "remote",
        }
        assert matches_vacancy_filter(_resume(), filt) is True
        assert matches_vacancy_filter(_resume(area={"name": "Казань"}), filt) is False
