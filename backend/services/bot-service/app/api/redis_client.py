import time
import redis.asyncio as aioredis
from app.app_logging import logger


class RedisClient:
    def __init__(self, url: str):
        self.url = url
        self.connection = None

    async def connect(self):
        if not self.connection:
            try:
                self.connection = await aioredis.from_url(
                    self.url,
                    decode_responses=True  # сразу строки вместо байтов
                )
                logger.info("Redis connection established")
            except Exception as e:
                logger.error(f"Redis connection error: {e}")
                raise

    async def close(self):
        if self.connection:
            await self.connection.close()
            self.connection = None
            logger.error("Redis connection closed")

    async def get(self, key: str) -> str | None:
        start = time.perf_counter()
        try:
            await self.connect()
            value = await self.connection.get(key)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"Redis GET request OK ({elapsed:.2f} ms): key: {key}, value: {value}")
            return value
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None

    async def set(self, key: str, value: str, expires: int | None = None) -> bool:
        start = time.perf_counter()
        try:
            await self.connect()
            await self.connection.set(key, value, ex=expires)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"Redis SET request OK ({elapsed:.2f} ms): key: {key}, value: {value}")
            return True
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        start = time.perf_counter()
        try:
            await self.connect()
            await self.connection.delete(key)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"Redis DELETE request OK ({elapsed:.2f} ms): key: {key}")
            return True
        except Exception as e:
            logger.info(f"Redis DELETE error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        start = time.perf_counter()
        try:
            await self.connect()
            exists = await self.connection.exists(key)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"Redis EXISTS request OK ({elapsed:.2f} ms): key: {key}")
            return bool(exists)
        except Exception as e:
            logger.error(f"Redis EXISTS error: {e}")
            return False

    async def lpush(self, key: str, *values) -> bool:
        start = time.perf_counter()
        try:
            await self.connect()
            await self.connection.lpush(key, *values)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"Redis LPUSH request OK ({elapsed:.2f} ms): key: {key}")
            return True
        except Exception as e:
            logger.error(f"Redis LPUSH error: {e}")
            return False

    async def rpush(self, key: str, *values) -> bool:
        start = time.perf_counter()
        try:
            await self.connect()
            await self.connection.rpush(key, *values)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"Redis RPUSH request OK ({elapsed:.2f} ms): key: {key}")
            return True
        except Exception as e:
            logger.error(f"Redis RPUSH error: {e}")
            return False

    async def lpop(self, key: str) -> str | None:
        start = time.perf_counter()
        try:
            await self.connect()
            value = await self.connection.lpop(key)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"Redis LPOP request OK ({elapsed:.2f} ms): key: {key}, value: {value}")
            return value
        except Exception as e:
            logger.error(f"Redis LPOP error: {e}")
            return None

    async def rpop(self, key: str) -> str | None:
        start = time.perf_counter()
        try:
            await self.connect()
            value = await self.connection.rpop(key)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"Redis RPOP request OK ({elapsed:.2f} ms): key: {key}, value: {value}")
            return value
        except Exception as e:
            logger.error(f"Redis RPOP error: {e}")
            return None

    async def llen(self, key: str) -> int:
        """Получить длину списка"""
        start = time.perf_counter()
        try:
            await self.connect()
            length = await self.connection.llen(key)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"Redis LLEN request OK ({elapsed:.2f} ms): key: {key}, len: {length}")
            return int(length)
        except Exception as e:
            logger.error(f"Redis LLEN error: {e}")
            return 0

    async def lrem(self, key: str, value: str, count: int = 0) -> int:
        """Удалить элементы из списка"""
        start = time.perf_counter()
        try:
            await self.connect()
            removed = await self.connection.lrem(key, count, value)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"Redis LREM request OK ({elapsed:.2f} ms): key: {key}, removed: {removed}")
            return int(removed)
        except Exception as e:
            logger.error(f"Redis LREM error: {e}")
            return 0

    async def lrange(self, key: str, start_index: int = 0, end_index: int = -1) -> list[str]:
        """Получить диапазон элементов из списка"""
        start = time.perf_counter()
        try:
            await self.connect()
            values = await self.connection.lrange(key, start_index, end_index)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"Redis LRANGE request OK ({elapsed:.2f} ms): key: {key}, count: {len(values)}")
            return values
        except Exception as e:
            logger.error(f"Redis LRANGE error: {e}")
            return []