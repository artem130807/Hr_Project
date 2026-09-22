from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.v1.enums import CallConversationStatus
from app.t2.sync import backfill_missing_transcripts, load_access_token, sync_call_conversations


class FakeAtsClient:
    def __init__(self, records, transcripts):
        self.records = records
        self.transcripts = transcripts
        self.listed = False

    async def list_call_records(self, **kwargs):
        if self.listed:
            return []
        self.listed = True
        return self.records

    async def get_transcript(self, filename):
        return self.transcripts.get(filename, [])


@pytest.mark.asyncio
async def test_sync_upserts_and_fetches_stt(monkeypatch):
    records = [
        {
            "id": 123456789,
            "filename": "recording_2025-08-25_14-30-15.mp3",
            "callStartTime": "2025-08-25T14:30:15+03:00",
            "callEndTime": "2025-08-25T14:35:42+03:00",
            "callerNumber": "+79001234567",
            "operatorNumber": "+79007654321",
            "duration": 327,
            "status": "ANSWERED",
        },
        {"id": 2, "callStatus": "NOT_ANSWERED_COMMON"},
    ]
    words = [
        {"channel": "B", "startTime": 0.3, "endTime": 1.08, "word": "информируем"},
        {"channel": "B", "startTime": 1.08, "endTime": 1.26, "word": "что"},
    ]
    client = FakeAtsClient(records, {"recording_2025-08-25_14-30-15.mp3": words})

    upserted = []

    class Repo:
        def __init__(self, db):
            pass

        async def upsert_from_ats(self, record, transcript):
            upserted.append((record["filename"], transcript, record["ats_status"]))
            return SimpleNamespace(id=1)

    monkeypatch.setattr("app.t2.sync.CallConversationRepository", Repo)
    db = MagicMock()
    stats = await sync_call_conversations(
        db,
        client=client,
        lookback_hours=24,
        now=datetime(2025, 8, 26, tzinfo=timezone.utc),
    )
    assert stats["fetched"] == 2
    assert stats["skipped"] == 1
    assert stats["upserted"] == 1
    assert upserted[0][0] == "recording_2025-08-25_14-30-15.mp3"
    assert upserted[0][1][0]["word"] == "информируем"
    assert upserted[0][2] == "ANSWERED"


@pytest.mark.asyncio
async def test_sync_skips_without_token(monkeypatch):
    db = MagicMock()
    token_repo = MagicMock()
    token_repo.get = AsyncMock(return_value=None)

    class TokenRepo:
        def __init__(self, _db):
            pass

        async def get(self):
            return None

    monkeypatch.setattr("app.t2.sync.T2OAuthTokenRepository", TokenRepo)
    stats = await sync_call_conversations(db)
    assert stats["skipped_reason"] == "no_token"


def test_load_access_token():
    assert load_access_token({"access_token": " abc "}) == "abc"
    assert load_access_token({}) is None
    assert load_access_token(None) is None


@pytest.mark.asyncio
async def test_repository_insert_keeps_pending():
    from app.repositories.call_conversation_repository import CallConversationRepository

    stored = {}

    async def _get(_cls, pk):
        return stored.get(pk)

    db = MagicMock()
    db.get = AsyncMock(side_effect=_get)
    db.add = MagicMock(side_effect=lambda row: stored.__setitem__("new", row))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    db.execute = AsyncMock(return_value=result)

    repo = CallConversationRepository(db)
    row = await repo.upsert_from_ats(
        {
            "ats_id": "123",
            "filename": "a.mp3",
            "call_start_time": datetime(2025, 8, 25, tzinfo=timezone.utc),
            "call_end_time": None,
            "caller_number": "+7900",
            "operator_number": "+7901",
            "duration": 10,
            "ats_status": "ANSWERED",
            "direction": "incoming",
            "caller_name": None,
            "operator_name": None,
            "source": {"id": 123},
        },
        [{"channel": "B", "startTime": 0, "endTime": 1, "word": "привет"}],
    )
    assert row.status == CallConversationStatus.pending.value
    assert row.description is None
    assert row.payload["transcript"][0]["word"] == "привет"
    assert stored["new"] is row


