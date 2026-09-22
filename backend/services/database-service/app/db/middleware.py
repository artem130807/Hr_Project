from fastapi import Request
from app.config import AsyncSessionLocal
from app.app_logging import logger


async def db_middleware(request: Request, call_next):
    async with AsyncSessionLocal() as session:
        request.state.db = session
        try:
            response = await call_next(request)
            return response
        except Exception:
            # Откатываем незавершённую транзакцию, чтобы сессия не осталась
            # в сломанном состоянии; ошибку пробрасываем дальше (в FastAPI).
            try:
                await session.rollback()
            except Exception as rollback_err:
                logger.error(f"Rollback failed: {rollback_err}")
            raise


async def get_db(request: Request):
    return request.state.db
