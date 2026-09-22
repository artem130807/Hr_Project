from datetime import datetime, timezone

import httpx
import pytest

from app.t2.client import T2AtsClient, T2AtsError


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/call-records/info"):
        assert "Authorization" in request.headers
        assert request.headers["Authorization"] == "tok"
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "id": 123,
                        "filename": "rec.mp3",
                        "callerNumber": "+79001112233",
                    }
                ]
            },
        )
    if request.url.path.endswith("/call-records/file/stt"):
        assert request.url.params["filename"] == "rec.mp3"
        return httpx.Response(
            200,
            json=[{"channel": "B", "startTime": 0.1, "endTime": 0.5, "word": "привет"}],
        )
    return httpx.Response(404, json={"message": "missing"})


@pytest.mark.asyncio
async def test_list_and_stt():
    transport = httpx.MockTransport(_handler)
    client = T2AtsClient(
        access_token="tok",
        base_url="https://ats2.t2.ru/crm/openapi",
        transport=transport,
    )
    records = await client.list_call_records(
        start=datetime(2025, 8, 25, tzinfo=timezone.utc),
        end=datetime(2025, 8, 26, tzinfo=timezone.utc),
    )
    assert records[0]["filename"] == "rec.mp3"
    words = await client.get_transcript("rec.mp3")
    assert words == [{"channel": "B", "startTime": 0.1, "endTime": 0.5, "word": "привет"}]


@pytest.mark.asyncio
async def test_stt_404_returns_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Object not found"})

    client = T2AtsClient(access_token="tok", transport=httpx.MockTransport(handler))
    assert await client.get_transcript("missing.mp3") == []


@pytest.mark.asyncio
async def test_list_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="denied")

    client = T2AtsClient(access_token="tok", transport=httpx.MockTransport(handler))
    with pytest.raises(T2AtsError) as exc:
        await client.list_call_records(
            start=datetime(2025, 8, 25, tzinfo=timezone.utc),
            end=datetime(2025, 8, 26, tzinfo=timezone.utc),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_list_timeout_is_wrapped_as_t2_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timeout", request=request)

    client = T2AtsClient(access_token="tok", transport=httpx.MockTransport(handler))
    with pytest.raises(T2AtsError) as exc:
        await client.list_call_records(
            start=datetime(2025, 8, 25, tzinfo=timezone.utc),
            end=datetime(2025, 8, 26, tzinfo=timezone.utc),
        )
    assert "request failed" in str(exc.value).lower()


def test_unwrap_records_variants():
    assert T2AtsClient.unwrap_records([{"a": 1}]) == [{"a": 1}]
    assert T2AtsClient.unwrap_records({"items": [{"a": 1}]}) == [{"a": 1}]
    assert T2AtsClient.unwrap_records({"filename": "x.mp3"}) == [{"filename": "x.mp3"}]
    assert T2AtsClient.unwrap_records("nope") == []


def test_bearer_passthrough():
    client = T2AtsClient(access_token="Bearer abc", auth_scheme="")
    assert client._auth_header() == "Bearer abc"
    client2 = T2AtsClient(access_token="abc", auth_scheme="Bearer")
    assert client2._auth_header() == "Bearer abc"


def test_empty_token_rejected():
    with pytest.raises(T2AtsError, match="empty"):
        T2AtsClient(access_token="  ")


@pytest.mark.asyncio
async def test_list_sends_recorded_query_and_unwraps_array():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["Authorization"]
        return httpx.Response(
            200,
            json=[{"uuid": "u1", "recordFileName": "2022-08-12/file"}],
        )

    client = T2AtsClient(
        access_token="raw-token",
        base_url="https://ats2.t2.ru/crm/openapi",
        transport=httpx.MockTransport(handler),
    )
    records = await client.list_call_records(
        start=datetime(2025, 8, 25, tzinfo=timezone.utc),
        end=datetime(2025, 8, 26, tzinfo=timezone.utc),
        page=2,
        size=50,
    )
    assert captured["auth"] == "raw-token"
    assert "call-records/info" in captured["url"]
    assert "is_recorded=true" in captured["url"]
    assert "page=2" in captured["url"]
    assert "size=50" in captured["url"]
    assert records[0]["recordFileName"] == "2022-08-12/file"


@pytest.mark.asyncio
async def test_list_non_json_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>oops</html>")

    client = T2AtsClient(access_token="tok", transport=httpx.MockTransport(handler))
    with pytest.raises(T2AtsError, match="non-JSON"):
        await client.list_call_records(
            start=datetime(2025, 8, 25, tzinfo=timezone.utc),
            end=datetime(2025, 8, 26, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
async def test_stt_empty_filename_skips_http():
    called = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        called["n"] += 1
        return httpx.Response(500, text="nope")

    client = T2AtsClient(access_token="tok", transport=httpx.MockTransport(handler))
    assert await client.get_transcript("") == []
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_stt_500_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="stt down")

    client = T2AtsClient(access_token="tok", transport=httpx.MockTransport(handler))
    with pytest.raises(T2AtsError) as exc:
        await client.get_transcript("rec.mp3")
    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_stt_non_json_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    client = T2AtsClient(access_token="tok", transport=httpx.MockTransport(handler))
    with pytest.raises(T2AtsError, match="non-JSON"):
        await client.get_transcript("rec.mp3")
