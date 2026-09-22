"""Persistence for the T2 PBX OAuth token singleton (table t2_oauth_tokens)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.db.v1.models import T2OAuthToken

_SINGLETON_ID = 1


class T2OAuthTokenRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get(self) -> Optional[T2OAuthToken]:
        return await self._db.get(T2OAuthToken, _SINGLETON_ID)

    async def upsert(self, payload: dict) -> T2OAuthToken:
        row = await self.get()
        if row is None:
            row = T2OAuthToken(
                id=_SINGLETON_ID,
                payload=payload,
                version=T2OAuthToken.INITIAL_VERSION,
            )
            self._db.add(row)
        else:
            row.payload = payload
            flag_modified(row, "payload")
            row.bump_version()
        await self._db.commit()
        await self._db.refresh(row)
        return row

    async def delete(self) -> bool:
        row = await self.get()
        if row is None:
            return False
        await self._db.delete(row)
        await self._db.commit()
        return True
