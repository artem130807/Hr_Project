import asyncio
from aiogram.types import FSInputFile
from app.api.redis_client import RedisClient
from app.app_logging import logger

LOGO_PATH = "./app/img/alt_logo.png"
LOGO_KEY = "logo:file_id"
LOGO_LOCK_KEY = "logo:file_id:lock"


async def get_logo_file(redis: RedisClient):
    """
    Возвращает file_id логотипа из Redis или FSInputFile, если кэша нет.
    Использует блокировку, чтобы избежать одновременной загрузки.
    """
    # если уже кэшировано
    file_id = await redis.get(LOGO_KEY)
    if file_id:
        return file_id.decode() if isinstance(file_id, bytes) else file_id

    # если кто-то уже загружает — ждём и пробуем снова
    if await redis.exists(LOGO_LOCK_KEY):
        logger.info("Waiting for logo upload to finish...")
        await asyncio.sleep(2)
        file_id = await redis.get(LOGO_KEY)
        if file_id:
            return file_id.decode() if isinstance(file_id, bytes) else file_id

    # ставим лок, чтобы не дублировать отправку
    await redis.set(LOGO_LOCK_KEY, "1", expires=10)

    # возвращаем путь к файлу — бот сам отправит, и потом закэшируем file_id
    return FSInputFile(LOGO_PATH)


async def cache_logo_file_id(redis: RedisClient, message):
    """Кэширует file_id после первого успешного отправления фото."""
    try:
        if not message.photo:
            logger.warning("No photo found in message to cache.")
            return

        file_id = message.photo[-1].file_id
        await redis.set(LOGO_KEY, file_id)
        await redis.delete(LOGO_LOCK_KEY)
        logger.info(f"Logo file_id cached successfully: {file_id}")
    except Exception as e:
        logger.error(f"⚠️ Failed to cache logo file_id: {e}")