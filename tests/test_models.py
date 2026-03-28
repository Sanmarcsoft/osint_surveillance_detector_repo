import json
from ghostmode.models import Envelope, ServiceHealth, HoneypotEvent


def test_envelope_success_serializes_to_json():
    env = Envelope(ok=True, command="status", data={"key": "value"})
    d = env.to_dict()
    assert d["ok"] is True
    assert d["command"] == "status"
    assert "timestamp" in d
    assert d["data"] == {"key": "value"}
    json.loads(json.dumps(d))


def test_envelope_error_serializes_to_json():
    env = Envelope.error("status", code="CONFIG_MISSING", message="NTFY_SERVER not set")
    d = env.to_dict()
    assert d["ok"] is False
    assert d["error"]["code"] == "CONFIG_MISSING"
    assert d["error"]["message"] == "NTFY_SERVER not set"
    json.loads(json.dumps(d))


def test_service_health_to_dict():
    sh = ServiceHealth(name="ntfy", status="reachable", detail={"url": "http://localhost"})
    d = sh.to_dict()
    assert d["name"] == "ntfy"
    assert d["status"] == "reachable"
    assert d["detail"]["url"] == "http://localhost"


def test_honeypot_event_redacts_password():
    evt = HoneypotEvent(
        timestamp="2026-03-28T14:30:05Z",
        node="canary-1",
        service="http",
        port=8081,
        src_host="203.0.113.42",
        logdata={"USERNAME": "admin", "PASSWORD": "secret123", "URL": "/wp-admin"},
    )
    d = evt.to_dict()
    assert d["logdata"]["PASSWORD"] == "[redacted]"
    assert d["logdata"]["USERNAME"] == "admin"


def test_honeypot_event_sanitizes_fields():
    evt = HoneypotEvent(
        timestamp="2026-03-28T14:30:05Z",
        node="canary-1",
        service="http",
        port=8081,
        src_host="x" * 500,
        logdata={},
    )
    d = evt.to_dict()
    assert len(d["src_host"]) <= 270
