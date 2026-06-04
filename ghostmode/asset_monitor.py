"""Asset-down → ntfy monitor for the Ops infrastructure board.

The board (ops_dashboard.build_ops_dashboard) only probes on page load and never
alerts. This module adds the missing outage path: a daemon thread that probes the
same ASSETS on a fixed interval, tracks each asset's health, and PUSHES to that
asset's per-asset ntfy topic on an up→down transition (and a recovery on down→up).

Two things the page-render path got wrong for monitoring, fixed here:

  1. Down-definition. ops_dashboard._check badges any response < 500 as "reachable"
     (so 401/403/404 look UP). That is fine for "is the edge answering" but wrong
     for outage detection. Each asset declares an EXPECTED healthy code set below
     (e.g. /healthz → 200; token-gated public API and the gated ADSB route → 401;
     RDS → AVAILABLE; SES → SENDING). Health = probe code ∈ expected set.

  2. Debounce + dedup. A single transient blip should not page anyone. We require
     CONSEC_DOWN consecutive failing probes before alerting, re-alert at most once
     per REALERT_SECONDS while still down, and always send a single recovery.

Publishes with NTFY_USER=ghostmode-publisher / NTFY_PASS (already in the task env)
to NTFY_SERVER (alerts.sanmarcsoft.com). Topics are the per-asset phenom-* topics
whose ACLs are provisioned on the a1 ntfy server.
"""
from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
from typing import Optional

import requests

from ghostmode.config import load_config
from ghostmode.ops_dashboard import ASSETS, _check

logger = logging.getLogger(__name__)

# Per-asset monitor config: board label → (ntfy topic, expected-healthy code set).
# `None` expected set = always healthy (the self/Ops row — this code running is
# itself proof it is up). Codes match what ops_dashboard._check emits: ints for
# HTTP, "AVAILABLE"/"SENDING" for the AWS control-plane probes.
ASSET_MONITOR: dict[str, tuple[str, Optional[set]]] = {
    "Website": ("phenom-www", {200}),
    "NEST": ("phenom-nest", {200}),
    "Dev NEST": ("phenom-dev-nest", {200}),
    "Drop": ("phenom-drop", {200}),
    "Chat (Synapse)": ("phenom-chat", {200}),
    "API (staging)": ("phenom-api-staging", {200}),
    "API (public)": ("phenom-api-public", {401}),     # token-gated: 401 = healthy
    "Analytics": ("phenom-analytics", {200}),
    "Webmail": ("phenom-webmail", {200}),
    "Cloudflare edge": ("phenom-cf-edge", {200}),
    "ADSB cache (archive API)": ("phenom-adsb", {401}),  # gated route: 401 = healthy
    "Ops": ("phenom-ops", None),                       # self row, always up
    "DB · dev (RDS Postgres)": ("phenom-db-dev", {"AVAILABLE"}),
    "DB · prod (RDS Postgres)": ("phenom-db-prod", {"AVAILABLE"}),
    "Mail · SES (us-east-1)": ("phenom-ses", {"SENDING"}),
}

_INTERVAL_SECONDS = 60
_CONSEC_DOWN = 2          # consecutive failing probes before paging (debounce)
_REALERT_SECONDS = 1800   # re-page at most every 30 min while still down
_WARMUP_SECONDS = 30      # let the service settle before the first probe

# Admin aggregate: every asset alert is ALSO mirrored here so an admin can watch
# one topic instead of subscribing to all 15 per-asset topics. Set to None/"" to
# disable. The per-asset phenom-* topics still fire for the team. (M's device is
# subscribed to ghostmode-alerts — confirmed on-device delivery 2026-06-04.)
_MIRROR_TOPIC = "ghostmode-alerts"

# label → {"down_streak": int, "alerted": bool, "last_alert": float}
_state: dict[str, dict] = {}


def _is_healthy(result: dict, expected: Optional[set]) -> bool:
    """True when the probe result meets the asset's expected-healthy definition."""
    if result.get("is_self"):
        return True
    if expected is None:
        return True
    return result.get("code") in expected


