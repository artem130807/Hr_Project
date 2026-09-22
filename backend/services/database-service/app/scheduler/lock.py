from redis.asyncio import Redis

from app.config import REDIS_URL
from app.app_logging import logger

redis = Redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None


class DistributedLock:
    """
    Redis NX lock across replicas.
    Fail-open if Redis is missing/unavailable so background jobs still run.
    """

    def __init__(self, key: str, ttl: int = 3600):
        self.key = key
        self.ttl = ttl
        self.acquired = False
        self._redis_ok = True

    async def __aenter__(self):
        if redis is None:
            logger.warning(f"Redis URL not set; running job '{self.key}' without lock")
            self._redis_ok = False
            return True
        try:
            self.acquired = bool(await redis.set(self.key, "1", ex=self.ttl, nx=True))
            self._redis_ok = True
            return self.acquired
        except Exception as exc:
            self._redis_ok = False
            self.acquired = False
            logger.warning(f"Redis lock unavailable ({exc}); running '{self.key}' without lock")
            return True

    async def __aexit__(self, exc_type, exc, tb):
        if not self._redis_ok or not self.acquired or redis is None:
            return
        try:
            await redis.delete(self.key)
        except Exception as exc:
            logger.warning(f"Failed to release Redis lock {self.key}: {exc}")
