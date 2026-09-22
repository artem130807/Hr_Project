"""Tests for HH employer vacancies / negotiations normalization helpers."""
import pytest
from app.utils.hh_import import normalize_vacancy_item, normalize_negotiation_item


def test_normalize_vacancy_item():
    raw = {
        "id": 136168977,
        "name": "Логист",
        "alternate_url": "https://hh.ru/vacancy/136168977",
        "published_at": "2026-08-01T10:00:00+0300",
        "archived": False,
        "closed_for_applicants": True,
        "area": {"id": "1", "name": "Москва"},
        "salary": {"from": 100000, "to": 150000, "currency": "RUR"},
        "counters": {"responses": 12},
        "manager": {"id": 42, "first_name": "Анна", "last_name": "Иванова"},
        "type": {"id": "open", "name": "Открытая"},
    }
    item = normalize_vacancy_item(raw)
    assert item["hh_vacancy_id"] == "136168977"
    assert item["name"] == "Логист"
    assert item["area"] == "Москва"
    assert item["salary_from"] == 100000
    assert item["responses_count"] == 12
    assert item["closed_for_applicants"] is True
    assert item["manager_id"] == "42"
    assert item["manager_name"] == "Иванова Анна"
    assert "raw" not in item


@pytest.mark.asyncio
async def test_list_employer_vacancies_passes_all_accessible():
    from unittest.mock import AsyncMock, MagicMock
    from app.utils.hh_import import list_employer_vacancies_normalized

    hh = MagicMock()
    hh.list_employer_vacancies = AsyncMock(
        return_value={
            "items": [{"id": 1, "name": "A", "archived": False}],
            "found": 1,
            "pages": 1,
            "page": 0,
            "per_page": 50,
        }
    )
    data = await list_employer_vacancies_normalized(hh, archived=False, page=0, per_page=50)
    hh.list_employer_vacancies.assert_awaited_once()
    kwargs = hh.list_employer_vacancies.await_args.kwargs
    assert kwargs["all_accessible"] is True
    assert data["found"] == 1
    assert data["all_accessible"] is True


@pytest.mark.asyncio
async def test_list_employer_vacancies_client_sends_all_accessible_param(monkeypatch):
    from unittest.mock import AsyncMock
    from app.clients.hh import simple_hh_client as client_mod
    from app.clients.hh.simple_hh_client import SimpleHHClient

    monkeypatch.setattr(client_mod.config, "MOCK_HH", False)

    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh.employer_id = "6099903"
    hh._request = AsyncMock(return_value={"items": [], "found": 0, "pages": 0, "page": 0, "per_page": 50})

    await SimpleHHClient.list_employer_vacancies(
        hh, archived=False, page=0, per_page=50, employer_id="6099903"
    )

    assert hh._request.await_args.args[0] == "GET"
    assert hh._request.await_args.args[1] == "/employers/6099903/vacancies/active"
    assert hh._request.await_args.kwargs["params"]["all_accessible"] == "true"
    assert hh._request.await_args.kwargs["params"]["per_page"] == 50


def test_normalize_negotiation_item():
    raw = {
        "id": "abc",
        "chat_id": "42",
        "created_at": "2026-08-10T12:00:00+0300",
        "state": {"id": "response", "name": "Отклик"},
        "employer_state": {"id": "response", "name": "Неразобранные"},
        "resume": {
            "id": "res1",
            "title": "Водитель",
            "first_name": "Иван",
            "last_name": "Иванов",
            "age": 30,
            "alternate_url": "https://hh.ru/resume/1",
            "area": {"name": "Казань"},
            "total_experience": {"months": 40},
            "work_format": [{"id": "REMOTE", "name": "Удалённо"}],
        },
    }
    item = normalize_negotiation_item(raw)
    assert item["id"] == "abc"
    assert item["resume"]["full_name"] == "Иванов Иван"
    assert item["state"] == "response"
    assert item["resume"]["title"] == "Водитель"
    assert item["resume"]["area"] == "Казань"
    assert item["resume"]["experience_months"] == 40
    assert item["resume"]["work_formats"][0]["id"] == "REMOTE"


