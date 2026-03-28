"""Service health checks for external monitoring."""

import time
from typing import Optional

import requests

from ghostmode.models import ServiceHealth
from ghostmode import metrics

_start_time = time.monotonic()


def check_ntfy(server: str, topic: str) -> ServiceHealth:
    """Check if ntfy server is reachable."""
    try:
        resp = requests.get(f"{server.rstrip('/')}/{topic}/json?poll=1", timeout=5)
        status = "reachable" if resp.status_code in (200, 304) else f"http_{resp.status_code}"
        metrics.services_up.labels(service="ntfy").set(1 if status == "reachable" else 0)
        return ServiceHealth(name="ntfy", status=status, detail={"url": f"{server}/{topic}"})
    except requests.RequestException as e:
        metrics.services_up.labels(service="ntfy").set(0)
        return ServiceHealth(name="ntfy", status="unreachable", detail={"error": str(e)})


def check_opencanary_log(path: str) -> ServiceHealth:
    """Check if OpenCanary is producing logs."""
    try:
        with open(path, "r") as f:
            lines = sum(1 for _ in f)
        metrics.services_up.labels(service="opencanary").set(1)
        return ServiceHealth(name="opencanary", status="running", detail={"log_lines": lines})
    except FileNotFoundError:
        metrics.services_up.labels(service="opencanary").set(0)
        return ServiceHealth(name="opencanary", status="log_missing", detail={"path": path})


def get_status(
    ntfy_server: str = "http://localhost",
    ntfy_topic: str = "ghostmode-alerts",
    canary_log: str = "/var/log/opencanary/opencanary.log",
) -> dict:
    """Aggregate health of all services."""
    ntfy = check_ntfy(ntfy_server, ntfy_topic)
    canary = check_opencanary_log(canary_log)

    uptime = time.monotonic() - _start_time
    metrics.uptime_seconds.set(uptime)

    return {
        "services": {
            "ntfy": ntfy.to_dict(),
            "opencanary": canary.to_dict(),
        },
        "uptime_seconds": round(uptime, 1),
    }
