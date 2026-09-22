from pathlib import Path
from io import BytesIO
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.datastructures import UploadFile
from fastapi import HTTPException

from app.db.v1.enums import CandidateStatus
from app.schemas.v1.messages import SendOfferData
from app.services.candidate_documents import (
    PreparedUpload,
    build_public_url,
    hash_token,
    prepare_uploads,
    safe_filename,
    upload_package,
    create_upload_session,
    move_draft_package,
    purge_expired_upload_sessions,
    resolve_upload_session,
)
from app.db.v1.models import CandidateDocumentUploadSession


def test_document_token_is_only_stored_as_hash():
    token = "secret-public-token"
    digest = hash_token(token)
    assert token not in digest
    assert len(digest) == 64
    assert digest == hash_token(token)


@pytest.mark.parametrize(
    "filename,content_type,suffix",
    [("passport.JPG", "image/jpeg", ".jpg"), ("../../scan", "application/pdf", ".pdf")],
)
def test_safe_document_filename(filename, content_type, suffix):
    result = safe_filename(filename, 1, content_type)
    assert result.startswith("01-")
    assert result.endswith(suffix)
    assert ".." not in result and "/" not in result and "\\" not in result


@pytest.mark.asyncio
async def test_upload_normalizes_long_filename_and_mismatched_extension():
    upload = UploadFile(filename="../../" + "a" * 500 + ".pdf", file=BytesIO(b"\xff\xd8\xffpayload"),
                        headers={"content-type": "image/jpeg"})
    item = (await prepare_uploads([upload], ["passport"], "draft/"))[0]
    assert len(item.filename) < 255
    assert item.filename.endswith(".jpg")
    assert "/" not in item.filename and ".." not in item.filename
    assert item.key.endswith(item.filename)


@pytest.mark.asyncio
@pytest.mark.parametrize("batch_size", [0, -1, 1001])
async def test_purge_rejects_unbounded_batch(batch_size):
    db = MagicMock()
    db.execute = AsyncMock()
    with pytest.raises(ValueError):
        await purge_expired_upload_sessions(db, batch_size=batch_size)
    db.execute.assert_not_awaited()


def test_offer_documents_link_is_explicit_opt_in():
    basic = SendOfferData(candidate_id=1, offer_text="offer")
    enabled = SendOfferData(candidate_id=1, offer_text="offer", include_documents_link=True)
    assert basic.include_documents_link is False
    assert enabled.include_documents_link is True
    assert CandidateStatus.full_documents.value == "Full documents"


def test_public_document_url_prefers_configured_frontend(monkeypatch):
    monkeypatch.setenv("HR_FRONTEND_BASE_URL", "https://hr.example.ru/v1/")
    request = SimpleNamespace(headers={"Origin": "https://api.example.ru"}, base_url="https://api.example.ru/v1/")
    assert build_public_url(request, "a/b") == "https://hr.example.ru/candidate-documents/a%2Fb"


def test_candidate_document_routes_and_startup_migration_are_registered():
    from main import app

    paths = {(route.path, method) for route in app.routes for method in getattr(route, "methods", set())}
    assert ("/v1/public/candidate-documents/{token}", "GET") in paths
    assert ("/v1/public/candidate-documents/{token}", "POST") in paths
    assert ("/v1/public/candidate-documents/{token}/upload-sessions", "POST") in paths
    assert ("/v1/public/candidate-documents/{token}/upload-sessions/files", "POST") in paths
    assert ("/v1/public/candidate-documents/{token}/upload-sessions/files/{file_id}", "DELETE") in paths
    assert ("/v1/public/candidate-documents/{token}/upload-sessions/submit", "POST") in paths
    assert ("/v1/candidate-documents", "GET") in paths
    assert ("/v1/candidate-documents/{docs_id}/complete", "POST") in paths
    main_source = Path(__file__).resolve().parents[1].joinpath("main.py").read_text(encoding="utf-8")
    assert '"candidate_documents.sql"' in main_source
    assert "Candidate documents migration failed" in main_source
    migration = Path(__file__).resolve().parents[1].joinpath("migrations/candidate_documents.sql").read_text(encoding="utf-8")
    assert "candidate_document_upload_sessions" in migration
    assert "candidate_document_upload_files" in migration


