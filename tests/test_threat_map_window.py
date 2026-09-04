"""Threat map: cumulative time windows (#82) and keyless basemap (#83)."""

import pytest
from starlette.testclient import TestClient

from ghostmode.cloudflare_monitor import event_budget_for_window
from ghostmode.mcp_server import create_server

MAP_WINDOWS = [1, 6, 12, 24, 72, 168, 336, 720]


class TestEventBudgetForWindow:
    """The #82 regression: the fetch budget was a constant 50, so every
    window in the dropdown returned the same newest-50 events."""

    def test_longer_window_gets_a_larger_budget(self):
        assert event_budget_for_window(1) < event_budget_for_window(24)

    def test_dropdown_windows_are_not_all_identical(self):
        budgets = {h: event_budget_for_window(h) for h in MAP_WINDOWS}
        assert len(set(budgets.values())) > 1, f"all windows collapsed: {budgets}"

    def test_budget_never_shrinks_as_the_window_grows(self):
        budgets = [event_budget_for_window(h) for h in MAP_WINDOWS]
        assert budgets == sorted(budgets)

    def test_tiny_window_still_gets_a_usable_floor(self):
        assert event_budget_for_window(0.25) >= 200

    def test_cloudflare_ceiling_is_respected(self):
        # Cloudflare's firewallEventsAdaptive rejects limit > 1000.
        assert event_budget_for_window(720) <= 1000

    def test_store_ceiling_can_exceed_the_cloudflare_ceiling(self):
        # The Postgres event store has no such cap, so long windows may ask
        # for far more than Cloudflare would allow.
        assert event_budget_for_window(720, ceiling=20000) > 1000


class TestThreatMapEndpointScalesWithWindow:
    def _captured_limits(self, monkeypatch):
        captured = []

        def fake_fetch(hours_back, limit_per_zone=20, zones=None, meta=None):
            captured.append({"hours": hours_back, "limit": limit_per_zone})
            return []

        monkeypatch.setenv("GHOSTMODE_DEV_NO_AUTH", "1")
        monkeypatch.setattr(
            "ghostmode.cloudflare_monitor.fetch_security_events", fake_fetch)
        server = create_server(port=3200)
        app = server.http_app(transport="http")
        with TestClient(app, raise_server_exceptions=False) as c:
            c.get("/api/threat-map?hours=1")
            c.get("/api/threat-map?hours=720")
        return captured

    def test_endpoint_asks_for_more_events_on_a_longer_window(self, monkeypatch):
        captured = self._captured_limits(monkeypatch)
        assert len(captured) == 2
        assert captured[0]["limit"] < captured[1]["limit"], (
            f"limit did not scale with window: {captured}")


class TestKeylessBasemap:
    """#83: CARTO closed anonymous basemap access."""

    def test_dashboard_does_not_use_carto_tiles(self):
        from ghostmode.dashboard import _HTML
        assert "basemaps.cartocdn.com" not in _HTML

    def test_dashboard_uses_openstreetmap_tiles(self):
        from ghostmode.dashboard import _HTML
        assert "tile.openstreetmap.org" in _HTML

    def test_dashboard_attributes_openstreetmap(self):
        # OSM's tile usage policy requires visible attribution.
        from ghostmode.dashboard import _HTML
        assert "OpenStreetMap" in _HTML

    def test_csp_allows_the_new_tile_host_and_drops_the_old(self, monkeypatch):
        monkeypatch.setenv("GHOSTMODE_DEV_NO_AUTH", "1")
        server = create_server(port=3200)
        app = server.http_app(transport="http")
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "tile.openstreetmap.org" in csp
        assert "cartocdn.com" not in csp
