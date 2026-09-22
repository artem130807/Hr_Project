from __future__ import annotations

import threading

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import AI_DATABASE_URL
from app.db.models import Base

engine = create_async_engine(AI_DATABASE_URL, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

_thread_local = threading.local()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Session factory bound to the current thread's engine.

    asyncpg connections are event-loop-bound: the evaluate handler runs on a
    private loop inside a worker thread while the outbox relay runs on the
    main loop. A shared pooled engine mixes loops -> asyncpg InterfaceError
    ("another operation is in progress"). Per-thread engines with NullPool
    keep every connection on exactly one loop.
    """
    factory = getattr(_thread_local, "factory", None)
    if factory is None:
        _thread_local.engine = create_async_engine(
            AI_DATABASE_URL, future=True, poolclass=NullPool
        )
        factory = async_sessionmaker(
            _thread_local.engine, expire_on_commit=False, class_=AsyncSession
        )
        _thread_local.factory = factory
    return factory


async def init_outbox_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
