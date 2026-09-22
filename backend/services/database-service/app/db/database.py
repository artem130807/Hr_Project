from typing import AsyncGenerator, Annotated
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import mapped_column, Mapped, DeclarativeBase
from sqlalchemy import ARRAY, String, DateTime, func, Integer, JSON

from app.config import AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as Session:
        try:
            yield Session
        finally:
            await Session.aclose()


class Base(DeclarativeBase):
    pass


# Универсальные типы для переиспользования
int_pk = Annotated[int, mapped_column(Integer, primary_key=True, autoincrement=True, index=True)]
str_uniq = Annotated[str, mapped_column(String, unique=True, nullable=False, index=True)]
str_list = Annotated[list[str], mapped_column(JSON)]


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )