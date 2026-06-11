"""Service health checks for external monitoring."""

import os
import time
from typing import Optional

import requests

from ghostmode.models import ServiceHealth
from ghostmode.sanitize import safe_error
from ghostmode import metrics

_start_time = time.monotonic()


def check_ntfy(server: str, topic: str) -> ServiceHealth:
    """Check if ntfy server is reachable (with auth if configured)."""
    from ghostmode.config import load_config
    cfg = load_config()
    auth = None
    if cfg.get("ntfy_user") and cfg.get("ntfy_pass"):
        auth = (cfg["ntfy_user"], cfg["ntfy_pass"])
    try:
        resp = requests.get(f"{server.rstrip('/')}/{topic}/json?poll=1", auth=auth, timeout=5)
        status = "reachable" if resp.status_code in (200, 304) else f"http_{resp.status_code}"
        metrics.services_up.labels(service="ntfy").set(1 if status == "reachable" else 0)
        return ServiceHealth(name="ntfy", status=status, detail={"url": f"{server}/{topic}"})
    except requests.RequestException as e:
        metrics.services_up.labels(service="ntfy").set(0)
        return ServiceHealth(name="ntfy", status="unreachable", detail={"error": safe_error(e, "ntfy")})


def check_opencanary_log(path: str) -> ServiceHealth:
    """Health of the canary event pipeline (local sensor + remote ingest).

    Local OpenCanary and remote sensors (POSTing via /api/canary-ingest) both
    append to the same log file, so its last-modified age is a liveness signal
    for the whole sensor fleet — `stale` past CANARY_LOG_MAX_AGE_H (default
    48h) catches a dead remote pusher that a bare existence check misses.

    Instances that run no sensor pipeline at all (e.g. the ECS nest-ops
    deployment) leave OPENCANARY_LOG unset and report `not_configured`
    instead of a permanent false `log_missing` (osint #58).
    """
    if "OPENCANARY_LOG" not in os.environ:
        return ServiceHealth(
            name="opencanary",
            status="not_configured",
            detail={"hint": "set OPENCANARY_LOG to enable the sensor-pipeline check"},
        )
    max_age_h = float(os.getenv("CANARY_LOG_MAX_AGE_H", "48"))
    try:
        with open(path, "r") as f:
            lines = sum(1 for _ in f)
        age_s = max(0.0, time.time() - os.path.getmtime(path))
        stale = age_s > max_age_h * 3600
        metrics.services_up.labels(service="opencanary").set(0 if stale else 1)
        return ServiceHealth(
            name="opencanary",
            status="stale" if stale else "running",
            detail={
                "log_lines": lines,
                "last_activity_age_s": round(age_s, 1),
                "max_age_h": max_age_h,
            },
        )
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
