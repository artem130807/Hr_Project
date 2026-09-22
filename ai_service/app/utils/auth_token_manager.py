from datetime import datetime, timezone

import httpx


def _parse_expires(value: str) -> datetime:
    expires_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at


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
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.token_url,
                                         json={
                                             "client_id": self.client_id,
                                             "client_secret": self.client_secret
                                         })
            if response.status_code != 201:
                raise Exception(f"Failed to obtain token: {response.text}")
            data = response.json()
            self.token = data['access_token']
            self.token_expires = _parse_expires(data['expires'])
            return self.token
