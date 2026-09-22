import pytest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException


@pytest.mark.asyncio
async def test_sync_candidate_hh_action_posts_via_internal_proxy():
    from app.utils.hh_sync import sync_candidate_hh_action

    with patch("app.config.HH_SERVICE_URL", "http://hh-service:8003"), patch(
        "app.endpoints.v1.vacancies._proxy_hh_import",
        new=AsyncMock(return_value={"status": "ok", "action_id": "consider"}),
    ) as proxy:
        out = await sync_candidate_hh_action(None, 7, "consider")

    assert out["status"] == "ok"
    proxy.assert_awaited_once()
    args, kwargs = proxy.await_args
    assert args[0] == "POST"
    assert args[1] == "hh/candidates/7/actions/consider"
    assert kwargs["json_body"] == {}
    assert kwargs["timeout"] == 90.0


@pytest.mark.asyncio
async def test_sync_candidate_hh_action_noop_without_url():
    from app.utils.hh_sync import sync_candidate_hh_action

    with patch("app.config.HH_SERVICE_URL", None):
        out = await sync_candidate_hh_action(None, 1, "offer")
    assert out["status"] == "unavailable"
    assert out["reason"] == "hh_service_not_configured"


@pytest.mark.asyncio
async def test_sync_candidate_hh_action_sends_message_body():
    from app.utils.hh_sync import sync_candidate_hh_action

    with patch("app.config.HH_SERVICE_URL", "http://hh-service:8003"), patch(
        "app.endpoints.v1.vacancies._proxy_hh_import",
        new=AsyncMock(return_value={"status": "ok", "action_id": "message"}),
    ) as proxy:
        out = await sync_candidate_hh_action(None, 6, "message", message="test")

    assert out["status"] == "ok"
    assert proxy.await_args.kwargs["json_body"] == {"message": "test"}
    assert proxy.await_args.args[1] == "hh/candidates/6/actions/message"


@pytest.mark.asyncio
async def test_sync_candidate_hh_action_keeps_hh_error_detail():
    from app.utils.hh_sync import sync_candidate_hh_action

    with patch("app.config.HH_SERVICE_URL", "http://hh-service:8003"), patch(
        "app.endpoints.v1.vacancies._proxy_hh_import",
        new=AsyncMock(
            side_effect=HTTPException(403, detail="HH API Error no_invitation")
        ),
    ):
        out = await sync_candidate_hh_action(None, 6, "message", message="hi")

    assert out["status"] == "unavailable"
    assert out["reason"] == "hh_api_rejected"
    assert out["http_status"] == 403
    assert "no_invitation" in str(out["detail"])
