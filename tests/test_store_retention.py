"""Event store retention contract and fail-loud behaviour (#85).

The threat map offers windows up to 30 days, yet in production every window
beyond 23h returned an empty list. Root cause: ``query_events`` caught the
psycopg2 ``OperationalError`` and returned ``[]``, which is indistinguishable
from "there were no events". That also disarmed the 23h Cloudflare fallback in
``fetch_security_events``, whose ``except`` could never fire. A database the
service could not reach rendered on the dashboard as a clean bill of health.
"""

import pytest
from starlette.testclient import TestClient

from ghostmode.mcp_server import create_server


class _FakeCursor:
    description = [
        ("timestamp",), ("domain",), ("host",), ("path",), ("method",),
        ("action",), ("source",), ("client_ip",), ("country",), ("asn",),
        ("user_agent",), ("is_recon",), ("threat_level",),
    ]

    def __init__(self, rows):
        self._rows = rows

    def execute(self, *a, **k):
        return None

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return (0, None)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    """A store that is reachable and legitimately holds no rows."""

    def __init__(self, rows=()):
        self._rows = list(rows)
        self.autocommit = False

    def cursor(self):
        return _FakeCursor(self._rows)

    def close(self):
        return None


class TestRetentionContract:
    """The store must retain at least as long as the longest window offered."""

    def test_retention_covers_the_longest_map_window(self):
        from ghostmode.event_store import MAP_WINDOW_HOURS, RETENTION_HOURS
        assert RETENTION_HOURS >= max(MAP_WINDOW_HOURS)

    def test_retention_is_at_least_thirty_days(self):
        from ghostmode.event_store import RETENTION_HOURS
        assert RETENTION_HOURS >= 720

    def test_every_dashboard_window_is_within_retention(self):
        """No selectable timeframe may exceed what the store promises to keep."""
        import re
        from ghostmode.dashboard import _HTML
        from ghostmode.event_store import RETENTION_HOURS

        block = _HTML[_HTML.index('id="map-hours"'):]
        block = block[:block.index("</select>")]
        offered = [int(v) for v in re.findall(r'<option value="(\d+)"', block)]
        assert offered, "could not parse the threat-map window options"
        assert max(offered) <= RETENTION_HOURS, (
            f"window {max(offered)}h exceeds retention {RETENTION_HOURS}h")

    def test_nothing_in_the_store_module_prunes_below_retention(self):
        """Retention is currently guaranteed by never deleting. If a prune is
        ever added it must respect RETENTION_HOURS, so fail loudly here."""
        import inspect
        from ghostmode import event_store
        src = inspect.getsource(event_store).upper()
        if "DELETE FROM" in src:
            assert "RETENTION_HOURS" in inspect.getsource(event_store), (
                "a prune was added without referencing RETENTION_HOURS")


class TestStoreFailsLoud:
    """An unreachable store must not masquerade as an empty one."""

    def test_query_events_raises_when_the_store_is_unreachable(self, monkeypatch):
        from ghostmode import event_store
        from ghostmode.event_store import EventStoreUnavailable

        def boom():
            raise OSError("could not connect to server")

        monkeypatch.setattr(event_store, "_get_conn", boom)
        monkeypatch.setattr(event_store, "_ensure_schema", lambda: None)
        with pytest.raises(EventStoreUnavailable):
            event_store.query_events(hours_back=720, limit=100)

    def test_query_events_returns_empty_when_store_is_healthy_but_bare(
            self, monkeypatch):
        from ghostmode import event_store

        monkeypatch.setattr(event_store, "_get_conn", lambda: _FakeConn())
        monkeypatch.setattr(event_store, "_ensure_schema", lambda: None)
        assert event_store.query_events(hours_back=720, limit=100) == []

    def test_error_message_does_not_leak_connection_detail(self, monkeypatch):
        """osint #27: no host/user/dbname in a client-visible string."""
        from ghostmode import event_store
        from ghostmode.event_store import EventStoreUnavailable

        def boom():
            raise OSError("FATAL: password authentication failed for user "
                          "'nestops' at phenom-dev-postgres.rds.amazonaws.com")

        monkeypatch.setattr(event_store, "_get_conn", boom)
        monkeypatch.setattr(event_store, "_ensure_schema", lambda: None)
        with pytest.raises(EventStoreUnavailable) as ei:
            event_store.query_events(hours_back=720, limit=100)
        msg = str(ei.value)
        assert "nestops" not in msg
        assert "rds.amazonaws.com" not in msg


