"""Tests for stored-XSS hardening + CSP (osint #24).

The dashboards render attacker-controlled log fields (paths, user agents,
usernames, hosts) into innerHTML. Every interpolation must go through esc().
These tests guard the known-dangerous sinks by asserting the raw (unescaped)
concatenation patterns never reappear, and that HTML responses carry CSP.
"""

import re
import time

import pytest
from starlette.testclient import TestClient

from ghostmode import alb_auth
from ghostmode.dashboard import build_dashboard
from ghostmode.nest_dashboard import build_nest_wrapper
from ghostmode.mcp_server import create_server


# --- render-escape regressions ---------------------------------------------------

# Raw interpolations of attacker-controlled fields that used to exist.
# If any of these reappear in the generated JS, the XSS is back.
FORBIDDEN_RAW_SINKS = [
    "+ (e.src_host||'?') +",
    "' user='+e.logdata.USERNAME",
    "' url='+e.logdata.URL",
    "+data.error+'</div>'",
    "+e.path+'</a>",
    "+e.host+'</span>",
    "+e.client_ip+'</a>",
    "+ m.ip + '</a>",
    "'+i+'</li>",
    "+ data.what_happened +",
    "+ data.risk +",
]


def test_dashboard_has_no_raw_event_sinks():
    html = build_dashboard()
    for sink in FORBIDDEN_RAW_SINKS:
        assert sink not in html, f"unescaped sink reappeared: {sink}"


def test_dashboard_defines_esc_helper():
    html = build_dashboard()
    assert "function esc(" in html
    # esc must escape quotes too (attribute contexts)
    assert "&#39;" in html and "&quot;" in html


def test_nest_wrapper_ticker_blocks_javascript_links():
    html = build_nest_wrapper()
    # the ticker must scheme-check links before building an <a href>
    assert re.search(r"https\?:.*test\(h\.link\)", html), \
        "ticker link scheme check missing"


# --- CSP headers ------------------------------------------------------------------

@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("GHOSTMODE_METRICS_TOKEN", "m")
    monkeypatch.setenv("GHOSTMODE_MCP_TOKEN", "t")
    monkeypatch.delenv("GHOSTMODE_DEV_NO_AUTH", raising=False)
    server = create_server(port=3200)
    app = server.http_app(transport="http")
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _verified(monkeypatch):
    claims = {"email": "agent@sanmarcsoft.com", "exp": int(time.time()) + 300}
    monkeypatch.setattr(alb_auth, "verify_alb_jwt", lambda token: claims)


@pytest.mark.parametrize("path", ["/", "/ghostmode/"])
def test_html_routes_carry_csp(client, monkeypatch, path):
    _verified(monkeypatch)
    r = client.get(path, headers={"x-amzn-oidc-data": "x.y.z"})
    assert r.status_code == 200
    csp = r.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert r.headers.get("x-content-type-options") == "nosniff"


def test_ops_route_carries_csp(client, monkeypatch):
    _verified(monkeypatch)
    import ghostmode.github_auth as ga
    monkeypatch.setattr(ga, "get_user_permissions",
                        lambda email, github_token=None, **kw: {
                            "int_team_member": True, "linear_enabled": True,
                            "ops_enabled": True})
    r = client.get("/ops/", headers={"x-amzn-oidc-data": "x.y.z"})
    assert r.status_code == 200
    assert "default-src 'self'" in r.headers.get("content-security-policy", "")
