"""Outbound proxy resolution (same as bot-service / opened-monitor-bot)."""
import os
from unittest.mock import patch


def test_proxy_disabled():
    with patch.dict(
        os.environ,
        {"TELEGRAM_PROXY_ENABLED": "false", "TELEGRAM_PROXY_URL": "", "TELEGRAM_PROXY": ""},
        clear=False,
    ):
        import importlib
        import app.config as conf

        importlib.reload(conf)
        assert conf.get_outbound_proxy_url() is None
        importlib.reload(conf)


def test_proxy_explicit_url():
    with patch.dict(
        os.environ,
        {
            "TELEGRAM_PROXY_ENABLED": "true",
            "TELEGRAM_PROXY_URL": "http://127.0.0.1:8080",
            "TELEGRAM_PROXY": "",
        },
        clear=False,
    ):
        import importlib
        import app.config as conf

        importlib.reload(conf)
        assert conf.get_outbound_proxy_url() == "http://127.0.0.1:8080"
        importlib.reload(conf)


def test_proxy_default_http_cluster():
    with patch.dict(
        os.environ,
        {
            "TELEGRAM_PROXY_ENABLED": "true",
            "TELEGRAM_PROXY_URL": "",
            "TELEGRAM_PROXY": "",
            "TELEGRAM_PROXY_TYPE": "http",
        },
        clear=False,
    ):
        import importlib
        import app.config as conf

        importlib.reload(conf)
        assert conf.get_outbound_proxy_url() == (
            "http://singbox-proxy.infrastructure.svc.cluster.local:8080"
        )
        importlib.reload(conf)


def test_proxy_default_socks5_cluster():
    with patch.dict(
        os.environ,
        {
            "TELEGRAM_PROXY_ENABLED": "true",
            "TELEGRAM_PROXY_URL": "",
            "TELEGRAM_PROXY": "",
            "TELEGRAM_PROXY_TYPE": "socks5",
        },
        clear=False,
    ):
        import importlib
        import app.config as conf

        importlib.reload(conf)
        assert conf.get_outbound_proxy_url() == (
            "socks5://singbox-proxy.infrastructure.svc.cluster.local:1080"
        )
        importlib.reload(conf)