def _publish(topic: str, title: str, body: str, priority: int, tags: str) -> bool:
    """Publish one notification to a specific ntfy topic. Returns True on HTTP 200."""
    cfg = load_config()
    server = (cfg.get("ntfy_server") or "").rstrip("/")
    if not server:
        logger.warning("Asset monitor: NTFY_SERVER unset; cannot publish %s", topic)
        return False
    auth = (cfg.get("ntfy_user"), cfg.get("ntfy_pass")) if cfg.get("ntfy_user") else None
    try:
        resp = requests.post(
            f"{server}/{topic}",
            data=body.encode("utf-8"),
            headers={"Title": title, "Priority": str(priority), "Tags": tags},
            auth=auth,
            timeout=8,
        )
        if resp.status_code == 200:
            return True
        logger.error("ntfy publish %s → HTTP %s: %s", topic, resp.status_code, resp.text[:200])
        return False
    except requests.RequestException as e:
        logger.error("ntfy publish %s failed: %s", topic, e)
        return False


def _emit(asset_topic: str, title: str, body: str, priority: int, tags: str) -> bool:
    """Publish to the asset's own topic AND mirror to the admin aggregate topic."""
    targets = [asset_topic]
    if _MIRROR_TOPIC and _MIRROR_TOPIC != asset_topic:
        targets.append(_MIRROR_TOPIC)
    ok = False
    for t in targets:
        if _publish(t, title, body, priority, tags):
            ok = True
    return ok


def evaluate_transition(label: str, topic: str, healthy: bool, result: dict,
                        now: Optional[float] = None) -> Optional[str]:
    """Update state for one asset and emit an alert on a transition.

    Returns "down", "recovered", or None — the action taken (for tests/logging).
    """
    if now is None:
        now = time.time()
    st = _state.setdefault(label, {"down_streak": 0, "alerted": False, "last_alert": 0.0})
    host = result.get("host", "?")
    code = result.get("code")

    if healthy:
        st["down_streak"] = 0
        if st["alerted"]:
            st["alerted"] = False
            _emit(
                topic,
                f"{label}: RECOVERED",
                f"{label} is back up ({host}). Probe: {code}.",
                priority=3,
                tags="white_check_mark",
            )
            return "recovered"
        return None

    # unhealthy
    st["down_streak"] += 1
    if st["down_streak"] < _CONSEC_DOWN:
        return None  # debounce a single transient blip
    if st["alerted"] and (now - st["last_alert"]) < _REALERT_SECONDS:
        return None  # already paged, still inside the re-alert cooldown
    st["alerted"] = True
    st["last_alert"] = now
    _emit(
        topic,
        f"{label}: DOWN",
        f"{label} is DOWN ({host}).\nProbe code: {code} (expected healthy).\n"
        f"Failing for {st['down_streak']} consecutive checks "
        f"(~{st['down_streak'] * _INTERVAL_SECONDS}s).",
        priority=5,
        tags="rotating_light",
    )
    return "down"


def monitor_tick() -> None:
    """Probe every monitored asset once and process transitions."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ASSETS)) as pool:
        results = list(pool.map(_check, ASSETS))
    for r in results:
        cfg_t = ASSET_MONITOR.get(r["label"])
        if not cfg_t:
            continue
        topic, expected = cfg_t
        evaluate_transition(r["label"], topic, _is_healthy(r, expected), r)


def _monitor_loop() -> None:
    time.sleep(_WARMUP_SECONDS)
    logger.info("Asset monitor started (interval=%ds, assets=%d)",
                _INTERVAL_SECONDS, len(ASSET_MONITOR))
    while True:
        try:
            monitor_tick()
        except Exception as e:  # never let the loop die
            logger.error("Asset monitor tick failed: %s", e)
        time.sleep(_INTERVAL_SECONDS)


def start_asset_monitor() -> None:
    """Start the asset-down monitor as a daemon thread."""
    t = threading.Thread(target=_monitor_loop, daemon=True, name="asset-monitor")
    t.start()
