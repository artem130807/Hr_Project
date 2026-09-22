"""HH dictionary proxy falls back to public HH API when hh-service is unavailable."""
from unittest.mock import AsyncMock, patch

import pytest

from app.endpoints.v1 import hh_dictionaries as hh_dict


@pytest.mark.asyncio
async def test_proxy_uses_hh_service_when_available():
    with patch(
        "app.endpoints.v1.vacancies._proxy_hh_import",
        new=AsyncMock(return_value=[{"id": "full", "name": "Полная"}]),
    ) as proxy:
        result = await hh_dict._proxy("employment")
    assert result == [{"id": "full", "name": "Полная"}]
    proxy.assert_awaited_once_with("GET", "employment", timeout=20.0)


@pytest.mark.asyncio
async def test_proxy_falls_back_to_public_api():
    with patch(
        "app.endpoints.v1.vacancies._proxy_hh_import",
        new=AsyncMock(side_effect=Exception("hh down")),
    ), patch.object(
        hh_dict, "_fetch_public", new=AsyncMock(return_value=[{"id": "full"}])
    ) as fetch:
        result = await hh_dict._proxy("employment")
        assert result == [{"id": "full"}]
        fetch.assert_awaited_once_with("employment")


@pytest.mark.asyncio
async def test_proxy_works_without_hh_client():
    with patch(
        "app.endpoints.v1.vacancies._proxy_hh_import",
        new=AsyncMock(side_effect=Exception("no hh")),
    ), patch.object(hh_dict, "_fetch_public", new=AsyncMock(return_value=[{"id": "1"}])):
        result = await hh_dict._proxy("areas")
        assert result == [{"id": "1"}]
