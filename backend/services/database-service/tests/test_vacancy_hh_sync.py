"""Tests for vacancy PATCH/DELETE HH auto-sync hooks and proxy auth classification."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


def test_is_proxy_auth_failure_ignores_hh_duplicate_403():
    from app.endpoints.v1.vacancies import _is_proxy_auth_failure

    detail = (
        'HH API Error {"errors":[{"value":"duplicate","found":1,'
        '"items":[{"id":136168977}],"type":"vacancies"}]}'
    )
    assert _is_proxy_auth_failure(403, detail) is False
    assert _is_proxy_auth_failure(401, "Could not validate credentials") is True
    assert _is_proxy_auth_failure(403, "Invalid internal proxy token") is True


@pytest.mark.asyncio
async def test_update_vacancy_syncs_to_hh_when_published():
    from app.endpoints.v1 import vacancies as mod
    from app.schemas.v1.vacancies import ReadVacancy

    vacancy = MagicMock()
    vacancy.id = 1
    vacancy.hh_vacancy_id = "12345"
    vacancy.hh_vacancy_url = "https://hh.ru/vacancy/12345"
    vacancy.name = "New title"
    vacancy.created_at = MagicMock()
    vacancy.updated_at = MagicMock()
    vacancy.planned_close_date = None
    # Enough fields for ReadVacancy.model_validate via from_attributes
    for attr in (
        "billing_type_id", "vacancy_type_id", "synonyms", "description", "department",
        "area_id", "schedule_id", "employment_id", "professional_roles_id", "age",
        "gender", "languages", "personal_characteristics", "relevant_position_expirience",
        "certain_position_expirience", "total_work_expirience", "other_work_expirience",
        "average_service_length", "education", "required_hard_skills", "optional_hard_skills",
        "main_tasks", "secondary_tasks", "work_programs", "kpi_metrics", "resume_update_date",
        "active_search", "salary_from", "salary_to", "currency_id", "gross", "is_template",
        "hiring_request_id",
    ):
        if not hasattr(vacancy, attr) or getattr(vacancy, attr) is vacancy:
            pass

    db = AsyncMock()
    db.get = AsyncMock(return_value=vacancy)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    data = MagicMock()
    data.model_dump.return_value = {"name": "New title"}

    fake_result = MagicMock(spec=ReadVacancy)
    fake_result.hh_synced = None
    fake_result.hh_sync_error = None

    with patch.object(mod.conf, "HH_SERVICE_URL", "http://hh-service:8003"), patch.object(
        mod, "_proxy_vacancy_to_hh", new_callable=AsyncMock
    ) as proxy, patch.object(mod.ReadVacancy, "model_validate", return_value=fake_result):
        proxy.return_value = {"status": "ok"}
        result = await mod.update_vacancy_endpoint(1, data, db)

    assert proxy.await_args.args[0] == "PUT"
    assert proxy.await_args.args[1] == 1
    assert result.hh_synced is True
    assert result.hh_sync_error is None


@pytest.mark.asyncio
async def test_update_vacancy_soft_fails_hh_sync():
    from app.endpoints.v1 import vacancies as mod
    from app.schemas.v1.vacancies import ReadVacancy
    from fastapi import HTTPException

    vacancy = MagicMock()
    vacancy.id = 1
    vacancy.hh_vacancy_id = "12345"
    vacancy.hh_vacancy_url = "https://hh.ru/vacancy/12345"

    db = AsyncMock()
    db.get = AsyncMock(return_value=vacancy)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    data = MagicMock()
    data.model_dump.return_value = {"name": "New title"}

    fake_result = MagicMock(spec=ReadVacancy)
    fake_result.hh_synced = None
    fake_result.hh_sync_error = None

    with patch.object(mod.conf, "HH_SERVICE_URL", "http://hh-service:8003"), patch.object(
        mod, "_proxy_vacancy_to_hh", new_callable=AsyncMock
    ) as proxy, patch.object(mod.ReadVacancy, "model_validate", return_value=fake_result):
        proxy.side_effect = HTTPException(status_code=502, detail="HH down")
        result = await mod.update_vacancy_endpoint(1, data, db)

    db.commit.assert_awaited()
    assert result.hh_synced is False
    assert "HH down" in str(result.hh_sync_error)


@pytest.mark.asyncio
async def test_update_vacancy_backfills_hh_id_from_url():
    from app.endpoints.v1 import vacancies as mod
    from app.schemas.v1.vacancies import ReadVacancy

    vacancy = MagicMock()
    vacancy.id = 1
    vacancy.hh_vacancy_id = None
    vacancy.hh_vacancy_url = "https://hh.ru/vacancy/99988"

    db = AsyncMock()
    db.get = AsyncMock(return_value=vacancy)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    data = MagicMock()
    data.model_dump.return_value = {"name": "T"}

    fake_result = MagicMock(spec=ReadVacancy)
    fake_result.hh_synced = None
    fake_result.hh_sync_error = None

    with patch.object(mod.conf, "HH_SERVICE_URL", "http://hh-service:8003"), patch.object(
        mod, "_proxy_vacancy_to_hh", new_callable=AsyncMock
    ) as proxy, patch.object(mod.ReadVacancy, "model_validate", return_value=fake_result):
        proxy.return_value = {"status": "ok"}
        await mod.update_vacancy_endpoint(1, data, db)

    assert vacancy.hh_vacancy_id == "99988"
    proxy.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_vacancy_reports_missing_hh_service_config():
    from app.endpoints.v1 import vacancies as mod
    from app.schemas.v1.vacancies import ReadVacancy

    vacancy = MagicMock()
    vacancy.id = 1
    vacancy.hh_vacancy_id = "12345"
    vacancy.hh_vacancy_url = "https://hh.ru/vacancy/12345"

    db = AsyncMock()
    db.get = AsyncMock(return_value=vacancy)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    data = MagicMock()
    data.model_dump.return_value = {"name": "New title"}

    fake_result = MagicMock(spec=ReadVacancy)
    fake_result.hh_synced = None
    fake_result.hh_sync_error = None

    with patch.object(mod.conf, "HH_SERVICE_URL", None), patch.object(
        mod, "_proxy_vacancy_to_hh", new_callable=AsyncMock
    ) as proxy, patch.object(mod.ReadVacancy, "model_validate", return_value=fake_result):
        result = await mod.update_vacancy_endpoint(1, data, db)

    proxy.assert_not_awaited()
    assert result.hh_synced is False
    assert "HH_SERVICE_INTERNAL" in str(result.hh_sync_error)


@pytest.mark.asyncio
async def test_update_vacancy_skips_hh_when_only_link_fields():
    from app.endpoints.v1 import vacancies as mod
    from app.schemas.v1.vacancies import ReadVacancy

    vacancy = MagicMock()
    vacancy.hh_vacancy_id = "12345"
    vacancy.hh_vacancy_url = "https://hh.ru/vacancy/12345"

    db = AsyncMock()
    db.get = AsyncMock(return_value=vacancy)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    data = MagicMock()
    data.model_dump.return_value = {"hh_vacancy_url": "https://hh.ru/vacancy/12345"}

    fake_result = MagicMock(spec=ReadVacancy)
    fake_result.hh_synced = None
    fake_result.hh_sync_error = None

    with patch.object(mod.conf, "HH_SERVICE_URL", "http://hh-service:8003"), patch.object(
        mod, "_proxy_vacancy_to_hh", new_callable=AsyncMock
    ) as proxy, patch.object(mod.ReadVacancy, "model_validate", return_value=fake_result):
        await mod.update_vacancy_endpoint(1, data, db)

    proxy.assert_not_awaited()


def _empty_select_result():
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    return result


@pytest.mark.asyncio
async def test_delete_vacancy_does_not_change_hh_publication():
    from app.endpoints.v1 import vacancies as mod

    vacancy = MagicMock()
    vacancy.hh_vacancy_id = "99"
    vacancy.hh_vacancy_url = "https://hh.ru/vacancy/99"

    db = AsyncMock()
    db.get = AsyncMock(return_value=vacancy)
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    # auto_search (empty) + vacancy_test_relations (empty)
    db.execute = AsyncMock(side_effect=[_empty_select_result(), _empty_select_result()])

    with patch.object(mod.conf, "HH_SERVICE_URL", "http://hh-service:8003"), patch.object(
        mod, "_proxy_vacancy_to_hh", new_callable=AsyncMock
    ) as proxy:
        await mod.delete_vacancy_endpoint(7, db)

    proxy.assert_not_awaited()
    db.delete.assert_awaited_once_with(vacancy)
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_delete_vacancy_clears_autosearch_fk():
    from app.endpoints.v1 import vacancies as mod

    vacancy = MagicMock()
    vacancy.hh_vacancy_id = None
    vacancy.hh_vacancy_url = None

    auto = MagicMock()
    auto.id = 11

    db = AsyncMock()
    db.get = AsyncMock(return_value=vacancy)
    db.delete = AsyncMock()
    db.commit = AsyncMock()

    auto_result = MagicMock()
    auto_result.scalars.return_value.all.return_value = [auto]
    reviewed_result = MagicMock()
    reviewed_result.scalars.return_value.all.return_value = []
    tests_result = MagicMock()
    tests_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[auto_result, reviewed_result, tests_result])

    with patch.object(mod.conf, "HH_SERVICE_URL", "http://hh-service:8003"), patch.object(
        mod, "_proxy_vacancy_to_hh", new_callable=AsyncMock
    ) as proxy:
        await mod.delete_vacancy_endpoint(2, db)

    proxy.assert_not_awaited()
    # auto_search row deleted before vacancy
    assert db.delete.await_count >= 2
    db.commit.assert_awaited()
