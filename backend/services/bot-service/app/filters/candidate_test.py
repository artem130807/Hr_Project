from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from app.loader import redis_client
from app.app_logging import logger

class OnTestFilter(BaseFilter):
    def __init__(self, on_test: bool = True):
        self.on_test = on_test
    async def __call__(self, update: Message | CallbackQuery) -> bool:
        user_id = str(update.from_user.id)
        key = f"{user_id}:on_test"
        exists = await redis_client.exists(key)
        if exists:
            return self.on_test
        else:
            return not self.on_test

    

