from app.config import DB_SERVICE_URL, BOT_SERVICE_CLIENT_ID, BOT_SERVICE_CLIENT_SECRET
from app.api.db_client import APIClient as DBClient
from app.utils.auth_token_manager import TokenManager


_db_client: DBClient | None = None


async def get_db_client() -> DBClient:
    global _db_client
    if _db_client is None:
        token_manager = TokenManager(
            token_url=f"{DB_SERVICE_URL}/token/service",
            client_id=BOT_SERVICE_CLIENT_ID,
            client_secret=BOT_SERVICE_CLIENT_SECRET
        )
        _db_client = DBClient(
                    DB_SERVICE_URL, 
                   token_manager,
                   headers_required=True
        )
    return _db_client