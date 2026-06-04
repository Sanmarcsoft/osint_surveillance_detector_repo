"""Validated ingest of remote OpenCanary events into the local JSONL log.

Remote sensors (the EC2 honeypot, the NAS canary) POST events to
/api/canary-ingest using OpenCanary's WebhookHandler. Events are validated
and appended to OPENCANARY_LOG, so every downstream consumer — dashboard,
query_logs, watch, status — sees remote events exactly like local ones.
"""

import json
import os

MAX_BODY_BYTES = 256 * 1024
MAX_EVENTS_PER_REQUEST = 500


class IngestError(ValueError):
    """Validation failure with the HTTP status code it maps to."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def parse_payload(raw: bytes) -> list[dict]:
    """Parse and validate a request body into a list of canary events.

    Accepted shapes:
    - a single event object: {"logtype": 2000, ...}
    - a list of event objects
    - the WebhookHandler envelope: {"message": "<json event string>"}
    """
    if len(raw) > MAX_BODY_BYTES:
        raise IngestError("payload too large", 413)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise IngestError("body must be valid JSON")

    if isinstance(payload, dict) and isinstance(payload.get("message"), str):
        try:
            payload = json.loads(payload["message"])
        except json.JSONDecodeError:
            raise IngestError("message envelope is not valid JSON")

    events = payload if isinstance(payload, list) else [payload]
    if len(events) > MAX_EVENTS_PER_REQUEST:
        raise IngestError("too many events in one request", 413)
    for evt in events:
        if not isinstance(evt, dict) or "logtype" not in evt:
            raise IngestError("each event must be a JSON object with a logtype")
    return events


def append_events(path: str, events: list[dict]) -> int:
    """Append events to the JSONL log, one compact line per event."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "a") as f:
        for evt in events:
            f.write(json.dumps(evt, separators=(",", ":"), sort_keys=True) + "\n")
    return len(events)
