"""TDD: generic HH negotiation action executor + detail normalization."""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_execute_negotiation_action_puts_form_args():
    from app.clients.hh.simple_hh_client import SimpleHHClient

    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh._request = AsyncMock(
        side_effect=[
            {
                "id": "n1",
                "actions": [
                    {
                        "id": "phone_interview",
                        "enabled": True,
                        "method": "PUT",
                        "url": "https://api.hh.ru/negotiations/phone_interview/n1",
                        "arguments": [{"id": "message", "required": False}],
                    }
                ],
            },
            None,
        ]
    )

    with patch("app.clients.hh.simple_hh_client.config") as cfg:
        cfg.MOCK_HH = False
        result = await hh.execute_negotiation_action(
            "n1", "phone_interview", arguments={"message": "Звоним завтра"}
        )

    assert result is None
    method, path = hh._request.await_args_list[1].args[:2]
    assert method == "PUT"
    assert path == "/negotiations/phone_interview/n1"
    assert hh._request.await_args_list[1].kwargs["data"]["message"] == "Звоним завтра"


@pytest.mark.asyncio
async def test_execute_action_missing_raises_409():
    from app.clients.hh.simple_hh_client import SimpleHHClient

    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh._request = AsyncMock(
        return_value={"id": "n1", "actions": [{"id": "discard", "enabled": True, "url": "/x"}]}
    )
    with patch("app.clients.hh.simple_hh_client.config") as cfg:
        cfg.MOCK_HH = False
        with pytest.raises(HTTPException) as exc:
            await hh.execute_negotiation_action("n1", "interview")
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_discard_delegates_to_execute_action():
    from app.clients.hh.simple_hh_client import SimpleHHClient

    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh.execute_negotiation_action = AsyncMock(return_value={"status": "ok"})
    with patch("app.clients.hh.simple_hh_client.config") as cfg:
        cfg.MOCK_HH = False
        out = await hh.discard_negotiation("n9", message="bye")
    assert out == {"status": "ok"}
    hh.execute_negotiation_action.assert_awaited_once_with(
        "n9",
        SimpleHHClient.DISCARD_ACTION_IDS,
        arguments={"message": "bye"},
        topic=None,
    )


@pytest.mark.asyncio
async def test_consider_delegates_to_execute_action():
    from app.clients.hh.simple_hh_client import SimpleHHClient

    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh.execute_negotiation_action = AsyncMock(return_value={"status": "ok"})
    with patch("app.clients.hh.simple_hh_client.config") as cfg:
        cfg.MOCK_HH = False
        out = await hh.consider_negotiation("n3")
    assert out == {"status": "ok"}
    hh.execute_negotiation_action.assert_awaited_once_with(
        "n3",
        SimpleHHClient.CONSIDER_ACTION_IDS,
        topic=None,
    )


@pytest.mark.asyncio
async def test_send_message_to_negotiation_posts_chat_message():
    from app.clients.hh.simple_hh_client import SimpleHHClient

    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh.get_negotiation = AsyncMock(return_value={"id": "n5"})
    hh._request = AsyncMock(return_value={"ok": True})
    with patch("app.clients.hh.simple_hh_client.config") as cfg:
        cfg.MOCK_HH = False
        out = await hh.send_message_to_negotiation("n5", "Текст сообщения")
    assert out["status"] == "sent"
    assert out["via"] == "chat"
    hh._request.assert_awaited_once_with(
        "POST",
        "/negotiations/n5/messages",
        data={"message": "Текст сообщения"},
    )


@pytest.mark.asyncio
async def test_send_message_uses_messages_url_from_topic():
    from app.clients.hh.simple_hh_client import SimpleHHClient

    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh.get_negotiation = AsyncMock(
        return_value={
            "id": "n5",
            "messages_url": "https://api.hh.ru/negotiations/n5/messages",
        }
    )
    hh._request = AsyncMock(return_value={"status": "ok", "http_status": 201})
    hh._strip_hh_api_host = SimpleHHClient._strip_hh_api_host
    with patch("app.clients.hh.simple_hh_client.config") as cfg:
        cfg.MOCK_HH = False
        out = await hh.send_message_to_negotiation("n5", "Привет")
    assert out["via"] == "chat"
    hh._request.assert_awaited_once_with(
        "POST",
        "/negotiations/n5/messages",
        data={"message": "Привет"},
    )


