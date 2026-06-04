"""Tests for the board backdrop (osint #34).

M directive: /ops and /ghostmode use the same starfield background as the
dev-nest SPA. The previous hero referenced www.thephenom.app cross-origin,
which the boards' own CSP (img-src 'self' data: …) silently blocked — the
backdrop must be served from 'self'.
"""

import time
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from ghostmode import alb_auth, brand
from ghostmode.mcp_server import create_server

_STATIC = Path(brand.__file__).parent / "static" / "figma"


# --- CSS stack --------------------------------------------------------------------

def test_backdrop_uses_self_hosted_assets():
    """Cross-origin background URLs violate img-src 'self' and never render."""
    assert "/assets/figma/bg-image.jpg" in brand.BACKDROP_CSS
    assert "http" not in brand.BACKDROP_CSS, (
        "backdrop must not reference cross-origin assets (CSP img-src 'self')"
    )


def test_backdrop_layers_clean_starfield():
    """M iteration 2026-06-04: starfield + dim + cyan glow + floor — the
    magenta home-overlay turned the boards to purple mud on mobile."""
    css = brand.BACKDROP_CSS
    assert "linear-gradient" in css        # dim layer over the starfield
    assert "radial-gradient" in css        # cyan top glow
    assert "165, 227, 232" in css or "#a5e3e8" in css.lower()
    assert "home-overlay" not in css, "the overlay reads as purple blotches"


def test_bundled_assets_exist():
    for name in ("bg-image.jpg", "home-overlay.png", "floor.svg"):
        path = _STATIC / name
        assert path.is_file(), f"missing bundled asset: {name}"
        assert path.stat().st_size > 0


# --- /assets/figma/ route ----------------------------------------------------------

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


@pytest.mark.parametrize("name,ctype", [
    ("bg-image.jpg", "image/jpeg"),
    ("home-overlay.png", "image/png"),
    ("floor.svg", "image/svg+xml"),
])
def test_figma_assets_served(client, monkeypatch, name, ctype):
    _verified(monkeypatch)
    r = client.get(f"/assets/figma/{name}", headers={"x-amzn-oidc-data": "x.y.z"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(ctype)
    assert len(r.content) > 0


def test_unknown_asset_404(client, monkeypatch):
    _verified(monkeypatch)
    r = client.get("/assets/figma/alb_auth.py",
                   headers={"x-amzn-oidc-data": "x.y.z"})
    assert r.status_code == 404


def test_asset_route_requires_identity(client, monkeypatch):
    monkeypatch.setattr(alb_auth, "verify_alb_jwt", lambda token: None)
    r = client.get("/assets/figma/bg-image.jpg",
                   headers={"x-amzn-oidc-data": "forged"})
    assert r.status_code == 401


# --- every board uses the shared starfield (no duplicated cross-origin hero) -------

def _board_htmls():
    from ghostmode.dashboard import build_dashboard
    from ghostmode.nest_dashboard import build_nest_wrapper
    from ghostmode.ops_dashboard import build_ops_dashboard
    return {
        "ghostmode": build_dashboard(),
        "nest": build_nest_wrapper(),
        "ops": build_ops_dashboard(),
    }


def test_all_boards_use_self_hosted_starfield():
    for name, html in _board_htmls().items():
        assert "/assets/figma/bg-image.jpg" in html, f"{name}: starfield missing"
        assert "www.thephenom.app/assets/images" not in html, (
            f"{name}: still references the CSP-blocked cross-origin hero"
        )


# --- /ops mobile conformance (M directive 2026-06-04) ------------------------------

def test_ops_board_mobile_ready():
    from ghostmode.ops_dashboard import build_ops_dashboard
    html = build_ops_dashboard()
    assert 'name="viewport"' in html and "width=device-width" in html
    # small screens get a dedicated layout pass
    assert "@media" in html


# --- board toggle (osint #37, M directive) ------------------------------------------

def test_boards_carry_toggle_nav():
    """Both boards link to each other with the shared pill toggle, and mark
    their own tab active."""
    from ghostmode.dashboard import build_dashboard
    from ghostmode.ops_dashboard import build_ops_dashboard
    ops = build_ops_dashboard()
    gm = build_dashboard()
    for html in (ops, gm):
        assert 'class="board-nav"' in html
        assert 'href="/ops/"' in html
        assert 'href="/ghostmode/"' in html
    # active tab marked on the right side in each
    assert re_active(ops, "/ops/")
    assert re_active(gm, "/ghostmode/")


def re_active(html: str, href: str) -> bool:
    import re
    # the anchor for `href` carries the active class
    pat = r'<a[^>]*class="[^"]*\bactive\b[^"]*"[^>]*href="' + href.replace("/", r"/") + '"'
    alt = r'<a[^>]*href="' + href.replace("/", r"/") + r'"[^>]*class="[^"]*\bactive\b[^"]*"'
    return bool(re.search(pat, html) or re.search(alt, html))


def test_ops_board_mobile_stacks_rows_not_scrolls():
    """M iteration: a horizontally-scrolling table hides the Status/Latency/TLS
    columns — the entire point of the board. Small screens must stack each
    probe as a card instead (thead hidden, cells grid-placed by class)."""
    from ghostmode.ops_dashboard import build_ops_dashboard
    html = build_ops_dashboard()
    flat = html.replace(" ", "").replace("\n", "")
    assert "thead{display:none" in flat
    # every cell is class-tagged so the stacked layout can place it
    for cls in ("td.asset", "td.host", "td.status", "td.lat", "td.tls"):
        assert cls.replace(" ", "") in flat, f"missing stacked-layout rule for {cls}"
    assert "class='host'" in html or 'class="host"' in html
