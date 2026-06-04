"""Tests for the OpenUI Lang view builders + /api/ui routes (osint #45)."""

import time

import pytest
from starlette.testclient import TestClient

from ghostmode import alb_auth
from ghostmode.mcp_server import create_server
from ghostmode.openui_views import build_ops_lang


def _row(label="Website", host="www.thephenom.app", code=200, expect=(200,),
         reachable=True, latency=120, ssl_days=60, kind="http", **kw):
    base = {"label": label, "host": host, "code": code, "expect": expect,
            "reachable": reachable, "latency_ms": latency, "ssl_days": ssl_days,
            "kind": kind, "is_self": False, "tls_na": False}
    base.update(kw)
    return base


def test_lang_doc_starts_at_root_and_is_line_oriented():
    doc = build_ops_lang([_row()])
    lines = [l for l in doc.splitlines() if l.strip()]
    assert lines[0].startswith("root = ")
    # one statement per line: every non-empty line is `ident = Expr`
    for l in lines:
        assert " = " in l, f"not a statement: {l}"


def test_lang_encodes_desired_code_colors():
    rows = [
        _row(code=200, expect=(200,)),                     # desired -> success
        _row(label="Gate", code=200, expect=(302,)),       # gate off -> warning
        _row(label="Down", code=None, reachable=False,
             latency=None, ssl_days=None),                 # down -> danger
    ]
    doc = build_ops_lang(rows)
    assert '"success"' in doc
    assert '"warning"' in doc
    assert '"danger"' in doc
    assert 'Tag("DOWN"' in doc


def test_lang_escapes_strings():
    doc = build_ops_lang([_row(label='Evil "quote" \\ asset')])
    # json-escaped, never raw quotes inside a literal
    assert '\\"quote\\"' in doc


def test_lang_summary_counts_only_desired():
    rows = [_row(), _row(label="Amber", code=404, expect=(200,))]
    doc = build_ops_lang(rows)
    assert '"1/2 desired"' in doc


# --- routes -------------------------------------------------------------------------

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


def test_ui_ops_route_gated_like_ops_board(client, monkeypatch):
    _verified(monkeypatch)
    import ghostmode.github_auth as ga
    monkeypatch.setattr(ga, "get_user_permissions",
                        lambda email, github_token=None, **kw: {
                            "int_team_member": False, "linear_enabled": False,
                            "ops_enabled": False})
    r = client.get("/api/ui/ops", headers={"x-amzn-oidc-data": "x.y.z"})
    assert r.status_code == 403


def test_ui_ops_route_returns_lang(client, monkeypatch):
    _verified(monkeypatch)
    import ghostmode.github_auth as ga
    import ghostmode.ops_dashboard as ops
    monkeypatch.setattr(ga, "get_user_permissions",
                        lambda email, github_token=None, **kw: {
                            "int_team_member": True, "linear_enabled": True,
                            "ops_enabled": True})
    monkeypatch.setattr(ops, "run_probes", lambda: [_row()])
    r = client.get("/api/ui/ops", headers={"x-amzn-oidc-data": "x.y.z"})
    assert r.status_code == 200
    assert r.text.startswith("root = ")
    assert r.headers["content-type"].startswith("text/plain")


def test_openui_bundle_assets_served(client, monkeypatch):
    _verified(monkeypatch)
    for name, ctype in (("openui-bundle.min.js", "text/javascript"),
                        ("openui-styles.css", "text/css")):
        r = client.get(f"/assets/openui/{name}",
                       headers={"x-amzn-oidc-data": "x.y.z"})
        assert r.status_code == 200, name
        assert r.headers["content-type"].startswith(ctype)
