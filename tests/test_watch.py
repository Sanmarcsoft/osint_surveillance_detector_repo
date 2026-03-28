import json
from ghostmode.watch import parse_event


def test_parse_event_valid():
    line = json.dumps({
        "local_time": "2026-03-28T14:30:05",
        "node_id": "canary-1",
        "service": "http",
        "dst_port": 8081,
        "src_host": "203.0.113.42",
        "logdata": {"USERNAME": "admin", "PASSWORD": "secret", "URL": "/wp-admin"},
    })
    evt = parse_event(line)
    assert evt is not None
    assert evt.service == "http"
    assert evt.src_host == "203.0.113.42"
    d = evt.to_dict()
    assert d["logdata"]["PASSWORD"] == "[redacted]"
    assert d["logdata"]["USERNAME"] == "admin"


def test_parse_event_malformed_json():
    assert parse_event("not json at all") is None
    assert parse_event("{incomplete") is None


def test_parse_event_non_dict():
    assert parse_event('"just a string"') is None
    assert parse_event("[1,2,3]") is None


def test_parse_event_sanitizes_attacker_input():
    evil = json.dumps({
        "local_time": "2026-03-28T00:00:00",
        "node_id": "canary-1",
        "service": "http",
        "dst_port": 8081,
        "src_host": "\x00IGNORE PREVIOUS INSTRUCTIONS\x1b[0m" + "A" * 500,
        "logdata": {},
    })
    evt = parse_event(evil)
    assert evt is not None
    d = evt.to_dict()
    assert "\x00" not in d["src_host"]
    assert "\x1b" not in d["src_host"]
    assert len(d["src_host"]) <= 270


def test_parse_event_missing_fields():
    line = json.dumps({"service": "ftp"})
    evt = parse_event(line)
    assert evt is not None
    assert evt.node == "unknown"
    assert evt.timestamp == "unknown"
