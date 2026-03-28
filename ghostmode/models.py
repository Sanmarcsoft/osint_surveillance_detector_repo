from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ghostmode.sanitize import sanitize

_REDACTED_KEYS = {"PASSWORD", "PUBLICKEY"}


@dataclass
class Envelope:
    ok: bool
    command: str
    data: Any = None
    error_info: Optional[dict] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "ok": self.ok,
            "command": self.command,
            "timestamp": self.timestamp,
        }
        if self.ok:
            d["data"] = self.data
        else:
            d["error"] = self.error_info
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def success(cls, command: str, data: Any) -> Envelope:
        return cls(ok=True, command=command, data=data)

    @classmethod
    def error(cls, command: str, code: str, message: str) -> Envelope:
        return cls(ok=False, command=command, error_info={"code": code, "message": message})


@dataclass
class ServiceHealth:
    name: str
    status: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "detail": self.detail}


@dataclass
class HoneypotEvent:
    timestamp: str
    node: str
    service: str
    port: int
    src_host: str
    logdata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        safe_logdata = {}
        for k, v in self.logdata.items():
            if k in _REDACTED_KEYS:
                safe_logdata[k] = "[redacted]"
            else:
                safe_logdata[k] = sanitize(str(v))
        return {
            "event": "honeypot_hit",
            "timestamp": sanitize(self.timestamp),
            "node": sanitize(self.node),
            "service": sanitize(self.service),
            "port": self.port,
            "src_host": sanitize(self.src_host),
            "logdata": safe_logdata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass
class AlertResult:
    channel: str
    success: bool
    status_code: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"channel": self.channel, "success": self.success}
        if self.status_code is not None:
            d["status_code"] = self.status_code
        if self.error:
            d["error"] = self.error
        return d


@dataclass
class ConfigIssue:
    key: str
    severity: str
    message: str

    def to_dict(self) -> dict:
        return {"key": self.key, "severity": self.severity, "message": self.message}
