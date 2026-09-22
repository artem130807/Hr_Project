import time
from app.app_logging import logger
from app.api.redis_client import RedisClient  
from app.api.db_client import APIClient as DBClient


class NegotiationManager:
    """
    Менеджер для управления списками откликов (negotiations):
      - хранит candidate_id в очереди Redis
      - при необходимости подгружает свежие отклики из БД
      - умеет выдавать следующего кандидата, считать количество и помечать прочитанным
    """

    def __init__(self, 
                 redis_client: RedisClient, 
                 db_client: DBClient,
                 prefix: str = "negotiations"):
        self.redis = redis_client
        self.db = db_client
        self.prefix = prefix

    # ---------------- Вспомогательные методы ----------------
    
    def _key(self, context_id: str | int = "all_vacancies") -> str:
        """Генерация ключа Redis для очереди откликов"""
        return f"{self.prefix}:{context_id}"
    
    async def _fill_from_db(self, context_id: str) -> list[int] | None:
        """Если в Redis пусто — подгрузить из БД"""
        negotiations = await self.db.get("/negotiations/unread")
        if not negotiations:
            return None
        
        ids = [n["candidate_id"] for n in negotiations]
        if ids:
            await self.redis.rpush(self._key(context_id), *ids)
        return ids
    
    async def _put_current(self, candidate_id: int, context_id: str = "all_vacancies") -> bool:
        result = await self.redis.set(f"{self._key(context_id)}:current", candidate_id)
        if not result:
            logger.error("Redis error getting current candidate")
        return result
    
    async def _get_current(self, context_id: str = "all_vacancies") -> str | None:
        candidate_id = await self.redis.get(f"{self._key(context_id)}:current")
        if candidate_id is None:
            logger.error("Redis error getting current candidate")
            return None
        return candidate_id

    # ---------------- Публичные методы ----------------
    
    async def count(self, context_id: str = "all_vacancies") -> int:
        """Подсчитать количество непрочитанных откликов"""
        count = await self.redis.llen(self._key(context_id))
        if count == 0:
            negotiations = await self._fill_from_db(context_id)
            count = len(negotiations) if negotiations else 0
        return count

    async def get_next(self, context_id: str = "all_vacancies") -> int | None:
        """
        Получить ID следующего кандидата из очереди.
        Если очередь пуста — подгрузить из БД.
        """
        candidate_id = await self.redis.lpop(self._key(context_id))
        if not candidate_id:
            negotiations = await self._fill_from_db(context_id)
            if not negotiations:
                return None
            candidate_id = await self.redis.lpop(self._key(context_id))
        await self._put_current(candidate_id, context_id)
        
        logger.info(f"Next candidate_id from negotiations: {candidate_id}")
        return int(candidate_id) if candidate_id else None

    async def read(self, candidate_id: int) -> bool:
        """
        Пометить отклик как прочитанный:
          - удалить из Redis
          - отправить POST в БД
        """
        response = await self.db.post(
            "/negotiation/read",
            json={"candidate_id": int(candidate_id)}
        )

        if not response:
            logger.error(f"Failed to mark candidate {candidate_id} as read in DB")
            return False

        logger.info(f"Candidate {candidate_id} marked as read")
        return True
    
    async def get_current(self, context_id: str = "all_vacancies"):
        candidate_id = await self._get_current(context_id)
        if not candidate_id:
            return None
        return candidate_id