"""Tests for Cloudflare scoped-token auth (osint #25).

CF_API_TOKEN (scoped, Bearer) is preferred; the legacy Global key
(CF_AUTH_EMAIL/CF_AUTH_KEY) is a transitional fallback only.
"""

import pytest

from ghostmode import cloudflare_monitor as cfm


CF_EMPTY = {"data": {"viewer": {"zones": []}}}


class _Resp:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return CF_EMPTY


def test_token_preferred_over_global_key(monkeypatch):
    monkeypatch.setenv("CF_API_TOKEN", "scoped-token-xyz")
    monkeypatch.setenv("CF_AUTH_EMAIL", "e@x.com")
    monkeypatch.setenv("CF_AUTH_KEY", "global-key")
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["headers"] = headers
        return _Resp()

    monkeypatch.setattr(cfm.requests, "post", fake_post)
    cfm.fetch_security_events(hours_back=1, zones={"z.test": "a" * 32})
    h = captured["headers"]
    assert h.get("Authorization") == "Bearer scoped-token-xyz"
    # the Global key must NOT be sent when a scoped token exists
    assert "X-Auth-Key" not in h
    assert "X-Auth-Email" not in h


def test_global_key_fallback_still_works(monkeypatch):
    monkeypatch.delenv("CF_API_TOKEN", raising=False)
    monkeypatch.setenv("CF_AUTH_EMAIL", "e@x.com")
    monkeypatch.setenv("CF_AUTH_KEY", "global-key")
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["headers"] = headers
        return _Resp()

    monkeypatch.setattr(cfm.requests, "post", fake_post)
    cfm.fetch_security_events(hours_back=1, zones={"z.test": "a" * 32})
    h = captured["headers"]
    assert h.get("X-Auth-Key") == "global-key"


def test_no_credentials_errors_cleanly(monkeypatch):
    for var in ("CF_API_TOKEN", "CF_AUTH_EMAIL", "CF_AUTH_KEY"):
        monkeypatch.delenv(var, raising=False)
    # also neutralize the `pass` fallback
    monkeypatch.setattr(cfm, "_get_cf_auth", lambda: ("", ""))
    out = cfm.fetch_security_events(hours_back=1, zones={"z.test": "a" * 32})
    assert out and "error" in out[0]