@pytest.mark.asyncio
async def test_upload_validation_checks_real_file_signature():
    fake = UploadFile(filename="passport.jpg", file=BytesIO(b"<html>not an image</html>"), headers={"content-type": "image/jpeg"})
    with pytest.raises(HTTPException) as exc:
        await prepare_uploads([fake], ["passport"], "candidates/1/employment-documents/x/")
    assert exc.value.status_code == 415

    jpeg = UploadFile(filename="passport.jpg", file=BytesIO(b"\xff\xd8\xffpayload"), headers={"content-type": "image/jpeg"})
    prepared = await prepare_uploads([jpeg], ["passport"], "candidates/1/employment-documents/x/")
    assert prepared[0].key.startswith("candidates/1/employment-documents/x/passport/")


@pytest.mark.asyncio
async def test_upload_rejects_unknown_document_kind():
    jpeg = UploadFile(filename="scan.jpg", file=BytesIO(b"\xff\xd8\xffpayload"), headers={"content-type": "image/jpeg"})
    with pytest.raises(HTTPException) as exc:
        await prepare_uploads([jpeg], ["arbitrary_private_kind"], "candidates/1/employment-documents/x/")
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_partial_s3_upload_is_rolled_back(monkeypatch):
    class FakeS3:
        def __init__(self):
            self.puts = []
            self.deletes = []

        def put_object(self, **kwargs):
            self.puts.append(kwargs["Key"])
            if len(self.puts) == 2:
                raise RuntimeError("storage unavailable")

        def delete_object(self, **kwargs):
            self.deletes.append(kwargs["Key"])

    client = FakeS3()
    monkeypatch.setattr("app.services.candidate_documents._s3_client", lambda: client)
    monkeypatch.setattr("app.services.candidate_documents.S3_BUCKET", "private-documents")
    prepared = [
        PreparedUpload("one", "passport", "one.jpg", "image/jpeg", b"\xff\xd8\xff1"),
        PreparedUpload("two", "snils", "two.jpg", "image/jpeg", b"\xff\xd8\xff2"),
    ]

    with pytest.raises(HTTPException) as exc:
        await upload_package(prepared)

    assert exc.value.status_code == 502
    assert client.puts == ["one", "two"]
    assert client.deletes == ["one"]


@pytest.mark.asyncio
async def test_upload_session_token_is_hashed_and_scoped_to_invite():
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    invite = SimpleNamespace(id=8, candidate_id=42)
    session, token = await create_upload_session(db, invite)
    assert token not in session.token_hash
    assert session.candidate_id == 42 and session.invite_id == 8
    assert session.status == "draft"
    assert session.expires_at > datetime.now(timezone.utc) + timedelta(hours=70)


