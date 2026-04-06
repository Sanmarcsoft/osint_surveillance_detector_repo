"""Configuration loading and validation."""

import os
import json
from typing import Optional

from dotenv import load_dotenv

_REQUIRED_ENV = {
    "NTFY_SERVER": "ntfy server URL",
    "NTFY_TOPIC": "ntfy topic name",
}

_RECOMMENDED_ENV = {
    "TS_AUTHKEY": "Tailscale auth key",
    "ALERT_MODE": "alert delivery mode (print, signal, ntfy, both)",
}


def _is_truthy(val: str) -> bool:
    return val.lower() in ("true", "1", "yes")


def load_config() -> dict:
    """Load configuration from environment (with .env fallback)."""
    load_dotenv()
    nest_mode = _is_truthy(os.getenv("NEST_MODE", ""))
    return {
        "ntfy_server": os.getenv("NTFY_SERVER", "http://localhost").rstrip("/"),
        "ntfy_topic": os.getenv("NTFY_TOPIC",
                                "ghostmode-phenom" if nest_mode else "ghostmode-alerts"),
        "ntfy_user": os.getenv("NTFY_USER") or None,
        "ntfy_pass": os.getenv("NTFY_PASS") or None,
        "alert_mode": os.getenv("ALERT_MODE", "print"),
        "signal_phone": os.getenv("SIGNAL_PHONE"),
        "signal_recipient": os.getenv("SIGNAL_RECIPIENT"),
        "opencanary_log": os.getenv("OPENCANARY_LOG", "/var/log/opencanary/opencanary.log"),
        "chromadb_host": os.getenv("CHROMADB_HOST", "10.0.0.12"),
        "chromadb_port": int(os.getenv("CHROMADB_PORT", "18000")),
        "mcp_port": int(os.getenv("MCP_PORT", "3200")),
        # N.E.S.T. mode — thephenom.app-only dashboard
        "nest_mode": nest_mode,
        "nest_zone_id": os.getenv("NEST_ZONE_ID", "637c0036b564b56f7257815b23bd2e17"),
        # Linear.app integration (server-side, never exposed to browser)
        "linear_api_key": os.getenv("LINEAR_API_KEY") or None,
        # GitHub org/team membership check
        "github_org_token": os.getenv("GITHUB_ORG_TOKEN") or None,
    }


def validate_config(canary_conf_path: Optional[str] = None) -> dict:
    """Validate environment variables and config files. Returns structured result."""
    issues = []

    for key, desc in _REQUIRED_ENV.items():
        if not os.getenv(key):
            issues.append({"key": key, "severity": "error", "message": f"Required: {desc}"})

    for key, desc in _RECOMMENDED_ENV.items():
        if not os.getenv(key):
            issues.append({"key": key, "severity": "warning", "message": f"Recommended: {desc}"})

    if canary_conf_path:
        try:
            with open(canary_conf_path) as f:
                json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            issues.append({
                "key": "opencanary.conf",
                "severity": "error",
                "message": f"Invalid config: {e}",
            })

    has_errors = any(i["severity"] == "error" for i in issues)
    return {"ok": not has_errors, "issues": issues}
