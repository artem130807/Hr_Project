"""
Pytest bootstrap: set env before importing app modules that construct OpenAI client.
"""
import os
import sys
from unittest.mock import MagicMock

class BadRequestError(Exception):
    def __init__(self, message="", response=None, body=None):
        super().__init__(message)
        self.response = response
        self.body = body
        self.status_code = getattr(response, "status_code", 400)


if "openai" not in sys.modules:
    _openai = MagicMock()
    _openai.AsyncOpenAI = MagicMock
    _openai.BadRequestError = BadRequestError
    sys.modules["openai"] = _openai

# Must run before app.loader import
os.environ.setdefault("OPENAI_API_TOKEN", "test-openai-key")
os.environ.setdefault("TELEGRAM_PROXY_ENABLED", "false")
os.environ.setdefault("CLIENT_ID", "ai-service")
os.environ.setdefault("CLIENT_SECRET", "test-secret")
os.environ.setdefault("DB_SERVICE_URL", "http://localhost:8000/v1")
os.environ.setdefault("JWKS_URL", "http://localhost/.well-known/jwks.json")
os.environ.setdefault("DOMAIN", "localhost")
