import asyncio

import app.config as conf
from app.client.db_client import APICLient as DBClient
from app.utils.auth_token_manager import TokenManager


_db_client: DBClient | None = None


async def get_db_client() -> DBClient:
    global _db_client
    if _db_client is None:
        token_manager = TokenManager(
            token_url=conf.TOKEN_URL,
            client_id=conf.CLIENT_ID,
            client_secret=conf.CLIENT_SECRET
        )
        _db_client = DBClient(
            base_url=conf.DB_SERVICE_URL,
            token_manager=token_manager
        )
    return _db_client