from app.api.endpoints import Endpoints
from app.loader import client
from app.api.schemas import UpdateProgress

async def pass_checkpoint(telegram_id: str, field: str):
    payload = {field: True}
    data = UpdateProgress(**payload)
    response = await client.patch(Endpoints.patch_user_progress, telegram_id=telegram_id, json=data.model_dump(exclude_unset=True))
    return response


