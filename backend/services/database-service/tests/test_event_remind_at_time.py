"""Unit tests for EventCreate remind_at_time parsing."""
from datetime import time

import pytest
from pydantic import ValidationError

from app.schemas.v1.events import EventCreate, _parse_optional_time


def test_parse_optional_time_empty():
    assert _parse_optional_time(None) is None
    assert _parse_optional_time("") is None
    assert _parse_optional_time("  ") is None


def test_parse_optional_time_hhmm():
    assert _parse_optional_time("09:15") == time(9, 15)
    assert _parse_optional_time("15:00:00") == time(15, 0, 0)


def test_event_create_accepts_remind_at_time_string():
    from datetime import date

    ev = EventCreate(
        type="birthday",
        event_date=date(2026, 8, 19),
        remind_before=0,
        remind_at_time="10:30",
    )
    assert ev.remind_at_time == time(10, 30)


def test_event_create_optional_remind_at_time():
    from datetime import date

    ev = EventCreate(type="other", event_date=date(2026, 1, 1), note="x")
    assert ev.remind_at_time is None


def test_parse_optional_time_rejects_garbage():
    with pytest.raises(ValueError):
        _parse_optional_time("noon")
    with pytest.raises(ValueError):
        _parse_optional_time("10")
    with pytest.raises(ValueError):
        _parse_optional_time(123)


def test_event_create_rejects_bad_time():
    from datetime import date

    with pytest.raises(ValidationError):
        EventCreate(
            type="birthday",
            event_date=date(2026, 8, 19),
            remind_at_time="25:99",
        )