@pytest.mark.asyncio
async def test_repository_update_preserves_hr_status():
    from app.db.v1.models import CallConversation
    from app.repositories.call_conversation_repository import CallConversationRepository

    existing = CallConversation(
        id=1,
        ats_id="123",
        filename="a.mp3",
        description="Отказ: не готов к ночным сменам",
        payload={"transcript": []},
        status=CallConversationStatus.rejected.value,
        caller_number="+7900",
    )

    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = existing
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    repo = CallConversationRepository(db)
    row = await repo.upsert_from_ats(
        {
            "ats_id": "123",
            "filename": "a.mp3",
            "call_start_time": datetime(2025, 8, 25, tzinfo=timezone.utc),
            "call_end_time": None,
            "caller_number": "+79001234567",
            "operator_number": "+7901",
            "duration": 12,
            "ats_status": "ANSWERED",
            "direction": "incoming",
            "caller_name": None,
            "operator_name": None,
            "source": {},
        },
        [{"word": "новое", "channel": "A", "startTime": 0, "endTime": 1}],
    )
    assert row.status == CallConversationStatus.rejected.value
    assert row.description == "Отказ: не готов к ночным сменам"
    assert row.caller_number == "+79001234567"
    assert row.payload["transcript"][0]["word"] == "новое"


class PagingAtsClient:
    def __init__(self):
        self.pages = 0
        self.stt_calls = []

    async def list_call_records(self, **kwargs):
        page = kwargs.get("page", 0)
        self.pages += 1
        if page == 0:
            return [{"filename": "a.mp3", "id": 1, "status": "ANSWERED"}]
        if page == 1:
            return [{"filename": "b.mp3", "id": 2, "status": "ANSWERED"}]
        return []

    async def get_transcript(self, filename):
        self.stt_calls.append(filename)
        if filename == "b.mp3":
            from app.t2.client import T2AtsError

            raise T2AtsError("stt failed", status_code=500)
        return [{"channel": "B", "startTime": 0, "endTime": 1, "word": "ok"}]


@pytest.mark.asyncio
async def test_sync_paginates_and_keeps_row_when_stt_fails(monkeypatch):
    upserted = []

    class Repo:
        def __init__(self, db):
            pass

        async def get_existing_by_filenames(self, filenames):
            return {}

        async def upsert_from_ats(self, record, transcript):
            upserted.append((record["filename"], transcript))
            return SimpleNamespace(id=len(upserted))

    monkeypatch.setattr("app.t2.sync.CallConversationRepository", Repo)
    monkeypatch.setattr("app.t2.sync.T2_CALL_SYNC_PAGE_SIZE", 1)
    monkeypatch.setattr("app.t2.sync.T2_CALL_SYNC_MAX_PAGES", 5)
    client = PagingAtsClient()
    stats = await sync_call_conversations(MagicMock(), client=client)
    assert stats["fetched"] == 2
    assert stats["upserted"] == 2
    assert stats["errors"] == 1
    assert stats["stt_missing"] == 1
    assert upserted[0][0] == "a.mp3"
    assert upserted[0][1][0]["word"] == "ok"
    assert upserted[1] == ("b.mp3", [])
    assert client.stt_calls == ["a.mp3", "b.mp3"]


@pytest.mark.asyncio
async def test_sync_skips_duplicate_filenames_and_persist_errors(monkeypatch):
    class Repo:
        def __init__(self, db):
            pass

        async def get_existing_by_filenames(self, filenames):
            return {}

        async def upsert_from_ats(self, record, transcript):
            raise RuntimeError("db down")

    monkeypatch.setattr("app.t2.sync.CallConversationRepository", Repo)
    client = FakeAtsClient(
        [
            {"filename": "dup.mp3", "id": 1},
            {"filename": "dup.mp3", "id": 1},
        ],
        {"dup.mp3": []},
    )
    stats = await sync_call_conversations(MagicMock(), client=client)
    assert stats["fetched"] == 2
    assert stats["skipped"] == 1
    assert stats["errors"] == 1
    assert stats["upserted"] == 0


@pytest.mark.asyncio
async def test_sync_stops_on_list_error(monkeypatch):
    from app.t2.client import T2AtsError

    class Client:
        async def list_call_records(self, **kwargs):
            raise T2AtsError("forbidden", status_code=403)

        async def get_transcript(self, filename):
            raise AssertionError("stt must not run")

    class Repo:
        def __init__(self, db):
            pass

        async def get_existing_by_filenames(self, filenames):
            return {}

        async def upsert_from_ats(self, record, transcript):
            raise AssertionError("must not persist")

    monkeypatch.setattr("app.t2.sync.CallConversationRepository", Repo)
    stats = await sync_call_conversations(MagicMock(), client=Client())
    assert stats["errors"] == 1
    assert stats["fetched"] == 0
    assert stats["upserted"] == 0