@pytest.mark.asyncio
async def test_send_message_considers_then_retries_on_no_invitation():
    from app.clients.hh.simple_hh_client import SimpleHHClient

    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh.get_negotiation = AsyncMock(return_value={"id": "n5", "actions": []})
    hh.consider_negotiation = AsyncMock(return_value={"status": "considered"})
    hh._request = AsyncMock(
        side_effect=[
            HTTPException(403, "HH API Error no_invitation"),
            {"status": "ok", "http_status": 201},
        ]
    )
    with patch("app.clients.hh.simple_hh_client.config") as cfg:
        cfg.MOCK_HH = False
        out = await hh.send_message_to_negotiation("n5", "Ссылка на тест")
    assert out["via"] == "chat"
    hh.consider_negotiation.assert_awaited_once()
    assert hh._request.await_count == 2


@pytest.mark.asyncio
async def test_send_message_falls_back_to_action_with_message():
    from app.clients.hh.simple_hh_client import SimpleHHClient

    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh.get_negotiation = AsyncMock(return_value={"id": "n5"})
    hh.consider_negotiation = AsyncMock(return_value={"status": "considered"})
    hh._request = AsyncMock(side_effect=HTTPException(403, "HH API Error no_invitation"))
    hh.execute_negotiation_action = AsyncMock(return_value={"status": "ok", "action_id": "assessment"})
    with patch("app.clients.hh.simple_hh_client.config") as cfg:
        cfg.MOCK_HH = False
        out = await hh.send_message_to_negotiation("n5", "Ссылка на тест")
    assert out["via"] == "action"
    hh.execute_negotiation_action.assert_awaited_once()
    kwargs = hh.execute_negotiation_action.await_args.kwargs
    assert kwargs["arguments"]["message"] == "Ссылка на тест"
    assert kwargs["require_arguments"] == ("message",)


@pytest.mark.asyncio
async def test_offer_fallback_never_uses_interview_action():
    from app.clients.hh.simple_hh_client import SimpleHHClient, apply_offer_letter_heading

    assert apply_offer_letter_heading("Собеседование:\nтело").startswith("Приглашаем вас на работу")
    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh.execute_negotiation_action = AsyncMock(side_effect=HTTPException(409, "no offer"))
    hh.send_message_to_negotiation = AsyncMock(return_value={"via": "chat"})
    with patch("app.clients.hh.simple_hh_client.config") as cfg:
        cfg.MOCK_HH = False
        await hh.offer_negotiation("n9", message="Текст оффера")
    ids = hh.send_message_to_negotiation.await_args.kwargs["fallback_action_ids"]
    assert "interview" not in ids
    assert "phone_interview" not in ids


def test_normalize_negotiation_detail_exposes_safe_actions():
    from app.utils.hh_import import normalize_negotiation_detail

    raw = {
        "id": "abc",
        "created_at": "2026-08-14T10:00:00+0300",
        "state": {"id": "response", "name": "Отклик"},
        "employer_state": {"id": "response", "name": "Неразобранные"},
        "alternate_url": "https://hh.ru/employer/vacancyresponses/abc",
        "resume": {
            "id": "r1",
            "title": "Логист",
            "first_name": "Иван",
            "last_name": "Иванов",
            "age": 30,
            "alternate_url": "https://hh.ru/resume/r1",
            "area": {"name": "Москва"},
            "total_experience": {"months": 24},
            "skill_set": ["Excel"],
            "salary": {"amount": 100000, "currency": "RUR"},
        },
        "actions": [
            {
                "id": "discard",
                "name": "Отказ",
                "enabled": True,
                "method": "PUT",
                "url": "https://api.hh.ru/negotiations/discard/abc",
                "arguments": [{"id": "message", "required": False}],
            },
            {
                "id": "phone_interview",
                "name": "Телефонное интервью",
                "enabled": False,
                "method": "PUT",
                "url": "https://api.hh.ru/negotiations/phone_interview/abc",
                "arguments": [],
            },
        ],
    }
    detail = normalize_negotiation_detail(raw)
    assert detail["id"] == "abc"
    assert detail["resume"]["full_name"] == "Иванов Иван"
    assert detail["resume"]["area"] == "Москва"
    assert detail["resume"]["alternate_url"] == "https://hh.ru/resume/r1"
    assert detail["hh_url"] == "https://hh.ru/employer/vacancyresponses/abc"
    assert len(detail["actions"]) == 2
    discard = detail["actions"][0]
    assert discard["id"] == "discard"
    assert discard["enabled"] is True
    assert "url" not in discard  # never leak raw action URLs to FE
    assert discard["arguments"][0]["id"] == "message"