def test_normalize_negotiation_detail_includes_full_resume_card():
    from app.utils.hh_import import normalize_negotiation_detail

    raw = {
        "id": "abc",
        "state": {"id": "response", "name": "Отклик"},
        "resume": {
            "id": "r1",
            "title": "Логист",
            "first_name": "Иван",
            "last_name": "Иванов",
            "age": 30,
            "birth_date": "1996-05-01",
            "alternate_url": "https://hh.ru/resume/r1",
            "area": {"name": "Москва"},
            "total_experience": {"months": 24},
            "skill_set": ["Excel"],
            "salary": {"amount": 100000, "currency": "RUR"},
            "gender": {"id": "male", "name": "Мужской"},
            "photo": {"medium": "https://hhcdn.ru/photo.jpg"},
            "contact": [
                {"type": {"id": "cell"}, "value": {"formatted": "+7 999 111-22-33"}},
                {"type": {"id": "email"}, "value": "ivan@example.com"},
            ],
            "experience": [
                {
                    "position": "Логист",
                    "company": "ООО Ромашка",
                    "start": "2022-01-01",
                    "end": None,
                    "description": "Маршруты",
                    "area": {"name": "Москва"},
                    "industries": [{"name": "Логистика"}],
                }
            ],
            "education": {"primary": [{"name": "МГУ", "organization": "МГУ"}]},
            "language": [{"name": "Русский", "level": {"name": "Родной"}}],
            "skills": "Организую поставки.",
            "job_search_status": {"id": "active_search", "name": "Активно ищу работу"},
        },
        "actions": [],
    }
    detail = normalize_negotiation_detail(raw)
    resume = detail["resume"]
    assert resume["phone_number"]
    assert resume["email"] == "ivan@example.com"
    assert resume["photo_url"] == "https://hhcdn.ru/photo.jpg"
    assert resume["experience"][0]["title"] == "Логист"
    assert resume["experience"][0]["company"] == "ООО Ромашка"
    assert "МГУ" in resume["education"]
    assert resume["languages"][0].startswith("Русский")
    assert resume["about"] == "Организую поставки."
    assert resume["active_search"] is True
    assert resume["birth_date"] == "1996-05-01"


@pytest.mark.asyncio
async def test_sync_candidate_hh_action_endpoint_considers():
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.endpoints.v1.hh_import import sync_candidate_hh_action, CandidateHhActionBody

    hh = MagicMock()
    hh.consider_negotiation = AsyncMock(return_value={"status": "considered"})
    db = MagicMock()
    db.get = AsyncMock(
        side_effect=[
            {"id": 4, "hh_resume_link": "https://hh.ru/resume/abc"},
            {"id": 9, "hh_vacancy_id": "55"},
        ]
    )
    with patch(
        "app.utils.hh_candidate_sync.find_negotiation_id_for_resume",
        new=AsyncMock(return_value="neg-1"),
    ):
        out = await sync_candidate_hh_action(
            4, "consider", CandidateHhActionBody(), hh, db
        )
    assert out["status"] == "ok"
    assert out["negotiation_id"] == "neg-1"
    hh.consider_negotiation.assert_awaited_once_with("neg-1")


@pytest.mark.asyncio
async def test_sync_candidate_hh_action_endpoint_sends_message():
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.endpoints.v1.hh_import import sync_candidate_hh_action, CandidateHhActionBody

    hh = MagicMock()
    hh.send_message_to_negotiation = AsyncMock(return_value={"status": "sent"})
    db = MagicMock()
    db.get = AsyncMock(
        side_effect=[
            {"id": 4, "hh_resume_link": "https://hh.ru/resume/abc"},
            {"id": 9, "hh_vacancy_id": "55"},
        ]
    )
    with patch(
        "app.utils.hh_candidate_sync.find_negotiation_id_for_resume",
        new=AsyncMock(return_value="neg-2"),
    ):
        out = await sync_candidate_hh_action(
            4, "message", CandidateHhActionBody(message="Ссылка на тест"), hh, db
        )
    assert out["status"] == "ok"
    assert out["action_id"] == "message"
    assert out["negotiation_id"] == "neg-2"
    hh.send_message_to_negotiation.assert_awaited_once_with("neg-2", "Ссылка на тест")