@pytest.mark.asyncio
async def test_sync_builds_client_from_stored_token(monkeypatch):
    created = {}

    class TokenRepo:
        def __init__(self, db):
            pass

        async def get(self):
            return SimpleNamespace(payload={"access_token": "stored-token"})

    class BuiltClient:
        def __init__(self, *, access_token, **kwargs):
            created["token"] = access_token

        async def list_call_records(self, **kwargs):
            return []

        async def get_transcript(self, filename):
            return []

    class Repo:
        def __init__(self, db):
            pass

        async def get_existing_by_filenames(self, filenames):
            return {}

        async def upsert_from_ats(self, record, transcript):
            return SimpleNamespace(id=1)

    monkeypatch.setattr("app.t2.sync.T2OAuthTokenRepository", TokenRepo)
    monkeypatch.setattr("app.t2.sync.T2AtsClient", BuiltClient)
    monkeypatch.setattr("app.t2.sync.CallConversationRepository", Repo)
    stats = await sync_call_conversations(MagicMock())
    assert created["token"] == "stored-token"
    assert stats["fetched"] == 0


@pytest.mark.asyncio
async def test_sync_retries_after_forced_refresh_on_403(monkeypatch):
    from app.t2.client import T2AtsError

    calls = {"ensure": 0, "list": 0}

    class TokenRepo:
        def __init__(self, db):
            pass

        async def get(self):
            return SimpleNamespace(payload={"access_token": "old", "refresh_token": "r"})

    class Client:
        def __init__(self, *, access_token, **kwargs):
            self.access_token = access_token

        async def list_call_records(self, **kwargs):
            calls["list"] += 1
            if self.access_token == "old":
                raise T2AtsError("forbidden", status_code=403)
            return []

        async def get_transcript(self, filename):
            return []

    async def ensure(repo, force=False, transport=None):
        calls["ensure"] += 1
        return "fresh" if force else "old"

    monkeypatch.setattr("app.t2.sync.T2OAuthTokenRepository", TokenRepo)
    monkeypatch.setattr("app.t2.sync.ensure_access_token", ensure)
    monkeypatch.setattr("app.t2.sync.T2AtsClient", Client)
    class Repo:
        def __init__(self, db):
            pass

        async def get_existing_by_filenames(self, filenames):
            return {}

        async def upsert_from_ats(self, record, transcript):
            return SimpleNamespace(id=1)

    monkeypatch.setattr("app.t2.sync.CallConversationRepository", Repo)
    stats = await sync_call_conversations(MagicMock())
    assert calls["ensure"] == 2
    assert calls["list"] == 2
    assert stats["fetched"] == 0
    assert stats.get("errors", 0) == 0


@pytest.mark.asyncio
async def test_sync_skips_when_ats_base_empty(monkeypatch):
    class TokenRepo:
        def __init__(self, db):
            pass

        async def get(self):
            return SimpleNamespace(payload={"access_token": "tok"})

    monkeypatch.setattr("app.t2.sync.T2OAuthTokenRepository", TokenRepo)
    monkeypatch.setattr("app.t2.sync.T2_ATS_BASE", "")
    stats = await sync_call_conversations(MagicMock())
    assert stats["skipped_reason"] == "no_base"


@pytest.mark.asyncio
async def test_sync_limits_records_per_tick(monkeypatch):
    class Client:
        def __init__(self):
            self.stt_calls = []

        async def list_call_records(self, **kwargs):
            page = kwargs.get("page", 0)
            if page == 0:
                return [{"filename": "a.mp3", "id": 1}, {"filename": "b.mp3", "id": 2}]
            return [{"filename": "c.mp3", "id": 3}]

        async def get_transcript(self, filename):
            self.stt_calls.append(filename)
            return [{"channel": "B", "word": "ok", "startTime": 0, "endTime": 1}]

    class Repo:
        def __init__(self, db):
            pass

        async def get_existing_by_filenames(self, filenames):
            return {}

        async def upsert_from_ats(self, record, transcript):
            return SimpleNamespace(id=1)

    monkeypatch.setattr("app.t2.sync.CallConversationRepository", Repo)
    monkeypatch.setattr("app.t2.sync.T2_CALL_SYNC_MAX_RECORDS_PER_TICK", 1)
    monkeypatch.setattr("app.t2.sync.T2_CALL_SYNC_MAX_PAGES", 5)
    client = Client()
    stats = await sync_call_conversations(MagicMock(), client=client)
    assert stats["fetched"] == 1
    assert stats["upserted"] == 1
    assert stats.get("limited_by_cap") is True
    assert client.stt_calls == ["a.mp3"]


