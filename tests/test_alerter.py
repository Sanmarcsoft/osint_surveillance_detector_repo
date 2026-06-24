"""Tests for the intent-tier alert taxonomy + red-team hardening (alerter.py)."""
import ghostmode.alerter as al


def setup_function(_):
    al._recently_alerted.clear()
    al._emit_window.clear()
    al.greynoise._cache.clear()


def _capture(monkeypatch):
    calls = []
    monkeypatch.setattr(al, "_publish",
                        lambda topic, title, body, priority: calls.append((topic, priority, title)) or True)
    monkeypatch.setattr(al, "load_config",
                        lambda: {"ntfy_server": "https://x", "ntfy_topic": "ghostmode-alerts",
                                 "ntfy_user": "u", "ntfy_pass": "p"})
    # Default: treat single-domain sources as malicious so the legacy aggregation/
    # cap tests exercise the P4 path. The noise-gate tests below override this, and
    # nothing here hits the network (the real GreyNoise lookup is mocked away).
    monkeypatch.setattr(al.greynoise, "is_malicious", lambda ip: True)
    return calls


def test_pathwalk_flood_aggregates_to_one_alert(monkeypatch):
    calls = _capture(monkeypatch)
    evs = [{"threat_level": "high", "client_ip": "1.2.3.4", "host": "www.thephenom.app",
            "path": f"/.env?{n}", "action": "block", "country": "RU", "domain": "thephenom.app"}
           for n in range(50)]
    # prime suppresses (no restart storm)
    assert al.process_surveillance_alerts(evs, [], prime=True) == 0 and calls == []
    al.process_surveillance_alerts(evs, [])
    ops = [c for c in calls if c[0] == "ghostmode-alerts"]
    assert len(ops) == 1 and ops[0][1] == al.P4  # 50 path-walk events -> ONE P4


def test_cross_domain_is_p5_with_signal(monkeypatch):
    calls = _capture(monkeypatch)
    sigs = []
    monkeypatch.setattr(al, "_signal_fallback", lambda t, b: sigs.append(t))
    al.process_surveillance_alerts([], [{"client_ip": "9.9.9.9",
                                         "domains": ["thephenom.app", "sanmarcsoft.com"],
                                         "event_count": 12}])
    assert any(p == al.P5 for _, p, _ in calls) and sigs


def test_heartbeat_is_p2_no_domain_topics(monkeypatch):
    calls = _capture(monkeypatch)
    al.heartbeat("ok")
    topics = {t for t, _, _ in calls}
    # P2 → operator topic + admin mirror only, never stakeholder domain topics.
    assert calls and all(p == al.P2 for _, p, _ in calls)
    assert topics == {"ghostmode-alerts", "universal-exports"}


def test_operator_alerts_mirror_to_universal_exports(monkeypatch):
    """Every operator-topic alert must also reach the universal-exports admin
    aggregate (the mirror M requires). Regression guard for the silent gap."""
    calls = _capture(monkeypatch)
    al.heartbeat("ok")
    assert any(t == "universal-exports" for t, _, _ in calls), (
        "operator alert was NOT mirrored to universal-exports"
    )


def test_dedup_key_ignores_path(monkeypatch):
    now = 1000.0
    assert al._dedup_ok("ip:5.5.5.5:block", now) is True
    assert al._dedup_ok("ip:5.5.5.5:block", now + 10) is False  # within cooldown


def test_cleartext_ntfy_refused(monkeypatch):
    monkeypatch.setattr(al, "load_config", lambda: {"ntfy_server": "http://evil.example"})
    assert al._ntfy_server() is None
    monkeypatch.setattr(al, "load_config", lambda: {"ntfy_server": "https://alerts.sanmarcsoft.com"})
    assert al._ntfy_server() == "https://alerts.sanmarcsoft.com"


def test_per_scan_cap_rolls_up(monkeypatch):
    calls = _capture(monkeypatch)
    evs = [{"threat_level": "high", "client_ip": f"1.1.1.{n}", "host": "h", "path": "/x", "action": "block"}
           for n in range(25)]  # > _MAX_ALERTS_PER_SCAN (20)
    al.process_surveillance_alerts(evs, [])
    assert any(p == al.P3 for _, p, _ in calls), "expected a P3 volume-cap rollup"


# --- #78: single-source background-scanner noise gate ----------------------

def _scan(ip, host="www.thephenom.app", domain="thephenom.app", n=8):
    return [{"threat_level": "high", "client_ip": ip, "host": host, "path": f"/.env?{i}",
             "action": "managed_challenge", "country": "US", "domain": domain} for i in range(n)]


def test_single_domain_benign_scanner_suppressed(monkeypatch):
    """A single-domain source GreyNoise does not call malicious is background
    noise: Cloudflare already blocked it, so it must NOT page."""
    calls = _capture(monkeypatch)
    monkeypatch.setattr(al.greynoise, "is_malicious", lambda ip: False)
    sent = al.process_surveillance_alerts(_scan("203.0.113.7"), [])
    assert sent == 0
    assert not [c for c in calls if c[1] in (al.P4, al.P5)], "background scanner should be suppressed"


def test_single_domain_malicious_pages_p4(monkeypatch):
    """GreyNoise-confirmed malicious single-source still pages P4."""
    calls = _capture(monkeypatch)
    monkeypatch.setattr(al.greynoise, "is_malicious", lambda ip: ip == "198.51.100.9")
    al.process_surveillance_alerts(_scan("198.51.100.9"), [])
    ops = [c for c in calls if c[0] == "ghostmode-alerts" and c[1] == al.P4]
    assert len(ops) == 1


def test_cross_domain_ip_pages_p5_only_not_duplicate_p4(monkeypatch):
    """A cross-domain actor pages P5 once; its redundant per-domain P4 is skipped,
    and it is NOT dropped by the noise gate (correlation overrides GreyNoise)."""
    calls = _capture(monkeypatch)
    monkeypatch.setattr(al.greynoise, "is_malicious", lambda ip: False)  # would suppress if not correlated
    evs = _scan("9.9.9.9", host="www.thephenom.app", domain="thephenom.app")
    correlated = [{"client_ip": "9.9.9.9", "domains": ["thephenom.app", "sanmarcsoft.com"],
                   "event_count": 20, "country": "US", "asn": "AS1"}]
    al.process_surveillance_alerts(evs, correlated)
    prios = [p for _, p, _ in calls]
    assert al.P5 in prios, "cross-domain actor must page P5"
    assert al.P4 not in prios, "redundant per-domain P4 must be skipped for a correlated IP"
