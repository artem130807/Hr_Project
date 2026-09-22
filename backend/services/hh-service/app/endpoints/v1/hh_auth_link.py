from fastapi import APIRouter

import app.config as conf


router = APIRouter()
    

@router.get('/auth/link')
async def get_auth_link_endpoint() -> str:
    """
    Возвращает ссылку для авторизации на hh.ru
    """
    auth_url = (
        f"https://hh.ru/oauth/authorize?"
        f"response_type=code&"
        f"client_id={conf.HH_CLIENT_ID}&"
        f"redirect_uri={conf.HH_REDIRECT_URI}&"
        f"state=some_unique_state_value"  # Можно генерировать уникальное значение для безопасности
    )
    return auth_url