class TestFallbackIsRearmed:
    """With query_events raising, the existing 23h fallback can finally fire."""

    def test_fetch_falls_back_to_cloudflare_and_reports_degradation(
            self, monkeypatch):
        from ghostmode import cloudflare_monitor as cm
        from ghostmode.event_store import EventStoreUnavailable

        def dead_store(**kwargs):
            raise EventStoreUnavailable("Event store request failed (OSError)")

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"data": {"viewer": {"zones": [{
                    "zoneTag": "a" * 32,
                    "firewallEventsAdaptive": [{
                        "action": "block", "clientIP": "203.0.113.7",
                        "clientRequestHTTPHost": "www.thephenom.app",
                        "clientRequestPath": "/", "datetime": "2026-09-04T09:00:00Z",
                        "clientRequestHTTPMethodName": "GET", "source": "waf",
                        "userAgent": "curl", "clientCountryName": "US",
                        "clientASNDescription": "EXAMPLE",
                    }],
                }]}}}

        monkeypatch.setattr("ghostmode.event_store.query_events", dead_store)
        monkeypatch.setattr(cm, "_get_cf_headers", lambda: {"X-Auth": "x"})
        monkeypatch.setattr(cm, "get_zones", lambda: {"thephenom.app": "a" * 32})
        monkeypatch.setattr(cm.requests, "post", lambda *a, **k: _Resp())

        meta = {}
        events = cm.fetch_security_events(
            hours_back=720, limit_per_zone=100, meta=meta)

        assert meta.get("degraded") is True, meta
        assert meta.get("effective_hours") == 23, meta
        assert meta.get("store_error"), meta
        assert events, "fallback returned nothing"


class TestThreatMapSurfacesDegradation:
    """The API must let the UI say 'store down', not 'no threats'."""

    def _get(self, monkeypatch, meta_to_set):
        def fake_fetch(hours_back, limit_per_zone=20, zones=None, meta=None):
            if meta is not None:
                meta.update(meta_to_set)
            return []

        monkeypatch.setenv("GHOSTMODE_DEV_NO_AUTH", "1")
        monkeypatch.setattr(
            "ghostmode.cloudflare_monitor.fetch_security_events", fake_fetch)
        server = create_server(port=3200)
        app = server.http_app(transport="http")
        with TestClient(app, raise_server_exceptions=False) as c:
            return c.get("/api/threat-map?hours=720").json()

    def test_degraded_window_is_flagged(self, monkeypatch):
        body = self._get(monkeypatch, {
            "degraded": True, "effective_hours": 23,
            "store_error": "Event store request failed (OperationalError)"})
        assert body.get("degraded") is True
        assert body.get("store_error")
        assert body.get("effective_hours") == 23
        assert body.get("requested_hours") == 720

    def test_healthy_window_is_not_flagged(self, monkeypatch):
        body = self._get(monkeypatch, {"degraded": False, "effective_hours": 720})
        assert body.get("degraded") is False
        assert not body.get("store_error")


class TestStoreStatsReportsRetention:
    def test_stats_include_the_retention_contract(self, monkeypatch):
        from ghostmode import event_store

        monkeypatch.setenv("GHOSTMODE_DEV_NO_AUTH", "1")
        monkeypatch.setattr(event_store, "_get_conn", lambda: _FakeConn())
        monkeypatch.setattr(event_store, "_ensure_schema", lambda: None)
        server = create_server(port=3200)
        app = server.http_app(transport="http")
        with TestClient(app, raise_server_exceptions=False) as c:
            body = c.get("/api/store-stats").json()
        assert body.get("retention_hours") == event_store.RETENTION_HOURS
        assert "meets_retention" in body


class TestDashboardWarnsOnDegradedWindow:
    """An empty map must never read as all-clear when the store is down."""

    def test_dashboard_reads_the_degraded_flag(self):
        from ghostmode.dashboard import _HTML
        assert "data.degraded" in _HTML

    def test_dashboard_distinguishes_incomplete_from_empty(self):
        from ghostmode.dashboard import _HTML
        assert "No geolocated threats found" in _HTML
        assert "Incomplete: " in _HTML
