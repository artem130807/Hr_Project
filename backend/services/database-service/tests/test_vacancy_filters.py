"""
TDD: VacancyFilter domain
- one filter → many vacancies
- one vacancy → at most one filter
- fields: city, age range, experience, work_format
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.db.v1.enums import VacancyFilterAction, WorkExpirience, WorkFormat
from app.schemas.v1.vacancy_filters import (
    VacancyFilterCreate,
    VacancyFilterUpdate,
    VacancyFilterRead,
)


# ---------------------------------------------------------------------------
# Enums & schemas
# ---------------------------------------------------------------------------


class TestWorkFormatEnum:
    def test_contains_expected_formats(self):
        values = {m.value for m in WorkFormat}
        assert "remote" in values
        assert "office" in values
        assert "field" in values
        assert "hybrid" in values

    def test_is_str_enum(self):
        assert isinstance(WorkFormat.remote, str)
        assert WorkFormat.remote == "remote"


class TestVacancyFilterSchemas:
    def test_create_schema_accepts_all_fields(self):
        data = VacancyFilterCreate(
            city="Москва",
            age_from=25,
            age_to=45,
            experience=WorkExpirience.one_to_three,
            work_format=WorkFormat.remote,
        )
        assert data.city == "Москва"
        assert data.age_from == 25
        assert data.age_to == 45
        assert data.experience == WorkExpirience.one_to_three
        assert data.work_format == WorkFormat.remote

    def test_create_schema_allows_partial(self):
        data = VacancyFilterCreate(city="Казань")
        assert data.city == "Казань"
        assert data.age_from is None
        assert data.work_format is None
        assert data.action.value == "discard"

    def test_create_schema_rejects_empty_criteria(self):
        with pytest.raises(ValueError):
            VacancyFilterCreate()

    def test_create_schema_accepts_consider_action(self):
        data = VacancyFilterCreate(city="Москва", action=VacancyFilterAction.consider)
        assert data.action == VacancyFilterAction.consider

    def test_create_rejects_inverted_age_range(self):
        with pytest.raises(ValueError):
            VacancyFilterCreate(age_from=40, age_to=20)

    def test_read_schema_from_orm_like(self):
        payload = {
            "id": 1,
            "city": "СПб",
            "age_from": 20,
            "age_to": 35,
            "experience": WorkExpirience.no_experience,
            "work_format": WorkFormat.office,
            "created_at": datetime(2026, 1, 1),
            "updated_at": datetime(2026, 1, 1),
        }
        read = VacancyFilterRead.model_validate(payload)
        assert read.id == 1
        assert read.work_format == WorkFormat.office

    def test_update_schema_partial(self):
        data = VacancyFilterUpdate(work_format=WorkFormat.hybrid)
        dumped = data.model_dump(exclude_unset=True)
        assert dumped == {"work_format": WorkFormat.hybrid}


# ---------------------------------------------------------------------------
# Model shape
# ---------------------------------------------------------------------------


class TestVacancyFilterModel:
    def test_tablename_and_columns(self):
        from app.db.v1.models import VacancyFilter, Vacancy

        assert VacancyFilter.__tablename__ == "vacancy_filters"
        cols = set(VacancyFilter.__table__.columns.keys())
        for required in (
            "id",
            "city",
            "age_from",
            "age_to",
            "experience",
            "work_format",
            "action",
            "created_at",
            "updated_at",
        ):
            assert required in cols

        assert "filter_id" in Vacancy.__table__.columns.keys()
        fk = Vacancy.__table__.c.filter_id.foreign_keys
        assert any("vacancy_filters" in str(f.target_fullname) for f in fk)


# ---------------------------------------------------------------------------
# Repository (mocked session)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestVacancyFilterRepository:
    async def test_create_adds_and_refreshes(self):
        from app.repositories.vacancy_filter_repository import VacancyFilterRepository
        from app.db.v1.models import VacancyFilter

        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        repo = VacancyFilterRepository(db)

        entity = await repo.create(
            city="Москва",
            age_from=25,
            age_to=40,
            experience=WorkExpirience.one_to_three,
            work_format=WorkFormat.remote,
        )

        db.add.assert_called_once()
        added = db.add.call_args[0][0]
        assert isinstance(added, VacancyFilter)
        assert added.city == "Москва"
        assert added.work_format == WorkFormat.remote
        db.commit.assert_awaited()
        db.refresh.assert_awaited()
        assert entity is added

    async def test_get_by_id_returns_entity(self):
        from app.repositories.vacancy_filter_repository import VacancyFilterRepository

        row = SimpleNamespace(id=7, city="Казань")
        db = AsyncMock()
        db.get = AsyncMock(return_value=row)
        repo = VacancyFilterRepository(db)

        found = await repo.get_by_id(7)
        assert found is row
        db.get.assert_awaited()

    async def test_list_all_returns_scalars(self):
        from app.repositories.vacancy_filter_repository import VacancyFilterRepository

        rows = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        repo = VacancyFilterRepository(db)

        listed = await repo.list_all()
        assert listed == rows

    async def test_delete_returns_false_when_missing(self):
        from app.repositories.vacancy_filter_repository import VacancyFilterRepository

        db = AsyncMock()
        db.get = AsyncMock(return_value=None)
        repo = VacancyFilterRepository(db)
        assert await repo.delete(99) is False

    async def test_count_vacancies_using_filter(self):
        from app.repositories.vacancy_filter_repository import VacancyFilterRepository

        result = MagicMock()
        result.scalar_one.return_value = 3
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        repo = VacancyFilterRepository(db)

        assert await repo.count_vacancies_using(5) == 3


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestVacancyFilterService:
    async def test_create_delegates_to_repo(self):
        from app.services.vacancy_filter_service import VacancyFilterService

        repo = AsyncMock()
        created = SimpleNamespace(id=1, city="Москва")
        repo.create = AsyncMock(return_value=created)
        service = VacancyFilterService(repo)

        data = VacancyFilterCreate(city="Москва", work_format=WorkFormat.office)
        result = await service.create(data)

        assert result is created
        repo.create.assert_awaited_once()
        kwargs = repo.create.await_args.kwargs
        assert kwargs["city"] == "Москва"
        assert kwargs["work_format"] == WorkFormat.office

    async def test_get_raises_404_when_missing(self):
        from app.services.vacancy_filter_service import VacancyFilterService

        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=None)
        service = VacancyFilterService(repo)

        with pytest.raises(HTTPException) as exc:
            await service.get(123)
        assert exc.value.status_code == 404

    async def test_update_raises_404_when_missing(self):
        from app.services.vacancy_filter_service import VacancyFilterService

        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=None)
        service = VacancyFilterService(repo)

        with pytest.raises(HTTPException) as exc:
            await service.update(1, VacancyFilterUpdate(city="X"))
        assert exc.value.status_code == 404

    async def test_update_applies_partial_fields(self):
        from app.services.vacancy_filter_service import VacancyFilterService

        entity = SimpleNamespace(
            id=1,
            city="Old",
            age_from=20,
            age_to=30,
            experience=None,
            work_format=WorkFormat.office,
        )
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=entity)
        repo.save = AsyncMock(return_value=entity)
        service = VacancyFilterService(repo)

        result = await service.update(
            1, VacancyFilterUpdate(city="New", work_format=WorkFormat.remote)
        )
        assert result.city == "New"
        assert result.work_format == WorkFormat.remote
        assert result.age_from == 20
        repo.save.assert_awaited_once_with(entity)

    async def test_delete_detaches_vacancies_then_removes(self):
        from app.services.vacancy_filter_service import VacancyFilterService

        entity = SimpleNamespace(id=9)
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=entity)
        repo.detach_vacancies = AsyncMock()
        repo.delete = AsyncMock(return_value=True)
        service = VacancyFilterService(repo)

        await service.delete(9)
        repo.detach_vacancies.assert_awaited_once_with(9)
        repo.delete.assert_awaited_once_with(9)

    async def test_assign_to_vacancy(self):
        from app.services.vacancy_filter_service import VacancyFilterService

        filt = SimpleNamespace(id=2)
        vacancy = SimpleNamespace(id=10, filter_id=None)
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=filt)
        repo.get_vacancy = AsyncMock(return_value=vacancy)
        repo.set_vacancy_filter = AsyncMock(return_value=vacancy)
        service = VacancyFilterService(repo)

        result = await service.assign_to_vacancy(vacancy_id=10, filter_id=2)
        assert result is vacancy
        repo.set_vacancy_filter.assert_awaited_once_with(vacancy, 2)

    async def test_assign_raises_if_filter_missing(self):
        from app.services.vacancy_filter_service import VacancyFilterService

        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=None)
        service = VacancyFilterService(repo)

        with pytest.raises(HTTPException) as exc:
            await service.assign_to_vacancy(1, 99)
        assert exc.value.status_code == 404

    async def test_assign_raises_if_vacancy_missing(self):
        from app.services.vacancy_filter_service import VacancyFilterService

        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=SimpleNamespace(id=1))
        repo.get_vacancy = AsyncMock(return_value=None)
        service = VacancyFilterService(repo)

        with pytest.raises(HTTPException) as exc:
            await service.assign_to_vacancy(404, 1)
        assert exc.value.status_code == 404

    async def test_unassign_from_vacancy(self):
        from app.services.vacancy_filter_service import VacancyFilterService

        vacancy = SimpleNamespace(id=10, filter_id=2)
        repo = AsyncMock()
        repo.get_vacancy = AsyncMock(return_value=vacancy)
        repo.set_vacancy_filter = AsyncMock(return_value=vacancy)
        service = VacancyFilterService(repo)

        await service.unassign_from_vacancy(10)
        repo.set_vacancy_filter.assert_awaited_once_with(vacancy, None)


# ---------------------------------------------------------------------------
# Endpoints wire to service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestVacancyFilterEndpoints:
    async def test_create_endpoint_calls_service(self):
        from app.endpoints.v1.vacancy_filters import create_vacancy_filter

        service = AsyncMock()
        entity = SimpleNamespace(
            id=1,
            city="Москва",
            age_from=None,
            age_to=None,
            experience=None,
            work_format=WorkFormat.remote,
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
        )
        service.create = AsyncMock(return_value=entity)
        body = VacancyFilterCreate(city="Москва", work_format=WorkFormat.remote)

        result = await create_vacancy_filter(body, service=service)
        service.create.assert_awaited_once_with(body)
        assert result.id == 1

    async def test_list_endpoint_calls_service(self):
        from app.endpoints.v1.vacancy_filters import list_vacancy_filters

        service = AsyncMock()
        service.list = AsyncMock(return_value=[])
        result = await list_vacancy_filters(service=service)
        assert result == []
        service.list.assert_awaited_once()

    async def test_get_endpoint_calls_service(self):
        from app.endpoints.v1.vacancy_filters import get_vacancy_filter

        service = AsyncMock()
        entity = SimpleNamespace(
            id=5,
            city=None,
            age_from=None,
            age_to=None,
            experience=None,
            work_format=None,
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
        )
        service.get = AsyncMock(return_value=entity)
        result = await get_vacancy_filter(5, service=service)
        assert result.id == 5
        service.get.assert_awaited_once_with(5)

    async def test_update_endpoint_calls_service(self):
        from app.endpoints.v1.vacancy_filters import update_vacancy_filter

        service = AsyncMock()
        entity = SimpleNamespace(
            id=5,
            city="Казань",
            age_from=None,
            age_to=None,
            experience=None,
            work_format=None,
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 2),
        )
        service.update = AsyncMock(return_value=entity)
        body = VacancyFilterUpdate(city="Казань")
        result = await update_vacancy_filter(5, body, service=service)
        service.update.assert_awaited_once_with(5, body)
        assert result.city == "Казань"

    async def test_delete_endpoint_calls_service(self):
        from app.endpoints.v1.vacancy_filters import delete_vacancy_filter

        service = AsyncMock()
        service.delete = AsyncMock(return_value=None)
        result = await delete_vacancy_filter(3, service=service)
        service.delete.assert_awaited_once_with(3)
        assert result is None

    async def test_assign_endpoint_calls_service(self):
        from app.endpoints.v1.vacancy_filters import assign_filter_to_vacancy

        service = AsyncMock()
        vacancy = SimpleNamespace(
            id=10,
            filter_id=2,
            name="Логист",
            public_code=None,
            description=None,
            department=None,
            area_id=None,
            salary_from=None,
            salary_to=None,
            currency=None,
            work_format=None,
            employment_type=None,
            total_work_expirience=None,
            key_skills=None,
            manager_id=None,
            status=None,
            hh_vacancy_id=None,
            hh_vacancy_url=None,
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
            professional_roles=None,
            synonyms=None,
            schedule_id=None,
            employment_id=None,
            hiring_request_id=None,
        )
        # assign returns vacancy ORM-like; endpoint uses response_model ReadVacancy
        service.assign_to_vacancy = AsyncMock(return_value=vacancy)
        result = await assign_filter_to_vacancy(10, 2, service=service)
        service.assign_to_vacancy.assert_awaited_once_with(10, 2)
        assert result.filter_id == 2

    async def test_unassign_endpoint_calls_service(self):
        from app.endpoints.v1.vacancy_filters import unassign_filter_from_vacancy

        service = AsyncMock()
        vacancy = SimpleNamespace(id=10, filter_id=None)
        service.unassign_from_vacancy = AsyncMock(return_value=vacancy)
        result = await unassign_filter_from_vacancy(10, service=service)
        service.unassign_from_vacancy.assert_awaited_once_with(10)
        assert result.filter_id is None

    async def test_routes_registered(self):
        from app.endpoints.v1.vacancy_filters import router

        paths = {route.path for route in router.routes}
        assert "/vacancy-filters" in paths
        assert "/vacancy-filters/{filter_id}" in paths
        assert "/vacancy/{vacancy_id}/filter/{filter_id}" in paths
        assert "/vacancy/{vacancy_id}/filter" in paths
