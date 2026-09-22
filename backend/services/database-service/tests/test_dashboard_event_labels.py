from datetime import date

from app.endpoints.v1 import stats as stats_mod


def test_event_type_label_maps_known_other():
    assert stats_mod._event_type_label("other") == "Другое событие"
    assert stats_mod._event_type_label("work_anniversary") == "Годовщина работы"
    assert stats_mod._event_type_label("interview") == "Собеседование"
    assert stats_mod._event_type_label("permanent") == "Постоянное событие"


def test_event_type_label_handles_unknown():
    assert stats_mod._event_type_label("custom_event") == "Custom event"


def test_format_event_date_ru():
    assert stats_mod._format_event_date_ru(date(2026, 8, 21)) == "21.08.2026"
