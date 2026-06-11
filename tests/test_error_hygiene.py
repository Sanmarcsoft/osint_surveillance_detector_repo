"""Tests for error-echo hygiene + db_bootstrap gating (osint #27).

Raw exception strings must never reach HTTP clients — psycopg2 errors carry
host/user/dbname, requests errors carry URLs. Clients get a generic message
with the exception class; the detail goes to server logs only.

db_bootstrap must not attempt a superuser connection from the app task
unless explicitly enabled.
"""

import sys
import types

import pytest
import requests

from ghostmode.sanitize import safe_error
from ghostmode import linear_proxy, rss_proxy
from ghostmode import cloudflare_monitor as cfm


SECRET = "password=SuperSecret123"


# --- safe_error primitive ---------------------------------------------------------

def test_safe_error_strips_detail():
    err = RuntimeError(f"connect failed {SECRET} at host=10.0.0.5")
    msg = safe_error(err, "Database")
    assert SECRET not in msg
    assert "10.0.0.5" not in msg
    assert "RuntimeError" in msg
    assert "Database" in msg


# --- module error paths must not echo exception detail -----------------------------

def _raiser(exc):
    def fake_post(*a, **kw):
        raise exc
    return fake_post


def test_linear_error_not_echoed(monkeypatch):
    linear_proxy._cache.clear()
    monkeypatch.setattr(linear_proxy.requests, "post",
                        _raiser(requests.RequestException(SECRET)))
    out = linear_proxy.fetch_issues("key", limit=5)
    assert out["ok"] is False
    assert SECRET not in str(out)


def test_rss_error_not_echoed(monkeypatch):
    monkeypatch.setattr(rss_proxy.requests, "get",
                        _raiser(requests.RequestException(SECRET)))
    out = rss_proxy.fetch_rss("https://example.com/feed.xml")
    assert out["ok"] is False
    assert SECRET not in str(out)


def test_cloudflare_error_not_echoed(monkeypatch):
    monkeypatch.setattr(cfm, "_get_cf_auth", lambda: ("e@x.com", "key"))
    monkeypatch.setattr(cfm.requests, "post",
                        _raiser(requests.RequestException(SECRET)))
    out = cfm.fetch_security_events(hours_back=1,
                                    zones={"good.test": "a" * 32})
    assert SECRET not in str(out)


# --- db_bootstrap gating ------------------------------------------------------------

def test_db_bootstrap_disabled_by_default(monkeypatch):
    """Without DB_BOOTSTRAP_ENABLED, the app task must never attempt a
    superuser connection."""
    from ghostmode import db_bootstrap

    monkeypatch.delenv("DB_BOOTSTRAP_ENABLED", raising=False)
    monkeypatch.setenv("DB_PASSWORD", "x")

    attempted = {"connect": False}
    fake_pg = types.ModuleType("psycopg2")

    def fake_connect(*a, **kw):
        attempted["connect"] = True
        raise AssertionError("superuser connect attempted while disabled")

    fake_pg.connect = fake_connect
    fake_ext = types.ModuleType("psycopg2.extensions")
    fake_ext.ISOLATION_LEVEL_AUTOCOMMIT = 0
    fake_pg.extensions = fake_ext
    monkeypatch.setitem(sys.modules, "psycopg2", fake_pg)
    monkeypatch.setitem(sys.modules, "psycopg2.extensions", fake_ext)

    assert db_bootstrap.bootstrap_db() is False
    assert attempted["connect"] is False
