import asyncio
from aiogram.types import FSInputFile
from app.api.redis_client import RedisClient
from app.app_logging import logger

OFFICE_VIDEO_PATH = "./app/media/office_review.MOV"
OFFICE_VIDEO_KEY = "office_review:file_id"
OFFICE_VIDEO_LOCK_KEY = "office_review:file_id:lock"


async def get_office_video(redis: RedisClient):
    """
    Возвращает file_id видео из Redis или FSInputFile, если кэша нет.
    Использует блокировку, чтобы избежать одновременной загрузки.
    """
    file_id = await redis.get(OFFICE_VIDEO_KEY)
    if file_id:
        return file_id.decode() if isinstance(file_id, bytes) else file_id

    if await redis.exists(OFFICE_VIDEO_LOCK_KEY):
        logger.info("Waiting for office video upload to finish...")
        await asyncio.sleep(5)
        file_id = await redis.get(OFFICE_VIDEO_KEY)
        if file_id:
            return file_id.decode() if isinstance(file_id, bytes) else file_id

    await redis.set(OFFICE_VIDEO_LOCK_KEY, "1", expires=120)

    return FSInputFile(OFFICE_VIDEO_PATH)


async def cache_office_video_file_id(redis: RedisClient, message):
    """Кэширует file_id после первого успешного отправления видео."""
    try:
        if not message.video:
            logger.warning("No video found in message to cache.")
            return

        file_id = message.video.file_id
        await redis.set(OFFICE_VIDEO_KEY, file_id)
        await redis.delete(OFFICE_VIDEO_LOCK_KEY)
        logger.info(f"Office video file_id cached successfully: {file_id}")
    except Exception as e:
        logger.error(f"Failed to cache office video file_id: {e}")