@pytest.mark.asyncio
async def test_sync_skips_existing_and_defers_to_backfill(monkeypatch):
    class Client:
        async def list_call_records(self, **kwargs):
            return [{"filename": "known.mp3", "id": 1}]

        async def get_transcript(self, filename):
            raise AssertionError("must not request STT for known row")

    class Repo:
        def __init__(self, db):
            pass

        async def get_existing_by_filenames(self, filenames):
            return {"known.mp3": SimpleNamespace(filename="known.mp3", payload={"transcript": []})}

        async def upsert_from_ats(self, record, transcript):
            raise AssertionError("must not upsert known row")

    monkeypatch.setattr("app.t2.sync.CallConversationRepository", Repo)
    stats = await sync_call_conversations(MagicMock(), client=Client())
    assert stats["fetched"] == 1
    assert stats["skipped_existing"] == 1
    assert stats["deferred_to_backfill"] == 1
    assert stats["upserted"] == 0


@pytest.mark.asyncio
async def test_repository_list_recent_and_get(monkeypatch):
    from app.repositories.call_conversation_repository import CallConversationRepository

    rows = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.get = AsyncMock(return_value=rows[0])

    repo = CallConversationRepository(db)
    listed = await repo.list_recent(limit=10, offset=0, status="pending", phone="900")
    assert listed == rows
    db.execute.assert_awaited()
    assert await repo.get(1) is rows[0]


@pytest.mark.asyncio
async def test_repository_upsert_falls_back_to_ats_id():
    from app.db.v1.models import CallConversation
    from app.repositories.call_conversation_repository import CallConversationRepository

    existing = CallConversation(
        id=7,
        ats_id="abc",
        filename="old-name.mp3",
        description=None,
        payload={},
        status=CallConversationStatus.pending.value,
    )
    calls = {"n": 0}

    async def execute(stmt):
        calls["n"] += 1
        result = MagicMock()
        if calls["n"] == 1:
            result.scalars.return_value.first.return_value = None
        else:
            result.scalars.return_value.first.return_value = existing
        return result

    db = MagicMock()
    db.execute = AsyncMock(side_effect=execute)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    repo = CallConversationRepository(db)
    row = await repo.upsert_from_ats(
        {
            "ats_id": "abc",
            "filename": "new-name.mp3",
            "call_start_time": None,
            "call_end_time": None,
            "caller_number": None,
            "operator_number": None,
            "duration": None,
            "ats_status": None,
            "direction": "incoming",
            "caller_name": None,
            "operator_name": None,
            "source": {},
        },
        [],
    )
    assert row.filename == "new-name.mp3"
    assert row.id == 7


