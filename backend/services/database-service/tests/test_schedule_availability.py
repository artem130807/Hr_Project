"""Tests for HR availability calendar API."""
from datetime import date, time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import MissingGreenlet

from app.endpoints.v1 import schedule as mod
from app.schemas.v1.schedule import AvailabilityCreate, slot_to_read


def test_slot_to_read_includes_candidate_name():
    slot = SimpleNamespace(
        id=1,
        date=date(2026, 8, 17),
        start_time=time(10, 0),
        end_time=time(11, 0),
        is_booked=True,
        candidate_id=5,
        candidate=SimpleNamespace(full_name="Иванов Иван"),
    )
    dto = slot_to_read(slot)
    assert dto.candidate_name == "Иванов Иван"
    assert dto.candidate_id == 5


def test_slot_to_read_survives_lazy_load_crash():
    class Slot:
        id = 7
        date = date(2026, 8, 17)
        start_time = time(10, 0)
        end_time = time(11, 0)
        is_booked = False
        candidate_id = None

        @property
        def candidate(self):
            raise MissingGreenlet("lazy load blocked in async")

    dto = slot_to_read(Slot())
    assert dto.id == 7
    assert dto.candidate_name is None


@pytest.mark.asyncio
async def test_create_rejects_empty_hr_id():
    body = AvailabilityCreate(
        hr_id="x",
        date=date(2026, 8, 17),
        start_time=time(10, 0),
        end_time=time(12, 0),
    )
    body.hr_id = "   "
    db = MagicMock()
    with pytest.raises(HTTPException) as exc:
        await mod.create_availability_slots_endpoint(body, db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_rejects_too_short_interval():
    body = AvailabilityCreate(
        hr_id="erp-uuid-1",
        date=date(2026, 8, 17),
        start_time=time(10, 0),
        end_time=time(10, 30),
        slot_length_minutes=60,
    )
    db = MagicMock()
    db.commit = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await mod.create_availability_slots_endpoint(body, db)
    assert exc.value.status_code == 400
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_returns_plain_dto_list():
    body = AvailabilityCreate(
        hr_id="erp-uuid-1",
        date=date(2026, 8, 17),
        start_time=time(10, 0),
        end_time=time(12, 0),
        slot_length_minutes=60,
    )
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    created = []

    def add_side_effect(slot):
        slot.id = 100 + len(created)
        created.append(slot)

    db.add.side_effect = add_side_effect

    out = await mod.create_availability_slots_endpoint(body, db)
    assert len(out) == 2
    assert out[0].candidate_name is None
    assert out[0].is_booked is False
    assert out[0].id == 100
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_get_hr_availability_returns_dto_list():
    slot = SimpleNamespace(
        id=3,
        date=date(2026, 8, 17),
        start_time=time(10, 0),
        end_time=time(11, 0),
        is_booked=False,
        candidate_id=None,
        candidate=None,
    )
    db = MagicMock()
    result = MagicMock()
    result.all.return_value = [slot]
    db.scalars = AsyncMock(return_value=result)

    out = await mod.get_hr_availability_endpoint(
        "erp-uuid-1",
        date(2026, 8, 17),
        date(2026, 8, 23),
        db,
    )
    assert len(out) == 1
    assert out[0].id == 3
    assert out[0].candidate_name is None