@pytest.mark.asyncio
async def test_resolve_upload_session_rejects_expired_or_cross_invite():
    expired = SimpleNamespace(
        status="draft", expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = expired
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    with pytest.raises(HTTPException) as exc:
        await resolve_upload_session(db, SimpleNamespace(id=1, candidate_id=2), "secret")
    assert exc.value.status_code == 404
    statement = db.execute.await_args.args[0]
    assert "invite_id" in str(statement) and "candidate_id" in str(statement)


@pytest.mark.asyncio
async def test_move_draft_package_uses_durable_prefix_and_submitted_tag(monkeypatch):
    class FakeS3:
        def __init__(self): self.copies = []
        def copy_object(self, **kwargs): self.copies.append(kwargs)

    client = FakeS3()
    monkeypatch.setattr("app.services.candidate_documents._s3_client", lambda: client)
    monkeypatch.setattr("app.services.candidate_documents.S3_BUCKET", "private-documents")
    file = SimpleNamespace(
        s3_key="candidate-docs/42/draft/session/passport/f.jpg", document_type="passport",
        file_id="file123", filename="passport.jpg", content_type="image/jpeg", size=100,
    )
    manifest = await move_draft_package([file], 42, "session")
    assert manifest[0]["key"] == "candidate-docs/42/submitted/session/passport/file123.jpg"
    assert client.copies[0]["Tagging"] == "status=submitted"
    assert client.copies[0]["TaggingDirective"] == "REPLACE"


def test_s3_lifecycle_targets_only_draft_tag():
    source = Path(__file__).resolve().parents[3].joinpath("docs/candidate-documents-s3-lifecycle.json").read_text(encoding="utf-8")
    assert '"Key": "status"' in source
    assert '"Value": "draft"' in source
    assert '"Days": 3' in source


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["commit", "signing"])
async def test_draft_upload_uses_required_s3_path_and_rolls_back_object_on_db_error(failure):
    from app.endpoints.v1 import candidate_documents as endpoint

    invite = SimpleNamespace(id=2, candidate_id=42)
    session = SimpleNamespace(id=3, session_id="session123")
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = []
    db = MagicMock()
    db.execute = AsyncMock(return_value=rows_result)
    db.commit = AsyncMock(side_effect=RuntimeError("database unavailable"))
    db.rollback = AsyncMock()
    upload = UploadFile(filename="passport.jpg", file=BytesIO(b"\xff\xd8\xffpayload"), headers={"content-type": "image/jpeg"})
    uploaded = AsyncMock(side_effect=lambda item: {
        "key": item.key, "kind": item.kind, "filename": item.filename,
        "content_type": item.content_type, "size": len(item.data),
    })
    deleted = AsyncMock()
    with (
        patch.object(endpoint, "resolve_invite", AsyncMock(return_value=invite)),
        patch.object(endpoint, "resolve_upload_session", AsyncMock(return_value=session)),
        patch.object(endpoint, "upload_draft_file", uploaded),
        patch.object(endpoint, "presigned_manifest", AsyncMock(
            side_effect=RuntimeError("signing failed") if failure == "signing" else None,
            return_value=[{"url": "https://storage.test/preview"}],
        )),
        patch.object(endpoint, "delete_objects", deleted),
        patch.object(endpoint.uuid, "uuid4", return_value=SimpleNamespace(hex="file123")),
    ):
        with pytest.raises(RuntimeError):
            await endpoint.upload_candidate_document_draft_file(
                "invite", "session-token", "passport", upload, db
            )
    item = uploaded.await_args.args[0]
    assert item.key == "candidate-docs/42/draft/session123/passport/file123.jpg"
    db.rollback.assert_awaited_once()
    deleted.assert_awaited_once()
    if failure == "signing":
        db.commit.assert_not_awaited()
    else:
        db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_session_atomically_marks_metadata_and_consumes_invite(monkeypatch):
    from app.endpoints.v1 import candidate_documents as endpoint

    invite = SimpleNamespace(id=2, candidate_id=42, used_at=None)
    session = SimpleNamespace(id=3, session_id="session123", status="draft", submitted_at=None)
    file = SimpleNamespace(id=4, file_id="file123", document_type="passport",
                           s3_key="draft-key", filename="passport.jpg",
                           content_type="image/jpeg", size=100, status="uploaded")
    no_docs = MagicMock(); no_docs.scalar_one_or_none.return_value = None
    file_rows = MagicMock(); file_rows.scalars.return_value.all.return_value = [file]
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[no_docs, file_rows])
    db.commit = AsyncMock(); db.flush = AsyncMock(); db.rollback = AsyncMock(); db.add = MagicMock()
    manifest = [{"key": "candidate-docs/42/submitted/session123/passport/file123.jpg",
                 "kind": "passport", "filename": "passport.jpg", "content_type": "image/jpeg", "size": 100}]
    deleted = AsyncMock()
    with (
        patch.object(endpoint, "resolve_invite", AsyncMock(return_value=invite)),
        patch.object(endpoint, "resolve_upload_session", AsyncMock(return_value=session)),
        patch.object(endpoint, "move_draft_package", AsyncMock(return_value=manifest)),
        patch.object(endpoint, "delete_objects", deleted),
    ):
        result = await endpoint.submit_candidate_document_upload_session(
            "invite", {"session_token": "secret"}, SimpleNamespace(headers={}), db
        )
    row = db.add.call_args.args[0]
    assert row.s3_prefix.endswith("candidate-docs/42/submitted/session123/")
    assert row.manifest == manifest
    assert session.status == "submitted" and session.submitted_at
    assert file.status == "submitted" and invite.used_at
    db.commit.assert_awaited_once()
    deleted.assert_awaited_once_with([{"key": "draft-key"}])
    assert result["status"] == "submitted"


