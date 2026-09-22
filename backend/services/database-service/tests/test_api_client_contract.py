from unittest.mock import AsyncMock
import httpx
import pytest
from app.clients.api_client import APICLient, UpstreamHTTPError


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [[{"msg": "bad request"}], "unavailable", {"detail": "rejected"}])
async def test_upstream_json_error_shape_does_not_crash_client(body):
    client = APICLient("https://upstream.test", AsyncMock(), headers_required=False)
    await client.client.aclose()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(422, json=body)))
    try:
        with pytest.raises(UpstreamHTTPError) as exc:
            await client.post("/test", raise_http=True)
        assert exc.value.status_code == 422
        assert exc.value.detail == (body["detail"] if isinstance(body, dict) else body)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_timeout_is_mapped_and_credentials_forwarded():
    manager = AsyncMock(); manager.get_token.return_value = "service-token"
    client = APICLient("https://upstream.test", manager, internal_token="internal")
    await client.client.aclose()
    def transport(request):
        assert request.headers["Authorization"] == "Bearer service-token"
        assert request.headers["X-Internal-Token"] == "internal"
        raise httpx.ReadTimeout("slow", request=request)
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
    try:
        with pytest.raises(UpstreamHTTPError) as exc:
            await client.get("/test", raise_http=True)
        assert exc.value.status_code == 504
    finally:
        await client.close()
