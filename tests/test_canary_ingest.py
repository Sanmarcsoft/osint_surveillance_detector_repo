"""Tests for the authenticated canary event ingest endpoint (/api/canary-ingest).

Remote OpenCanary sensors (EC2 honeypot, NAS canary) POST events here via
OpenCanary's WebhookHandler; ghostmode appends them to OPENCANARY_LOG so the
dashboard, logs queries, and watch pipeline see remote events as if local.

Policy:
- Bearer GHOSTMODE_INGEST_TOKEN required; unset token NEVER matches (fail closed).
- Accepts a single event dict, a list of events, or WebhookHandler's
  {"message": "<json event string>"} envelope.
- Events must be JSON objects with a "logtype" field; everything else is 400.
- Appended as one JSON line per event (JSONL, same format OpenCanary writes).
"""

import json

import pytest
from starlette.testclient import TestClient

from ghostmode.logs import query_logs
from ghostmode.mcp_server import create_server


EVENT = {
    "dst_host": "10.0.0.5",
    "dst_port": 2121,
    "local_time": "2026-06-04 18:00:00.000000",
    "logdata": {"USERNAME": "root", "PASSWORD": "admin"},
    "logtype": 2000,
    "node_id": "ec2-canary-1",
    "src_host": "203.0.113.7",
    "src_port": 51234,
}


@pytest.fixture()
def log_path(tmp_path):
    return str(tmp_path / "opencanary.log")


@pytest.fixture()
def client(monkeypatch, log_path):
    monkeypatch.setenv("GHOSTMODE_INGEST_TOKEN", "ingest-secret")
    monkeypatch.setenv("OPENCANARY_LOG", log_path)
    monkeypatch.delenv("GHOSTMODE_DEV_NO_AUTH", raising=False)
    server = create_server(port=3200)
    app = server.http_app(transport="http")
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _post(client, payload, token="ingest-secret", raw=None):
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if raw is not None:
        headers["Content-Type"] = "application/json"
        return client.post("/api/canary-ingest", content=raw, headers=headers)
    return client.post("/api/canary-ingest", json=payload, headers=headers)


# --- auth ---------------------------------------------------------------------

def test_ingest_rejects_anonymous(client):
    assert _post(client, EVENT, token=None).status_code == 401


def test_ingest_rejects_wrong_token(client):
    assert _post(client, EVENT, token="wrong").status_code == 401


def test_ingest_fails_closed_when_token_unset(monkeypatch, log_path):
    monkeypatch.delenv("GHOSTMODE_INGEST_TOKEN", raising=False)
    monkeypatch.setenv("OPENCANARY_LOG", log_path)
    monkeypatch.delenv("GHOSTMODE_DEV_NO_AUTH", raising=False)
    server = create_server(port=3200)
    app = server.http_app(transport="http")
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.post("/api/canary-ingest", json=EVENT,
                   headers={"Authorization": "Bearer "})
        assert r.status_code == 401


# --- happy paths --------------------------------------------------------------

def test_ingest_accepts_single_event(client, log_path):
    r = _post(client, EVENT)
    assert r.status_code == 200
    assert r.json()["data"]["written"] == 1
    lines = open(log_path).read().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["src_host"] == "203.0.113.7"


def test_ingest_accepts_batch(client, log_path):
    r = _post(client, [EVENT, {**EVENT, "src_host": "198.51.100.2"}])
    assert r.status_code == 200
    assert r.json()["data"]["written"] == 2
    assert len(open(log_path).read().splitlines()) == 2


def test_ingest_accepts_webhook_envelope(client, log_path):
    # OpenCanary WebhookHandler posts {"message": "<formatted log line>"}.
    r = _post(client, {"message": json.dumps(EVENT)})
    assert r.status_code == 200
    assert r.json()["data"]["written"] == 1
    assert json.loads(open(log_path).read().splitlines()[0])["logtype"] == 2000


def test_ingested_events_visible_via_query_logs(client, log_path):
    _post(client, EVENT)
    events = query_logs(log_path)
    assert len(events) == 1
    assert events[0]["src_host"] == "203.0.113.7"


def test_ingest_writes_single_line_per_event(client, log_path):
    evil = {**EVENT, "logdata": {"USERNAME": "a\nb", "PASSWORD": "c\rd"}}
    _post(client, evil)
    lines = open(log_path).read().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["logdata"]["USERNAME"] == "a\nb"


# --- validation ---------------------------------------------------------------

def test_ingest_rejects_non_json_body(client, log_path):
    r = _post(client, None, raw=b"not json at all")
    assert r.status_code == 400
    assert not open(log_path, "a").tell()


def test_ingest_rejects_event_without_logtype(client, log_path):
    r = _post(client, {"src_host": "203.0.113.7"})
    assert r.status_code == 400


def test_ingest_rejects_non_object_event(client):
    assert _post(client, ["just-a-string"]).status_code == 400


def test_ingest_rejects_invalid_envelope(client):
    assert _post(client, {"message": "not json"}).status_code == 400


def test_ingest_rejects_oversized_payload(client):
    big = b"[" + b",".join([json.dumps(EVENT).encode()] * 3000) + b"]"
    r = _post(client, None, raw=big)
    assert r.status_code == 413


def test_ingest_rejects_get_method(client):
    r = client.get("/api/canary-ingest",
                   headers={"Authorization": "Bearer ingest-secret"})
    assert r.status_code == 405