@pytest.mark.asyncio
@pytest.mark.parametrize("storage_deleted,expected", [(True, 1), (False, 0)])
async def test_expired_draft_is_finalized_only_after_s3_cleanup(storage_deleted, expected):
    session = SimpleNamespace(id=3, status="draft")
    file = SimpleNamespace(s3_key="candidate-docs/42/draft/session/file.jpg")
    session_rows = MagicMock(); session_rows.scalars.return_value.all.return_value = [session]
    file_rows = MagicMock(); file_rows.scalars.return_value.all.return_value = [file]
    db = MagicMock(); db.execute = AsyncMock(side_effect=[session_rows, file_rows]); db.commit = AsyncMock()
    with patch("app.services.candidate_documents.delete_objects", AsyncMock(return_value=storage_deleted)):
        result = await purge_expired_upload_sessions(db)
    assert result == expected
    assert session.status == ("expired" if storage_deleted else "draft")
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_copy_failure_removes_only_copied_submitted_objects(monkeypatch):
    class FakeS3:
        def __init__(self): self.copied = []; self.deleted = []
        def copy_object(self, **kwargs):
            if len(self.copied) == 1:
                raise RuntimeError("S3 failed on second object")
            self.copied.append(kwargs["Key"])
        def delete_object(self, **kwargs): self.deleted.append(kwargs["Key"])

    client = FakeS3()
    monkeypatch.setattr("app.services.candidate_documents._s3_client", lambda: client)
    monkeypatch.setattr("app.services.candidate_documents.S3_BUCKET", "private-documents")
    files = [SimpleNamespace(
        s3_key=f"candidate-docs/42/draft/session/{number}.pdf", document_type="passport",
        file_id=f"file{number}", filename=f"{number}.pdf", content_type="application/pdf", size=100,
    ) for number in (1, 2)]
    with pytest.raises(HTTPException) as exc:
        await move_draft_package(files, 42, "session")
    assert exc.value.status_code == 502
    assert client.deleted == client.copied


@pytest.mark.asyncio
async def test_submit_commit_failure_rolls_back_and_cleans_submitted_copy():
    from app.endpoints.v1 import candidate_documents as endpoint

    invite = SimpleNamespace(id=2, candidate_id=42, used_at=None)
    session = SimpleNamespace(id=3, session_id="session123", status="draft", submitted_at=None)
    file = SimpleNamespace(id=4, file_id="file123", document_type="passport",
                           s3_key="draft-key", filename="passport.jpg",
                           content_type="image/jpeg", size=100, status="uploaded")
    no_docs = MagicMock(); no_docs.scalar_one_or_none.return_value = None
    file_rows = MagicMock(); file_rows.scalars.return_value.all.return_value = [file]
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[no_docs, file_rows])
    db.flush = AsyncMock(); db.commit = AsyncMock(side_effect=RuntimeError("DB down")); db.rollback = AsyncMock()
    manifest = [{"key": "submitted-key"}]
    deleted = AsyncMock()
    with (
        patch.object(endpoint, "resolve_invite", AsyncMock(return_value=invite)),
        patch.object(endpoint, "resolve_upload_session", AsyncMock(return_value=session)),
        patch.object(endpoint, "move_draft_package", AsyncMock(return_value=manifest)),
        patch.object(endpoint, "delete_objects", deleted),
    ):
        with pytest.raises(RuntimeError):
            await endpoint.submit_candidate_document_upload_session(
                "invite", {"session_token": "secret"}, SimpleNamespace(headers={}), db
            )
    db.rollback.assert_awaited_once()
    deleted.assert_awaited_once_with(manifest)
