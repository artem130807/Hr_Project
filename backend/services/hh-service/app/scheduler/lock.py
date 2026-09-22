import asyncio
from redis.asyncio import Redis
from app.config import REDIS_URL

redis = Redis.from_url(REDIS_URL, decode_responses=True)

class DistributedLock:
    def __init__(self, key: str, ttl: int = 3600):
        self.key = key
        self.ttl = ttl
        self.acquired = False

    async def __aenter__(self):
        # пытаемся взять lock
        self.acquired = await redis.set(
            self.key,
            "1",
            ex=self.ttl,
            nx=True  # set only if not exists
        )
        return self.acquired

    async def __aexit__(self, exc_type, exc, tb):
        if self.acquired:
            await redis.delete(self.key)