@pytest.mark.asyncio
async def test_sync_candidate_hh_action_endpoint_sends_interview():
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.endpoints.v1.hh_import import sync_candidate_hh_action, CandidateHhActionBody

    hh = MagicMock()
    hh.interview_negotiation = AsyncMock(return_value={"status": "interview_invited"})
    db = MagicMock()
    db.get = AsyncMock(
        side_effect=[
            {"id": 4, "hh_resume_link": "https://hh.ru/resume/abc"},
            {"id": 9, "hh_vacancy_id": "55"},
        ]
    )
    with patch(
        "app.utils.hh_candidate_sync.find_negotiation_id_for_resume",
        new=AsyncMock(return_value="neg-3"),
    ):
        out = await sync_candidate_hh_action(
            4, "interview", CandidateHhActionBody(message="Приглашаем вас на собеседование"), hh, db
        )
    assert out["status"] == "ok"
    assert out["action_id"] == "interview"
    hh.interview_negotiation.assert_awaited_once_with(
        "neg-3", message="Приглашаем вас на собеседование"
    )


@pytest.mark.asyncio
async def test_sync_candidate_hh_action_falls_back_to_other_vacancy():
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.endpoints.v1.hh_import import sync_candidate_hh_action, CandidateHhActionBody

    hh = MagicMock()
    hh.send_message_to_negotiation = AsyncMock(return_value={"status": "sent"})
    db = MagicMock()
    db.get = AsyncMock(
        side_effect=[
            {"id": 4, "hh_resume_link": "https://hh.ru/resume/abc"},
            {"id": 9, "hh_vacancy_id": "55"},
            [{"vacancy": {"hh_vacancy_id": "99", "name": "Водитель"}}],
        ]
    )
    with patch(
        "app.utils.hh_candidate_sync.find_negotiation_id_for_resume",
        new=AsyncMock(side_effect=[None, "neg-fallback"]),
    ) as find:
        out = await sync_candidate_hh_action(
            4, "message", CandidateHhActionBody(message="Ссылка на тест"), hh, db
        )
    assert out["status"] == "ok"
    assert out["negotiation_id"] == "neg-fallback"
    assert out["hh_vacancy_id"] == "99"
    assert [call.args[1] for call in find.await_args_list] == ["55", "99"]
    hh.send_message_to_negotiation.assert_awaited_once_with("neg-fallback", "Ссылка на тест")


@pytest.mark.asyncio
async def test_sync_candidate_hh_action_uses_relations_when_no_active_vacancy():
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.endpoints.v1.hh_import import sync_candidate_hh_action, CandidateHhActionBody

    hh = MagicMock()
    hh.send_message_to_negotiation = AsyncMock(return_value={"status": "sent"})
    db = MagicMock()
    db.get = AsyncMock(
        side_effect=[
            {"id": 4, "hh_resume_link": "https://hh.ru/resume/abc"},
            None,
            [{"is_active": False, "vacancy": {"hh_vacancy_id": "77"}}],
        ]
    )
    with patch(
        "app.utils.hh_candidate_sync.find_negotiation_id_for_resume",
        new=AsyncMock(return_value="neg-rel"),
    ):
        out = await sync_candidate_hh_action(
            4, "message", CandidateHhActionBody(message="Тест"), hh, db
        )
    assert out["status"] == "ok"
    assert out["hh_vacancy_id"] == "77"


@pytest.mark.asyncio
async def test_sync_candidate_hh_action_skips_when_linked_vacancy_has_no_hh_id():
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.endpoints.v1.hh_import import sync_candidate_hh_action, CandidateHhActionBody

    hh = MagicMock()
    db = MagicMock()
    db.get = AsyncMock(
        side_effect=[
            {"id": 4, "hh_resume_link": "https://hh.ru/resume/abc"},
            None,
            [{"is_active": True, "vacancy": {"name": "Водитель"}}],
        ]
    )
    with patch(
        "app.utils.hh_candidate_sync.find_negotiation_id_for_resume",
        new=AsyncMock(return_value=None),
    ) as find:
        out = await sync_candidate_hh_action(
            4, "message", CandidateHhActionBody(message="Тест"), hh, db
        )
    assert out["status"] == "skipped"
    assert out["reason"] == "vacancy_not_on_hh"
    find.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_candidate_hh_action_reads_hh_id_from_relation_root():
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.endpoints.v1.hh_import import sync_candidate_hh_action, CandidateHhActionBody

    hh = MagicMock()
    hh.send_message_to_negotiation = AsyncMock(return_value={"status": "sent"})
    db = MagicMock()
    db.get = AsyncMock(
        side_effect=[
            {"id": 4, "hh_resume_link": "https://hh.ru/resume/abc"},
            None,
            [{"hh_vacancy_id": "88", "vacancy": {"name": "Логист"}}],
        ]
    )
    with patch(
        "app.utils.hh_candidate_sync.find_negotiation_id_for_resume",
        new=AsyncMock(return_value="neg-root"),
    ):
        out = await sync_candidate_hh_action(
            4, "message", CandidateHhActionBody(message="Тест"), hh, db
        )
    assert out["status"] == "ok"
    assert out["hh_vacancy_id"] == "88"