@pytest.mark.asyncio
async def test_repository_missing_transcript_helpers():
    from app.db.v1.models import CallConversation
    from app.repositories.call_conversation_repository import CallConversationRepository

    now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    rows = [
        CallConversation(
            id=1,
            filename="a.mp3",
            call_start_time=now - timedelta(days=1),
            payload={"transcript": []},
        ),
        CallConversation(
            id=2,
            filename="b.mp3",
            call_start_time=now - timedelta(days=2),
            payload={"transcript": [{"channel": "A", "word": "ok", "startTime": 0, "endTime": 1}]},
        ),
        CallConversation(
            id=3,
            filename="c.mp3",
            call_start_time=now - timedelta(days=8),
            payload={"other": 1},
        ),
    ]
    db = MagicMock()
    calls = {"n": 0}

    async def execute(stmt):
        calls["n"] += 1
        result = MagicMock()
        # list_missing_transcript() applies SQL cutoff; helper variant counts old in Python.
        result.scalars.return_value.all.return_value = rows[:2] if calls["n"] == 1 else rows
        return result

    db.execute = AsyncMock(side_effect=execute)
    db.get = AsyncMock(side_effect=[rows[0], rows[2]])
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    repo = CallConversationRepository(db)
    missing = await repo.list_missing_transcript(
        limit=2,
        scan_multiplier=4,
        min_call_start_time=now - timedelta(days=7),
    )
    assert [row.id for row in missing] == [1]
    stmt = db.execute.await_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
    assert "call_start_time" in compiled

    picked, skipped_old = await repo.list_missing_transcript_for_backfill(
        limit=2,
        scan_multiplier=4,
        min_call_start_time=now - timedelta(days=7),
    )
    assert [row.id for row in picked] == [1]
    assert skipped_old == 1

    changed = await repo.update_transcript(
        1,
        [{"channel": "B", "word": "привет", "startTime": 0, "endTime": 1}],
    )
    assert changed is True
    assert rows[0].payload["transcript"][0]["word"] == "привет"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_backfill_updates_rows_when_stt_available(monkeypatch):
    captured = {}

    class Client:
        async def get_transcript(self, filename):
            if filename == "a.mp3":
                return [{"channel": "B", "word": "готов", "startTime": 0, "endTime": 1}]
            return []

    updates = []

    class Repo:
        def __init__(self, db):
            pass

        async def list_missing_transcript_for_backfill(
            self, *, limit=12, scan_multiplier=5, min_call_start_time=None
        ):
            assert limit == 2
            assert min_call_start_time is not None
            captured["cutoff"] = min_call_start_time
            return (
                [
                    SimpleNamespace(id=1, filename="a.mp3"),
                    SimpleNamespace(id=2, filename="b.mp3"),
                ],
                3,
            )

        async def update_transcript(self, conversation_id, transcript):
            updates.append((conversation_id, transcript))
            return True

    monkeypatch.setattr("app.t2.sync.CallConversationRepository", Repo)
    monkeypatch.setattr("app.t2.sync.asyncio.sleep", AsyncMock())
    stats = await backfill_missing_transcripts(
        MagicMock(),
        client=Client(),
        batch_size=2,
        request_delay_seconds=0.01,
    )
    assert stats["scanned"] == 2
    assert stats["updated"] == 1
    assert stats["stt_missing"] == 1
    assert stats["skipped_old"] == 3
    assert updates[0][0] == 1
    assert isinstance(captured["cutoff"], datetime)


@pytest.mark.asyncio
async def test_backfill_skips_without_token(monkeypatch):
    class TokenRepo:
        def __init__(self, _db):
            pass

        async def get(self):
            return None

    monkeypatch.setattr("app.t2.sync.T2OAuthTokenRepository", TokenRepo)
    stats = await backfill_missing_transcripts(MagicMock())
    assert stats["skipped_reason"] == "no_token"


@pytest.mark.asyncio
async def test_backfill_forces_refresh_on_403(monkeypatch):
    from app.t2.client import T2AtsError

    calls = {"ensure": 0}

    class TokenRepo:
        def __init__(self, _db):
            pass

        async def get(self):
            return SimpleNamespace(payload={"access_token": "old", "refresh_token": "r"})

    class Client:
        def __init__(self, *, access_token, **kwargs):
            self.access_token = access_token

        async def get_transcript(self, filename):
            if self.access_token == "old":
                raise T2AtsError("forbidden", status_code=403)
            return [{"channel": "A", "word": "ok", "startTime": 0, "endTime": 1}]

    class Repo:
        def __init__(self, _db):
            pass

        async def list_missing_transcript_for_backfill(
            self, *, limit=12, scan_multiplier=5, min_call_start_time=None
        ):
            return ([SimpleNamespace(id=10, filename="x.mp3")], 0)

        async def update_transcript(self, conversation_id, transcript):
            return True

    async def ensure(repo, force=False, transport=None):
        calls["ensure"] += 1
        return "fresh" if force else "old"

    monkeypatch.setattr("app.t2.sync.T2OAuthTokenRepository", TokenRepo)
    monkeypatch.setattr("app.t2.sync.ensure_access_token", ensure)
    monkeypatch.setattr("app.t2.sync.T2AtsClient", Client)
    monkeypatch.setattr("app.t2.sync.CallConversationRepository", Repo)
    stats = await backfill_missing_transcripts(MagicMock())
    assert calls["ensure"] == 2
    assert stats["updated"] == 1
    assert stats["errors"] == 0
