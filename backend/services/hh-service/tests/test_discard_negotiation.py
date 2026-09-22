"""TDD: HH discard negotiation client."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_discard_negotiation_uses_action_url():
    from app.clients.hh.simple_hh_client import SimpleHHClient

    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh._request = AsyncMock(
        side_effect=[
            {
                "id": "neg-1",
                "actions": [
                    {
                        "id": "discard",
                        "enabled": True,
                        "method": "PUT",
                        "url": "https://api.hh.ru/negotiations/discard/neg-1",
                        "arguments": [{"id": "message", "required": True}],
                    }
                ],
            },
            None,  # 204
        ]
    )

    with patch("app.clients.hh.simple_hh_client.config") as cfg:
        cfg.MOCK_HH = False
        result = await hh.discard_negotiation("neg-1", message="К сожалению, не подходите")

    assert result is None
    assert hh._request.await_count == 2
    method, path = hh._request.await_args_list[1].args[:2]
    assert method == "PUT"
    assert path == "/negotiations/discard/neg-1"
    assert hh._request.await_args_list[1].kwargs.get("data", {}).get("message") == (
        "К сожалению, не подходите"
    )


@pytest.mark.asyncio
async def test_discard_negotiation_mock_hh_short_circuits():
    from app.clients.hh.simple_hh_client import SimpleHHClient

    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh._request = AsyncMock()

    with patch("app.clients.hh.simple_hh_client.config") as cfg:
        cfg.MOCK_HH = True
        result = await hh.discard_negotiation("neg-99", message="x")

    assert result == {"status": "discarded", "id": "neg-99"}
    hh._request.assert_not_awaited()


@pytest.mark.asyncio
async def test_discard_negotiation_raises_when_action_disabled():
    from app.clients.hh.simple_hh_client import SimpleHHClient

    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh._request = AsyncMock(
        return_value={
            "id": "neg-1",
            "actions": [{"id": "discard", "enabled": False, "url": "/negotiations/discard/neg-1"}],
        }
    )

    with patch("app.clients.hh.simple_hh_client.config") as cfg:
        cfg.MOCK_HH = False
        with pytest.raises(HTTPException) as exc:
            await hh.discard_negotiation("neg-1")

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_discard_falls_back_to_discard_by_employer():
    """HH often enables discard_by_employer while classic discard is off."""
    from app.clients.hh.simple_hh_client import SimpleHHClient

    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh._request = AsyncMock(
        side_effect=[
            {
                "id": "neg-1",
                "actions": [
                    {
                        "id": "discard",
                        "enabled": False,
                        "url": "https://api.hh.ru/negotiations/discard/neg-1",
                    },
                    {
                        "id": "discard_by_employer",
                        "enabled": True,
                        "method": "PUT",
                        "url": "https://api.hh.ru/negotiations/discard_by_employer/neg-1",
                        "arguments": [{"id": "message", "required": True}],
                    },
                ],
            },
            None,
        ]
    )

    with patch("app.clients.hh.simple_hh_client.config") as cfg:
        cfg.MOCK_HH = False
        await hh.discard_negotiation("neg-1", message="Не подходит")

    method, path = hh._request.await_args_list[1].args[:2]
    assert method == "PUT"
    assert path == "/negotiations/discard_by_employer/neg-1"
    assert hh._request.await_args_list[1].kwargs["data"]["message"] == "Не подходит"


@pytest.mark.asyncio
async def test_get_negotiation_mock():
    from app.clients.hh.simple_hh_client import SimpleHHClient

    hh = SimpleHHClient.__new__(SimpleHHClient)
    hh._request = AsyncMock()

    with patch("app.clients.hh.simple_hh_client.config") as cfg:
        cfg.MOCK_HH = True
        topic = await hh.get_negotiation("nid-1")

    assert topic["id"] == "nid-1"
    assert any(a["id"] == "discard" for a in topic["actions"])
    hh._request.assert_not_awaited()
