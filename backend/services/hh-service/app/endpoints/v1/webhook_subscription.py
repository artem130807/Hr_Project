from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies import get_hh_client
from app.clients.hh.simple_hh_client import SimpleHHClient

from app.schemas.v1.subscription import PostSubscriptionResponse, GetSubscriptionStatusResponse

from app.app_logging import logger
from app import config

router = APIRouter()


@router.post('/negotiations/subscribe', response_model=PostSubscriptionResponse)
async def subscribe_on_negotiations(
    subscribe: bool,
    hh: SimpleHHClient = Depends(get_hh_client)
):
    """
    Создаёт или удаляет подписку на вебхуки новых откликов от hh.ru.
    """
    webhook_url = f"{config.BASE_URL}/hh/negotiation"  # ← убедитесь, что BASE_URL задан правильно

    if subscribe:
        # Создаём подписку
        payload = {
            "url": webhook_url,
            "actions": [
                {
                    "type": "NEW_NEGOTIATION_VACANCY"
                }
            ]
        }
        try:
            result = await hh._request("POST", "/webhook/subscriptions", json=payload)
            return {"status": "subscribed", "subscription_id": result.get("id")}
        except HTTPException as e:
            logger.error(f"Failed to create webhook subscription: {e.detail}")
            raise HTTPException(status_code=500, detail="Не удалось создать подписку на отклики")
    else:
        # Удаляем все существующие подписки (или одну — если знаем ID)
        try:
            subs = await hh._request("GET", "/webhook/subscriptions")
            for sub in (subs or {}).get("items", []) if isinstance(subs, dict) else []:
                if sub.get("url") == webhook_url:
                    await hh._request("DELETE", f"/webhook/subscriptions/{sub['id']}")
            return {"status": "unsubscribed"}
        except HTTPException as e:
            logger.warning(f"Failed to unsubscribe: {e.detail}")
            return {"status": "unsubscribed", "warning": "Could not delete existing subscriptions"}
        

@router.get('/hh/subscription', response_model=GetSubscriptionStatusResponse)
async def get_hh_subscription(
    hh: SimpleHHClient = Depends(get_hh_client)
):
    """
    Возвращает true, если есть активная подписка на NEW_NEGOTIATION_VACANCY,
    и false — если такой подписки нет.
    """
    try:
        # Получаем список всех подписок
        subscriptions = await hh._request("GET", "/webhook/subscriptions")
    except HTTPException as e:
        # Если нет прав или другой ошибка — считаем, что подписки нет
        logger.warning(f"Failed to fetch HH webhook subscriptions: {e.detail}")
        return {"has_subscription": False}

    if not subscriptions or not isinstance(subscriptions, dict):
        return {"has_subscription": False}

    items = subscriptions.get("items") or []
    for sub in items:
        actions = sub.get("actions", []) or []
        for action in actions:
            if action.get("type") == "NEW_NEGOTIATION_VACANCY":
                return {"has_subscription": True}

    return {"has_subscription": False}