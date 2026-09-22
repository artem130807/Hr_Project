from datetime import datetime, timezone

import httpx

from app.utils.utils import create_token
from app.config import SERVICE_TOKEN_EXPIRES


class TokenManager:
    def __init__(self, token_url: str, client_id: str, client_secret: str):
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expires = None

    async def get_token(self):
        if self.token and datetime.now(timezone.utc) < self.token_expires:
            return self.token
        
        self.token, self.token_expires = create_token(
            data={"sub": self.client_id, "type": "service"},
            expires_delta=SERVICE_TOKEN_EXPIRES)
        return self.token
