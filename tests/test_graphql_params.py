"""Tests for GraphQL injection fixes (osint #26).

linear_proxy: user-controlled team/status/limit must travel as GraphQL
VARIABLES, never be interpolated into the query string.
cloudflare_monitor: zone tags must be validated as 32-hex zone IDs before
use; limits must be integers.
"""

import pytest

from ghostmode import linear_proxy
from ghostmode import cloudflare_monitor as cfm


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def clear_caches():
    linear_proxy._cache.clear()
    yield
    linear_proxy._cache.clear()


def _capture_post(captured, payload):
    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["body"] = json
        return _Resp(payload)
    return fake_post


# --- linear_proxy ---------------------------------------------------------------

LINEAR_EMPTY = {"data": {"issues": {"nodes": []}}}


def test_linear_team_travels_as_variable(monkeypatch):
    captured = {}
    monkeypatch.setattr(linear_proxy.requests, "post",
                        _capture_post(captured, LINEAR_EMPTY))
    evil = 'X" }) { viewer { organization { name } } } #'
    linear_proxy.fetch_issues("key", team=evil, status='S"inj', limit=5)
    body = captured["body"]
    # injection text must NOT appear in the query document
    assert evil not in body["query"]
    assert 'S"inj' not in body["query"]
    # it must arrive via variables instead
    assert body["variables"]["filter"]["team"]["key"]["eq"] == evil
    assert body["variables"]["filter"]["state"]["name"]["eq"] == 'S"inj'
    assert body["variables"]["first"] == 5


def test_linear_limit_clamped_to_int_range(monkeypatch):
    captured = {}
    monkeypatch.setattr(linear_proxy.requests, "post",
                        _capture_post(captured, LINEAR_EMPTY))
    linear_proxy.fetch_issues("key", limit=99999)
    assert captured["body"]["variables"]["first"] <= 50
    linear_proxy._cache.clear()
    linear_proxy.fetch_issues("key", limit=-3)
    assert captured["body"]["variables"]["first"] >= 1


def test_linear_no_filter_omits_filter_variable(monkeypatch):
    captured = {}
    monkeypatch.setattr(linear_proxy.requests, "post",
                        _capture_post(captured, LINEAR_EMPTY))
    result = linear_proxy.fetch_issues("key")
    assert result["ok"] is True
    assert "filter" not in captured["body"]["variables"]


# --- cloudflare_monitor ----------------------------------------------------------

CF_EMPTY = {"data": {"viewer": {"zones": []}}}


def test_cf_rejects_malformed_zone_ids(monkeypatch):
    """Zone tags are interpolated into the query filter; only 32-hex IDs
    may pass. A crafted 'zone id' must never reach the query document."""
    captured = {}
    monkeypatch.setattr(cfm.requests, "post", _capture_post(captured, CF_EMPTY))
    monkeypatch.setattr(cfm, "_get_cf_auth", lambda: ("e@x.com", "key"))
    evil = '"]}}) { viewer { accounts { id } } } #'
    events = cfm.fetch_security_events(
        hours_back=1, zones={"good.test": "a" * 32, "evil.test": evil})
    assert evil not in captured.get("body", {}).get("query", "")


def test_cf_accepts_valid_zone_ids(monkeypatch):
    captured = {}
    monkeypatch.setattr(cfm.requests, "post", _capture_post(captured, CF_EMPTY))
    monkeypatch.setattr(cfm, "_get_cf_auth", lambda: ("e@x.com", "key"))
    cfm.fetch_security_events(hours_back=1, zones={"good.test": "ab12" * 8})
    assert ("ab12" * 8) in captured["body"]["query"]


def test_cf_limit_is_integer(monkeypatch):
    captured = {}
    monkeypatch.setattr(cfm.requests, "post", _capture_post(captured, CF_EMPTY))
    monkeypatch.setattr(cfm, "_get_cf_auth", lambda: ("e@x.com", "key"))
    cfm.fetch_security_events(hours_back=1, limit_per_zone="50; drop",
                              zones={"good.test": "a" * 32})
    # non-int limit must not be interpolated verbatim
    assert "drop" not in captured["body"]["query"]