def test_hh_import_router_paths():
    from app.endpoints.v1.hh_import import router

    paths = {getattr(r, "path", None) for r in router.routes}
    assert "/hh/employer-vacancies" in paths
    assert "/hh/vacancies/{hh_vacancy_id}/negotiations" in paths
    assert "/hh/vacancies/{hh_vacancy_id}/link" in paths
    assert "/hh/vacancies/{hh_vacancy_id}/import" in paths
    assert "/hh/negotiations/{negotiation_id}" in paths
    assert "/hh/negotiations/{negotiation_id}/actions/{action_id}" in paths
    assert "/hh/candidates/{candidate_id}/actions/{action_id}" in paths


def test_build_local_vacancy_from_hh():
    from app.utils.hh_import import build_local_vacancy_from_hh

    raw = {
        "id": 55,
        "name": "Логист",
        "alternate_url": "https://hh.ru/vacancy/55",
        "description": "<p>" + ("x" * 220) + "</p>",
        "type": {"id": "open"},
        "area": {"id": "1", "name": "Москва"},
        "salary": {"from": 100000, "to": 150000, "currency": "RUR", "gross": True},
        "schedule": {"id": "fullDay"},
        "employment": {"id": "full"},
        "experience": {"id": "between1And3"},
        "professional_roles": [{"id": "67", "name": "Логист"}],
        "key_skills": [{"name": "1С"}, {"name": "Excel"}],
    }
    payload = build_local_vacancy_from_hh(raw, "логистический")
    assert payload["name"] == "Логист"
    assert payload["department"] == "логистический"
    assert payload["hh_vacancy_id"] == "55"
    assert payload["area_id"] == "1"
    assert payload["salary_from"] == 100000
    assert payload["professional_roles_id"] == ["67"]
    assert payload["required_hard_skills"] == ["1С", "Excel"]
    assert payload["total_work_expirience"] == "between1And3"
    assert len(payload["description"]) >= 200


def test_build_local_vacancy_skips_short_description():
    from app.utils.hh_import import build_local_vacancy_from_hh

    payload = build_local_vacancy_from_hh(
        {"id": 1, "name": "A", "description": "<p>short</p>", "type": {"id": "open"}},
        "hr",
    )
    assert "description" not in payload
    assert payload["synonyms"] == ["A"]


@pytest.mark.asyncio
async def test_import_hh_vacancy_creates_local():
    from unittest.mock import AsyncMock, MagicMock
    from app.endpoints.v1 import hh_import as mod

    hh = MagicMock()
    hh.get_vacancy = AsyncMock(
        return_value={
            "id": 77,
            "name": "Водитель",
            "alternate_url": "https://hh.ru/vacancy/77",
            "type": {"id": "open"},
            "area": {"id": "2"},
        }
    )
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    db.post = AsyncMock(
        return_value={
            "id": 12,
            "hh_vacancy_id": "77",
            "hh_vacancy_url": "https://hh.ru/vacancy/77",
            "name": "Водитель",
        }
    )

    result = await mod.import_hh_vacancy_to_local("77", "логистический", hh, db)

    assert result["status"] == "ok"
    assert result["created"] is True
    assert result["local_vacancy_id"] == 12
    db.post.assert_awaited_once()
    body = db.post.await_args.kwargs["json"]
    assert body["hh_vacancy_id"] == "77"
    assert body["department"] == "логистический"


@pytest.mark.asyncio
async def test_import_hh_vacancy_idempotent_when_already_linked():
    from unittest.mock import AsyncMock, MagicMock
    from app.endpoints.v1 import hh_import as mod

    hh = MagicMock()
    db = MagicMock()
    db.get = AsyncMock(
        return_value={"id": 3, "hh_vacancy_id": "77", "hh_vacancy_url": "https://hh.ru/vacancy/77"}
    )

    result = await mod.import_hh_vacancy_to_local("77", "hr", hh, db)

    assert result["status"] == "already_linked"
    assert result["created"] is False
    assert result["local_vacancy_id"] == 3
    db.post.assert_not_called()
    hh.get_vacancy.assert_not_called()


