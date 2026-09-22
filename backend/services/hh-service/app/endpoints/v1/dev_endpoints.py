from fastapi import APIRouter, HTTPException, Depends

from app.app_logging import logger
from app.clients.hh.simple_hh_client import SimpleHHClient
from app.clients.db_client import APICLient
from app.dependencies import get_hh_client, get_ai_client, get_db_client


router = APIRouter()
    

@router.get('/access_token', tags=['DEV'])
async def get_access_token(hh_client: SimpleHHClient = Depends(get_hh_client)):
    """DEV: Получить текущий access_token (для отладки)."""
    token = await hh_client.token_manager.get_token()
    return {"access_token": token}


@router.post('/autosearch/run', tags=['DEV'])
async def run_autosearch_job(
):
    """DEV: Запустить задачу автопоиска вручную (для отладки)."""
    from app.scheduler.scheduler import safe_autosearch

    await safe_autosearch()
    return {"status": "Autosearch job executed"}
