import os
from unittest.mock import patch

os.environ.setdefault("EMPLOYER_ID", "1")
os.environ.setdefault("HH_CLIENT_ID", "cid")
os.environ.setdefault("HH_CLIENT_SECRET", "secret")
os.environ.setdefault("HH_SERVICE_CLIENT_ID", "hh-service")
os.environ.setdefault("HH_SERVICE_CLIENT_SECRET", "secret")
os.environ.setdefault("DB_SERVICE_URL", "http://localhost:8000/v1")
os.environ.setdefault("DB_SERVICE_INTERNAL", "http://localhost:8000")
os.environ.setdefault("DOMAIN", "localhost")
os.environ.setdefault("REDIS_SERVICE_URL", "redis://localhost:6379/0")
os.environ.setdefault("MOCK_HH", "true")
os.environ.setdefault("JWKS_URL", "http://localhost/.well-known/jwks.json")


def pytest_configure(config):
    # Routes construct dictionaries during import, before fixtures are active.
    # Tests must use the checked-in snapshot, not refresh HH or overwrite it.
    from app.clients.hh.hh_dictionaries import HHDictionaries
    cache_patch = patch.object(HHDictionaries, "_cache_expired", return_value=False)
    cache_patch.start()
    config.add_cleanup(cache_patch.stop)