@pytest.mark.asyncio
async def test_get_negotiation_detail_endpoint():
    from unittest.mock import AsyncMock, MagicMock
    from app.endpoints.v1 import hh_import as mod

    hh = MagicMock()
    hh.get_negotiation = AsyncMock(
        return_value={
            "id": "n1",
            "alternate_url": "https://hh.ru/employer/vacancyresponses/n1",
            "state": {"id": "response", "name": "Отклик"},
            "resume": {"id": "r1", "first_name": "Аня", "last_name": "Петрова"},
            "actions": [
                {
                    "id": "discard",
                    "enabled": True,
                    "method": "PUT",
                    "url": "https://api.hh.ru/negotiations/discard/n1",
                    "arguments": [],
                }
            ],
        }
    )
    hh.get_resume = AsyncMock(
        return_value={
            "id": "r1",
            "first_name": "Аня",
            "last_name": "Петрова",
            "title": "Логист",
            "area": {"name": "Казань"},
            "alternate_url": "https://hh.ru/resume/r1",
        }
    )

    detail = await mod.get_negotiation_detail("n1", hh, None)
    assert detail["id"] == "n1"
    assert detail["resume"]["full_name"] == "Петрова Аня"
    assert detail["resume"]["area"] == "Казань"
    assert detail["actions"][0]["id"] == "discard"
    assert "url" not in detail["actions"][0]


@pytest.mark.asyncio
async def test_execute_action_endpoint_refreshes_detail():
    from unittest.mock import AsyncMock, MagicMock
    from app.endpoints.v1 import hh_import as mod

    hh = MagicMock()
    hh.execute_negotiation_action = AsyncMock(return_value=None)
    hh.get_negotiation = AsyncMock(
        return_value={
            "id": "n1",
            "employer_state": {"id": "discard", "name": "Отказ"},
            "resume": {"id": "r1", "first_name": "Аня", "last_name": "Петрова"},
            "actions": [],
        }
    )
    hh.get_resume = AsyncMock(return_value={"id": "r1", "first_name": "Аня", "last_name": "Петрова"})

    body = mod.NegotiationActionBody(arguments={"message": "Спасибо, отказ"})
    out = await mod.execute_negotiation_action_endpoint("n1", "discard", body, hh, None)

    assert out["status"] == "ok"
    assert out["action_id"] == "discard"
    assert out["negotiation"]["employer_state"] == "discard"
    hh.execute_negotiation_action.assert_awaited_once_with(
        "n1", "discard", arguments={"message": "Спасибо, отказ"}
    )


@pytest.mark.asyncio
async def test_link_hh_vacancy_soft_fallback_when_get_fails():
    from unittest.mock import AsyncMock, MagicMock
    from fastapi import HTTPException
    from app.endpoints.v1 import hh_import as mod

    hh = MagicMock()
    hh.get_vacancy = AsyncMock(side_effect=HTTPException(status_code=404, detail="gone"))
    db = MagicMock()
    db.patch = AsyncMock(return_value={"id": 9, "hh_vacancy_id": "55"})

    result = await mod.link_hh_vacancy_to_local("55", 9, hh, db)

    assert result["status"] == "ok"
    assert result["hh_vacancy_id"] == "55"
    assert result["hh_vacancy_url"] == "https://hh.ru/vacancy/55"
    db.patch.assert_awaited_once()
    assert db.patch.await_args.kwargs["json"]["hh_vacancy_id"] == "55"


@pytest.mark.asyncio
async def test_import_negotiation_skips_existing_candidate():
    from unittest.mock import AsyncMock, MagicMock
    from app.endpoints.v1 import hh_import as mod

    hh = MagicMock()
    hh._request = AsyncMock(
        side_effect=[
            {"id": "n1", "resume": {"id": "r1"}},
            {
                "id": "r1",
                "first_name": "Анна",
                "last_name": "Петрова",
                "alternate_url": "https://hh.ru/resume/r1",
                "contact": [],
            },
        ]
    )
    db = MagicMock()
    db.get = AsyncMock(
        side_effect=[
            {"id": 5, "hh_vacancy_id": "v1"},
            {"items": [{"resume_id": "r1", "candidate_id": 42, "matched_by": "resume"}]},
        ]
    )
    db.post = AsyncMock()

    out = await mod.import_negotiation_as_candidate("v1", "n1", "response", hh, db)

    assert out["status"] == "already_exists"
    assert out["created"] is False
    assert out["candidate_id"] == 42
    db.post.assert_not_called()

