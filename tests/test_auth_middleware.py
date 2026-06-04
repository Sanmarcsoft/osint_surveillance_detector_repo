"""Tests for fail-closed auth enforcement on every route + MCP endpoint
(osint #22 + #28).

Policy under test:
- /health is the ONLY anonymous route (ALB target-group health checks).
- /metrics requires `Authorization: Bearer $GHOSTMODE_METRICS_TOKEN`.
- /mcp requires `Authorization: Bearer $GHOSTMODE_MCP_TOKEN`.
- Everything else requires a VERIFIED x-amzn-oidc-data identity (signature
  checked — not merely decoded).
- The ?email= identity fallback is gone.
- GHOSTMODE_DEV_NO_AUTH=1 is an explicit local-dev opt-out (default closed).
"""

import time

import pytest
from starlette.testclient import TestClient

from ghostmode import alb_auth
from ghostmode.mcp_server import create_server


VALID_CLAIMS = {"email": "agent@sanmarcsoft.com", "sub": "abc",
                "exp": int(time.time()) + 300}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("GHOSTMODE_METRICS_TOKEN", "metrics-secret")
    monkeypatch.setenv("GHOSTMODE_MCP_TOKEN", "mcp-secret")
    monkeypatch.delenv("GHOSTMODE_DEV_NO_AUTH", raising=False)
    server = create_server(port=3200)
    app = server.http_app(transport="http")
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _stub_verify(monkeypatch, result):
    monkeypatch.setattr(alb_auth, "verify_alb_jwt", lambda token: result)


# --- anonymous allowlist -------------------------------------------------------

def test_health_is_anonymous(client):
    # 200/503 reflect real service health; the point is it is never 401 —
    # ALB target-group health checks carry no OIDC identity.
    assert client.get("/health").status_code != 401


# --- dashboards / APIs fail closed --------------------------------------------

@pytest.mark.parametrize("path", [
    "/", "/ops/", "/ghostmode/", "/api/logs", "/api/surveillance",
    "/api/correlated", "/api/threat-map", "/api/ip-events",
    "/api/action-intel", "/api/rss", "/api/linear/issues",
    "/api/config-validate", "/api/store-stats", "/api/auth/permissions",
])
def test_routes_reject_anonymous(client, path):
    r = client.get(path)
    assert r.status_code == 401, f"{path} must fail closed, got {r.status_code}"


def test_alert_test_post_rejects_anonymous(client):
    assert client.post("/api/alert-test").status_code == 401


def test_unverified_oidc_header_rejected(client, monkeypatch):
    """A decodable-but-unverified JWT must NOT grant access."""
    _stub_verify(monkeypatch, None)  # signature verification fails
    r = client.get("/api/logs", headers={"x-amzn-oidc-data": "x.y.z"})
    assert r.status_code == 401


def test_verified_oidc_header_grants_access(client, monkeypatch):
    _stub_verify(monkeypatch, dict(VALID_CLAIMS))
    r = client.get("/api/logs", headers={"x-amzn-oidc-data": "x.y.z"})
    assert r.status_code == 200


# --- ?email= fallback is dead ---------------------------------------------------

def test_email_query_param_fallback_removed(client):
    r = client.get("/api/auth/permissions?email=attacker@evil.example")
    assert r.status_code == 401


def test_permissions_uses_verified_identity_only(client, monkeypatch):
    _stub_verify(monkeypatch, dict(VALID_CLAIMS))
    captured = {}

    def fake_perms(email, github_token=None, **kw):
        captured["email"] = email
        return {"int_team_member": False, "linear_enabled": False,
                "ops_enabled": False}

    import ghostmode.github_auth as ga
    monkeypatch.setattr(ga, "get_user_permissions", fake_perms)
    r = client.get(
        "/api/auth/permissions?email=attacker@evil.example",
        headers={"x-amzn-oidc-data": "x.y.z"},
    )
    assert r.status_code == 200
    assert captured["email"] == "agent@sanmarcsoft.com"  # never the query param


# --- /metrics (#28) -------------------------------------------------------------

def test_metrics_rejects_anonymous(client):
    assert client.get("/metrics").status_code == 401


def test_metrics_rejects_wrong_token(client):
    r = client.get("/metrics", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_metrics_accepts_token(client):
    r = client.get("/metrics", headers={"Authorization": "Bearer metrics-secret"})
    assert r.status_code == 200


def test_metrics_fails_closed_when_token_unset(monkeypatch):
    monkeypatch.delenv("GHOSTMODE_METRICS_TOKEN", raising=False)
    monkeypatch.setenv("GHOSTMODE_MCP_TOKEN", "mcp-secret")
    monkeypatch.delenv("GHOSTMODE_DEV_NO_AUTH", raising=False)
    server = create_server(port=3200)
    app = server.http_app(transport="http")
    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.get("/metrics").status_code == 401
        assert c.get("/metrics",
                     headers={"Authorization": "Bearer "}).status_code == 401


# --- /mcp (#28) ------------------------------------------------------------------

MCP_INIT = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-03-26", "capabilities": {},
               "clientInfo": {"name": "t", "version": "0"}},
}
MCP_HEADERS = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}


def test_mcp_rejects_anonymous(client):
    r = client.post("/mcp", json=MCP_INIT, headers=MCP_HEADERS)
    assert r.status_code == 401


def test_mcp_accepts_bearer_token(client):
    headers = dict(MCP_HEADERS)
    headers["Authorization"] = "Bearer mcp-secret"
    r = client.post("/mcp", json=MCP_INIT, headers=headers)
    assert r.status_code == 200


# --- explicit dev opt-out ---------------------------------------------------------

def test_dev_no_auth_opens_routes(monkeypatch):
    monkeypatch.setenv("GHOSTMODE_DEV_NO_AUTH", "1")
    server = create_server(port=3200)
    app = server.http_app(transport="http")
    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.get("/api/config-validate").status_code == 200


# --- server-side permission tiers (#22: perms were client-side only) -------------

def _grant(monkeypatch, **perms):
    base = {"int_team_member": False, "linear_enabled": False, "ops_enabled": False}
    base.update(perms)
    import ghostmode.github_auth as ga
    monkeypatch.setattr(ga, "get_user_permissions", lambda email, github_token=None, **kw: base)


def test_linear_requires_linear_perm(client, monkeypatch):
    _stub_verify(monkeypatch, dict(VALID_CLAIMS))
    _grant(monkeypatch, linear_enabled=False)
    r = client.get("/api/linear/issues", headers={"x-amzn-oidc-data": "x.y.z"})
    assert r.status_code == 403


def test_linear_allows_with_perm(client, monkeypatch):
    _stub_verify(monkeypatch, dict(VALID_CLAIMS))
    _grant(monkeypatch, linear_enabled=True)
    r = client.get("/api/linear/issues", headers={"x-amzn-oidc-data": "x.y.z"})
    assert r.status_code == 200  # may be "Linear not configured" JSON, but not 403


def test_ops_requires_ops_perm(client, monkeypatch):
    _stub_verify(monkeypatch, dict(VALID_CLAIMS))
    _grant(monkeypatch, ops_enabled=False)
    r = client.get("/ops/", headers={"x-amzn-oidc-data": "x.y.z"})
    assert r.status_code == 403


def test_ops_allows_with_perm(client, monkeypatch):
    _stub_verify(monkeypatch, dict(VALID_CLAIMS))
    _grant(monkeypatch, ops_enabled=True)
    r = client.get("/ops/", headers={"x-amzn-oidc-data": "x.y.z"})
    assert r.status_code == 200
