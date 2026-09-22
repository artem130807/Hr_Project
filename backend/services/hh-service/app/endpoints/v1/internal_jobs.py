"""Internal job triggers for the single HR Huey worker (database-service)."""
from fastapi import APIRouter, Depends

from app.scheduler.scheduler import (
    safe_auto_reject_filtered,
    safe_autosearch,
    safe_token_keepalive,
)
from app.utils.internal_auth import verify_internal_token

router = APIRouter(
    prefix="/internal/jobs",
    tags=["Internal Jobs"],
    dependencies=[Depends(verify_internal_token)],
)


@router.post("/autosearch")
async def run_autosearch_job():
    await safe_autosearch()
    return {"status": "ok"}


@router.post("/auto-reject")
async def run_auto_reject_job():
    await safe_auto_reject_filtered()
    return {"status": "ok"}


@router.post("/token-keepalive")
async def run_token_keepalive_job():
    await safe_token_keepalive()
    return {"status": "ok"}
