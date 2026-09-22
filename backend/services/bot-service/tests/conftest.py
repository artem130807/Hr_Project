import os

os.environ.setdefault("DB_SERVICE_URL", "http://localhost:8000/v1")
os.environ.setdefault("DB_CLIENT_ID", "bot-service")
os.environ.setdefault("DB_CLIENT_SECRET", "secret")
os.environ.setdefault("BOT_TOKEN", "0:test")
os.environ.setdefault("REDIS_SERVICE_URL", "redis://localhost:6379/0")
