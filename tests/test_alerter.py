"""Tests for the intent-tier alert taxonomy + red-team hardening (alerter.py)."""
import ghostmode.alerter as al


def setup_function(_):
    al._recently_alerted.clear()
    al._emit_window.clear()


def _capture(monkeypatch):
    calls = []
    monkeypatch.setattr(al, "_publish",
                        lambda topic, title, body, priority: calls.append((topic, priority, title)) or True)
    monkeypatch.setattr(al, "load_config",
                        lambda: {"ntfy_server": "https://x", "ntfy_topic": "ghostmode-alerts",
                                 "ntfy_user": "u", "ntfy_pass": "p"})
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


def test_heartbeat_is_p2_operator_only(monkeypatch):
    calls = _capture(monkeypatch)
    al.heartbeat("ok")
    assert calls and calls[0][1] == al.P2 and all(t == "ghostmode-alerts" for t, _, _ in calls)


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
