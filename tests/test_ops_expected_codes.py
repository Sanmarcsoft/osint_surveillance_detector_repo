"""Tests for /ops per-asset expected codes (osint #39).

M audit: green meant "anything < 500" (401/404 included), probes followed
redirects (an SSO gate turning off would look identical to healthy), and
not-applicable TLS cells rendered alarm-red. Status color must encode
"matches the DESIRED code": green = desired, amber = alive-but-unexpected,
red = down. The probe must report the ORIGIN code, never a post-redirect one.
"""

import urllib.request

from ghostmode import ops_dashboard as ops


# --- desired-code badge logic -------------------------------------------------------

def test_status_class_green_only_on_expected():
    assert ops.status_class(200, (200,), reachable=True) == "up"
    assert ops.status_class(302, (302,), reachable=True) == "up"
    assert ops.status_class(401, (401,), reachable=True) == "up"


def test_status_class_amber_when_alive_but_unexpected():
    # 401 on an endpoint that should be 200 is NOT green
    assert ops.status_class(401, (200,), reachable=True) == "warn"
    # a gate that should redirect (302) suddenly serving 200 = gate OFF -> amber
    assert ops.status_class(200, (302,), reachable=True) == "warn"
    assert ops.status_class(404, (200,), reachable=True) == "warn"


def test_status_class_red_when_down():
    assert ops.status_class(None, (200,), reachable=False) == "down"
    assert ops.status_class(503, (200,), reachable=False) == "down"


# --- asset registry carries expectations -------------------------------------------

def test_every_http_asset_declares_expected_codes():
    for asset in ops.ASSETS:
        if asset["kind"] == "http":
            expect = asset.get("expect")
            assert expect, f"{asset['label']}: missing expect codes"
            assert all(isinstance(c, int) for c in expect)


def test_gated_assets_expect_their_gate_code():
    by_label = {a["label"]: a for a in ops.ASSETS}
    # SSO-gated apps: the DESIRED unauthenticated answer is the redirect
    assert 302 in by_label["Dev NEST"]["expect"]
    assert 302 in by_label["Analytics"]["expect"]
    # vanity redirect to AWS WorkMail is permanent by design
    assert 301 in by_label["Webmail"]["expect"]
    # token-gated by design
    assert 401 in by_label["ADSB cache (archive API)"]["expect"]


def test_api_public_probes_healthz_not_token_gated_path():
    by_label = {a["label"]: a for a in ops.ASSETS}
    assert by_label["API (public)"]["path"] == "/healthz"
    assert by_label["API (public)"]["expect"] == (200,)


# --- origin codes, not post-redirect codes ------------------------------------------

def test_probe_does_not_follow_redirects():
    """The opener must surface 3xx as the result, not chase it to a 200."""
    handlers = [type(h) for h in ops._OPENER.handlers]
    assert urllib.request.HTTPRedirectHandler not in handlers, (
        "probe opener must not auto-follow redirects — origin code is the signal"
    )


# --- n/a cells are neutral, not alarming --------------------------------------------

def test_non_tls_rows_render_neutral_na_badge():
    html = ops.build_ops_dashboard()
    # the n/a badge class exists and is styled dim, not down-red
    assert 'badge na' in html or "badge.na" in html
    assert ".badge.na" in html
