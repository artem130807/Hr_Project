from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adaptation.access import principal_from_claims, require_hr
from app.config import S3_BUCKET
from app.db.middleware import get_db
from app.db.v1.enums import CandidateStatus
from app.db.v1.models import (
    Candidate, CandidateDocs, CandidateDocumentInvite,
    CandidateDocumentUploadFile, CandidateDocumentUploadSession,
)
from app.services.candidate_documents import (
    MAX_FILES,
    MAX_TOTAL_BYTES,
    PreparedUpload,
    build_public_url,
    create_invite,
    delete_objects,
    create_upload_session,
    move_draft_package,
    prepare_uploads,
    presigned_manifest,
    resolve_invite,
    resolve_upload_session,
    upload_draft_file,
)
from app.utils.audit import write_audit
from app.utils.candidate_funnel import set_candidate_vacancy_status
from app.utils.utils import get_current_user

router = APIRouter()
public_router = APIRouter()


def _candidate_payload(candidate: Candidate) -> dict:
    return {"id": candidate.id, "full_name": candidate.full_name or "Кандидат"}


@router.post("/candidates/{candidate_id}/documents/invite")
async def generate_candidate_documents_invite(candidate_id: int, request: Request, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    principal = principal_from_claims(claims)
    require_hr(principal)
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Кандидат не найден")
    invite, token = await create_invite(db, candidate, actor_id=principal.user_id)
    await write_audit(db, action="candidate.documents.invite", entity_type="candidate", entity_id=candidate.id, details=f"invite_id={invite.id}")
    result = {"candidate_id": candidate.id, "url": build_public_url(request, token), "expires_at": invite.expires_at}
    await db.commit()
    return result


@public_router.get("/public/candidate-documents/{token}")
async def get_candidate_documents_form(token: str, response: Response, db: AsyncSession = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    invite = await resolve_invite(db, token)
    candidate = await db.get(Candidate, invite.candidate_id)
    if not candidate:
        raise HTTPException(404, "Кандидат не найден")
    return {"candidate": _candidate_payload(candidate), "expires_at": invite.expires_at}


async def _draft_payload(db: AsyncSession, session: CandidateDocumentUploadSession, token: str | None = None) -> dict:
    files = list((await db.execute(
        select(CandidateDocumentUploadFile)
        .where(CandidateDocumentUploadFile.session_id == session.id)
        .order_by(CandidateDocumentUploadFile.id)
    )).scalars().all())
    manifest = await presigned_manifest([
        {"key": row.s3_key, "kind": row.document_type, "filename": row.filename,
         "content_type": row.content_type, "size": row.size, "file_id": row.file_id}
        for row in files
    ])
    payload = {"expires_at": session.expires_at, "files": [
        {field: item[field] for field in ("file_id", "kind", "filename", "content_type", "size", "url")}
        for item in manifest
    ]}
    if token:
        payload["session_token"] = token
    return payload


@public_router.post("/public/candidate-documents/{token}/upload-sessions")
async def open_candidate_documents_upload_session(
    token: str, data: dict, response: Response, db: AsyncSession = Depends(get_db)
):
    response.headers["Cache-Control"] = "no-store"
    invite = await resolve_invite(db, token)
    supplied = str((data or {}).get("session_token") or "").strip()
    if supplied:
        session = await resolve_upload_session(db, invite, supplied)
        return await _draft_payload(db, session)
    session, session_token = await create_upload_session(db, invite)
    payload = await _draft_payload(db, session, session_token)
    await db.commit()
    return payload


@public_router.post("/public/candidate-documents/{token}/upload-sessions/files", status_code=201)
async def upload_candidate_document_draft_file(
    token: str,
    session_token: str = Form(...),
    kind: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    invite = await resolve_invite(db, token)
    session = await resolve_upload_session(db, invite, session_token, lock=True)
    rows = list((await db.execute(
        select(CandidateDocumentUploadFile).where(CandidateDocumentUploadFile.session_id == session.id)
    )).scalars().all())
    if len(rows) >= MAX_FILES:
        raise HTTPException(422, f"Можно приложить не более {MAX_FILES} файлов")
    file_id = uuid.uuid4().hex
    prepared = (await prepare_uploads([file], [kind], ""))[0]
    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}[prepared.content_type]
    key = f"candidate-docs/{invite.candidate_id}/draft/{session.session_id}/{prepared.kind}/{file_id}{suffix}"
    prepared = PreparedUpload(key, prepared.kind, prepared.filename, prepared.content_type, prepared.data)
    if sum(row.size for row in rows) + len(prepared.data) > MAX_TOTAL_BYTES:
        raise HTTPException(413, "Общий размер пакета не должен превышать 50 МБ")
    manifest = await upload_draft_file(prepared)
    row = CandidateDocumentUploadFile(
        file_id=file_id, session_id=session.id, document_type=prepared.kind, s3_key=key,
        filename=prepared.filename, content_type=prepared.content_type, size=len(prepared.data), status="uploaded",
    )
    db.add(row)
    try:
        # Signing is fallible: finish it before committing persistent metadata.
        url = (await presigned_manifest([{**manifest, "file_id": file_id}]))[0]["url"]
        await db.commit()
    except Exception:
        await db.rollback()
        await delete_objects([manifest])
        raise
    return {"file_id": file_id, "kind": prepared.kind, "filename": prepared.filename,
            "content_type": prepared.content_type, "size": len(prepared.data), "url": url}


@public_router.delete("/public/candidate-documents/{token}/upload-sessions/files/{file_id}")
async def delete_candidate_document_draft_file(
    token: str, file_id: str,
    session_token: str = Header(..., alias="X-Upload-Session"),
    db: AsyncSession = Depends(get_db),
):
    invite = await resolve_invite(db, token)
    session = await resolve_upload_session(db, invite, session_token, lock=True)
    row = (await db.execute(select(CandidateDocumentUploadFile).where(
        CandidateDocumentUploadFile.file_id == file_id,
        CandidateDocumentUploadFile.session_id == session.id,
    ))).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Документ не найден")
    manifest = [{"key": row.s3_key}]
    await db.delete(row)
    await db.commit()
    await delete_objects(manifest)
    return {"deleted": True}


@public_router.post("/public/candidate-documents/{token}/upload-sessions/submit", status_code=201)
async def submit_candidate_document_upload_session(
    token: str, data: dict, response: Response, db: AsyncSession = Depends(get_db)
):
    response.headers["Cache-Control"] = "no-store"
    invite = await resolve_invite(db, token, lock=True, allow_used=True)
    session_token = str((data or {}).get("session_token") or "").strip()
    session = await resolve_upload_session(db, invite, session_token, lock=True, allow_submitted=True)
    if session.status == "submitted":
        # A retry with the same two credentials returns the durable receipt;
        # it must never recopy S3 objects or create another package.
        row = (await db.execute(select(CandidateDocs).where(
            CandidateDocs.candidate_id == invite.candidate_id,
        ))).scalar_one_or_none()
        if not row:
            raise HTTPException(409, "Не найден отправленный пакет документов")
        return {"id": row.id, "status": row.status, "submitted_at": row.submitted_at}
    if invite.used_at:
        raise HTTPException(409, "Пакет документов уже отправлен из другой сессии")
    if (await db.execute(select(CandidateDocs.id).where(CandidateDocs.candidate_id == invite.candidate_id))).scalar_one_or_none():
        raise HTTPException(409, "Пакет документов уже отправлен")
    files = list((await db.execute(select(CandidateDocumentUploadFile).where(
        CandidateDocumentUploadFile.session_id == session.id
    ).order_by(CandidateDocumentUploadFile.id))).scalars().all())
    if not files:
        raise HTTPException(422, "Добавьте хотя бы один документ")
    manifest = await move_draft_package(files, invite.candidate_id, session.session_id)
    now = datetime.now(timezone.utc)
    prefix = f"candidate-docs/{invite.candidate_id}/submitted/{session.session_id}/"
    row = CandidateDocs(candidate_id=invite.candidate_id, s3_prefix=f"s3://{S3_BUCKET}/{prefix}",
                        manifest=manifest, submitted_at=now, status="submitted")
    db.add(row)
    session.status = "submitted"
    session.submitted_at = now
    invite.used_at = now
    for file_row in files:
        file_row.status = "submitted"
    draft_manifest = [{"key": item.s3_key} for item in files]
    try:
        await db.flush()
        result = {"id": row.id, "status": row.status, "submitted_at": row.submitted_at}
        await db.commit()
    except Exception:
        await db.rollback()
        await delete_objects(manifest)
        raise
    await delete_objects(draft_manifest)
    return result


@public_router.post("/public/candidate-documents/{token}", status_code=201)
async def submit_candidate_documents(
    token: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Legacy single-request uploads are disabled so documents cannot bypass durable drafts."""
    response.headers["Cache-Control"] = "no-store"
    raise HTTPException(410, "Обновите страницу: документы теперь загружаются по одному в защищённый черновик")


@router.get("/candidate-documents")
async def list_candidate_documents(db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    rows = list((await db.execute(
        select(CandidateDocs).options(selectinload(CandidateDocs.candidate)).order_by(CandidateDocs.submitted_at.desc())
    )).scalars().all())
    return [{
        "id": row.id, "candidate": _candidate_payload(row.candidate), "s3_prefix": row.s3_prefix,
        "status": row.status, "submitted_at": row.submitted_at, "reviewed_at": row.reviewed_at,
        "documents": await presigned_manifest(row.manifest),
    } for row in rows]


@router.get("/candidate-documents/{docs_id}")
async def get_candidate_documents(docs_id: int, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    require_hr(principal_from_claims(claims))
    row = (await db.execute(select(CandidateDocs).options(selectinload(CandidateDocs.candidate)).where(CandidateDocs.id == docs_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Пакет документов не найден")
    return {"id": row.id, "candidate": _candidate_payload(row.candidate), "s3_prefix": row.s3_prefix, "status": row.status, "submitted_at": row.submitted_at, "reviewed_at": row.reviewed_at, "documents": await presigned_manifest(row.manifest)}


@router.post("/candidate-documents/{docs_id}/complete")
async def complete_candidate_documents(docs_id: int, db: AsyncSession = Depends(get_db), claims=Depends(get_current_user)):
    principal = principal_from_claims(claims)
    require_hr(principal)
    row = await db.get(CandidateDocs, docs_id, with_for_update=True)
    if not row:
        raise HTTPException(404, "Пакет документов не найден")
    if row.status != "complete":
        row.status = "complete"
        row.reviewed_at = datetime.now(timezone.utc)
        row.reviewed_by = principal.user_id
        status_updated = await set_candidate_vacancy_status(db, row.candidate_id, CandidateStatus.full_documents)
        if not status_updated:
            raise HTTPException(409, "У кандидата нет связанной вакансии для обновления статуса")
        await write_audit(db, action="candidate.documents.complete", entity_type="candidate_docs", entity_id=row.id, details=f"candidate_id={row.candidate_id}")
        result = {"id": row.id, "status": row.status, "reviewed_at": row.reviewed_at}
        await db.commit()
        return result
    return {"id": row.id, "status": row.status, "reviewed_at": row.reviewed_at}
