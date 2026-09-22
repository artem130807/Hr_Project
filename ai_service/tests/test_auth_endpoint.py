"""Auth token proxy endpoint with mocked httpx."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


class _FakeResponse:
    def __init__(self, status_code: int, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_token_user_success():
    from app.endpoints.v1.auth import get_access_token_for_user_endpoint
    from fastapi.security import OAuth2PasswordRequestForm

    form = OAuth2PasswordRequestForm(username="u", password="p", scope="")
    fake = _FakeResponse(201, {"access_token": "tok", "token_type": "bearer"})

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=fake)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.endpoints.v1.auth.httpx.AsyncClient", return_value=mock_client):
        result = await get_access_token_for_user_endpoint(form)

    assert result["access_token"] == "tok"
    mock_client.post.assert_awaited()


@pytest.mark.asyncio
async def test_token_user_invalid_credentials():
    from app.endpoints.v1.auth import get_access_token_for_user_endpoint
    from fastapi.security import OAuth2PasswordRequestForm

    form = OAuth2PasswordRequestForm(username="u", password="bad", scope="")
    fake = _FakeResponse(401, text="nope")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=fake)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.endpoints.v1.auth.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(HTTPException) as exc:
            await get_access_token_for_user_endpoint(form)
    assert exc.value.status_code == 401
