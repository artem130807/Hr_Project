from datetime import date, datetime, time, timezone

import pytest
from pydantic import ValidationError

from app.events.recurrence import (
    add_interval,
    advance_to_future,
    first_notify_at,
    next_dispatch_after_initial,
)
from app.schemas.v1.events import EventCreate


def test_first_notify_at_matches_message_service_midnight_utc():
    got = first_notify_at(date(2026, 5, 1), remind_before=3, remind_at_time=None)
    assert got == datetime(2026, 4, 28, tzinfo=timezone.utc)


def test_first_notify_at_samara_clock():
    got = first_notify_at(date(2026, 8, 19), remind_before=0, remind_at_time=time(15, 0))
    assert got == datetime(2026, 8, 19, 11, 0, tzinfo=timezone.utc)


def test_add_interval_month():
    start = datetime(2026, 1, 31, 10, 0, tzinfo=timezone.utc)
    nxt = add_interval(start, 1, "month")
    assert nxt.month == 2
    assert nxt.day in (28, 29)


def test_advance_skips_missed_slots():
    due = datetime(2026, 1, 1, tzinfo=timezone.utc)
    now = datetime(2026, 4, 1, tzinfo=timezone.utc)
    nxt = advance_to_future(due, 1, "month", now)
    assert nxt > now


def test_permanent_schema_requires_interval():
    with pytest.raises(ValidationError):
        EventCreate(type="permanent", event_date=date(2026, 8, 24), note="x")


def test_permanent_schema_normalizes_interval():
    ev = EventCreate(
        type="permanent",
        event_date=date(2026, 8, 24),
        repeat_interval_unit="MONTH",
        note="x",
    )
    assert ev.repeat_interval_count == 1
    assert ev.repeat_interval_unit == "month"


def test_non_permanent_clears_interval():
    ev = EventCreate(
        type="other",
        event_date=date(2026, 8, 24),
        repeat_interval_unit="month",
        repeat_interval_count=2,
        note="x",
    )
    assert ev.repeat_interval_unit is None
    assert ev.repeat_interval_count is None


def test_next_dispatch_after_initial_is_one_month_after_first_notify():
    row = EventCreate(
        type="permanent",
        event_date=date(2026, 8, 24),
        remind_before=0,
        repeat_interval_count=1,
        repeat_interval_unit="month",
        note="x",
    )
    nxt = next_dispatch_after_initial(row)
    assert nxt == datetime(2026, 9, 24, tzinfo=timezone.utc)
