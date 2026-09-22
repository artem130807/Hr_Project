import os

# Minimal env so app.config / engine import does not crash in unit tests.
os.environ.setdefault("POSTGRES_DB", "testdb")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_SCHEMA", "public")
os.environ.setdefault("DB_SERVICE_URL", "http://localhost:8000")
os.environ.setdefault("DB_CLIENT_ID", "db-service")
os.environ.setdefault("DB_CLIENT_SECRET", "secret")
os.environ.setdefault("SUPERUSER_NAME", "admin")
os.environ.setdefault("SUPERUSER_PASSWORD", "admin")
os.environ.setdefault("ACCESS_TOKEN_EXPIRES", "90")
os.environ.setdefault("REFRESH_TOKEN_EXPIRES", "20160")
os.environ.setdefault("SERVICE_TOKEN_EXPIRES", "4320")
# Keep unit tests on local bcrypt auth unless a test enables ERP proxy explicitly.
os.environ.setdefault("ERP_AUTH_ENABLED", "false")
os.environ.setdefault("ERP_BASE", "")
os.environ.setdefault("ERP_JWT_SECRET", "test-erp-jwt-secret")
