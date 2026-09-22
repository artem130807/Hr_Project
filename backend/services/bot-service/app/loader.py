from app.api.db_client import APIClient
from app.api.redis_client import RedisClient
from app.utils.auth_token_manager import TokenManager
from app.utils.test_manager import TestManager
from app.utils.negotiation_manager import NegotiationManager
from app.config import DB_SERVICE_URL, REDIS_SERVICE_URL, BOT_SERVICE_CLIENT_ID, BOT_SERVICE_CLIENT_SECRET
\

token_manager = TokenManager(
    token_url=f"{DB_SERVICE_URL}/token/service",
    client_id=BOT_SERVICE_CLIENT_ID,
    client_secret=BOT_SERVICE_CLIENT_SECRET
)

client = APIClient(DB_SERVICE_URL, 
                   token_manager,
                   headers_required=True)

redis_client = RedisClient(REDIS_SERVICE_URL)

test_manager = TestManager(redis_client=redis_client,
                           db_client=client)

negotiation_manager = NegotiationManager(
    redis_client=redis_client,
    db_client=client
)