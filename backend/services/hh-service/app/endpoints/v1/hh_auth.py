from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse

import app.config as conf
from app.app_logging import logger
from app.clients.hh.simple_hh_client import SimpleHHClient
from app.dependencies import get_hh_client
from app.utils.auth import verify_external_access

from app.schemas.v1.auth import AuthPassed

router = APIRouter()


@router.get("/hh/auth")
async def hh_auth_callback(code: str,
                           state: str,
                           hh_client: SimpleHHClient = Depends(get_hh_client)):
    """
    Обрабатывает редирект от HH.ru:
    1. Принимает `code` и `state`
    2. Обменивает код на токен
    3. Сохраняет токены в БД
    4. Редиректит пользователя на фронт
    """

    logger.info(f"🔐 Получен HH OAuth callback, state={state}")

    data = {
        "grant_type": "authorization_code",
        "client_id": conf.HH_CLIENT_ID,
        "client_secret": conf.HH_CLIENT_SECRET,
        "redirect_uri": conf.HH_REDIRECT_URI,
        "code": code,
    }

    frontend_error = f"{conf.FRONTEND_URL}?error=hh_auth_failed"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post("https://hh.ru/oauth/token", data=data)
        if response.status_code != 200:
            logger.error(f"Ошибка получения токена HH: status={response.status_code}")
            return RedirectResponse(url=frontend_error)

        tokens = response.json()
        logger.info("✅ Токен HH успешно получен")

        hh_client.token_manager.access_token = tokens["access_token"]
        hh_client.token_manager.refresh_token = tokens["refresh_token"]
        hh_client.token_manager.token_expires = datetime.now(tz=timezone.utc) + timedelta(seconds=tokens["expires_in"])
        await hh_client.token_manager._save_tokens()

        # Успешная авторизация → редирект на фронт
        return RedirectResponse(url=conf.FRONTEND_URL)

    except Exception as e:
        logger.exception(f"Ошибка обмена кода HH: {e}")
        return RedirectResponse(url=frontend_error)


@router.get('/access_token', tags=['DEV'])
async def get_access_token(
    hh_client: SimpleHHClient = Depends(get_hh_client),
    _: dict = Depends(verify_external_access),
):
    """DEV: Получить текущий access_token (для отладки). Только в DEV и с авторизацией."""
    if conf.ENV.upper() != "DEV":
        raise HTTPException(status_code=404, detail="Not available in production")
    token = await hh_client.token_manager.get_token()
    return {"access_token": token}


@router.get('/auth-passed', response_model=AuthPassed)
async def get_auth_passed(
    hh: SimpleHHClient = Depends(get_hh_client)
):
    auth_passed = None
    if hh.token_manager.access_token is not None and hh.token_manager.refresh_token is not None:
        auth_passed = True
    else:
        auth_passed = False

    return {"auth_passed": auth_passed}