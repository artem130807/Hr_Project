from fastapi import APIRouter, BackgroundTasks, Request

from app.app_logging import logger
from app.dependencies import get_db_client, get_hh_client
from app.utils.negotiation import process_negotiation

router = APIRouter()


async def _process_negotiation(payload: dict) -> None:
    await process_negotiation(payload, await get_hh_client(), await get_db_client())


@router.post("/hh/negotiation")
async def post_negotiation_endpoint(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    logger.info(
        "Received HH webhook: type=%s",
        payload.get("event_type") or payload.get("type"),
    )
    background_tasks.add_task(_process_negotiation, payload)
    return {"status": "ok"}
