"""Push alert engine — intent-tiered, audience-routed ntfy/Signal alerts.

Tiers (Council taxonomy):
  P5 urgent  — cross-domain targeted recon (one actor hitting >=2 owned domains)
               and credential submission to a canary. ntfy priority 5 + Signal.
  P4 high    — honeypot interaction beyond bare connect, and WAF-block / recon
               bursts AGGREGATED per source IP (one alert per IP, not per request).
  P3 digest  — volume/cap rollups + periodic recon summaries (badge-only).
  P2 ops     — stack-health + a heartbeat ("all clear") so silence is trustworthy.

Audience routing:
  operator topic (NTFY_TOPIC, e.g. ghostmode-alerts) gets EVERYTHING.
  stakeholder per-domain topics (_DOMAIN_TOPICS) get exception-only (P4/P5),
  scoped to their own domain — silence by default.

Red-team hardening:
  - per-IP aggregation defeats path-walk flooding; per-scan cap + global rate
    limit bound total volume with a single rollup instead of a storm.
  - prime-on-startup avoids the in-memory-dedup restart re-alert storm.
  - every attacker field is sanitize()'d (incl. CR/LF, which would otherwise
    abort the send and silently suppress the alert).
  - the Click target is PINNED to the gated ops dashboard, never the event's own
    host (which would let an outsider plant a malicious tap target).
  - ntfy server must be https (basic-auth never sent in cleartext).
"""
from __future__ import annotations

import time
import logging
from typing import Optional

import requests

from ghostmode.config import load_config
from ghostmode.sanitize import sanitize, header_safe

logger = logging.getLogger(__name__)

# ntfy priority == tier number. 5 urgent / 4 high / 3 default / 2 low / 1 min.
P5, P4, P3, P2 = 5, 4, 3, 2
_TAGS = {5: "rotating_light", 4: "warning", 3: "mag", 2: "heartbeat", 1: "speech_balloon"}

# Click ALWAYS points at the gated ops dashboard — never an event-controlled host.
_DASHBOARD_URL = "https://nest-ops.thephenom.app/ops/"

# Stakeholder per-domain topics (exception-only, scoped). Operator topic = cfg.ntfy_topic.
_DOMAIN_TOPICS = {
    "thephenom.app": "ghostmode-phenom",
    "sanmarcsoft.com": "ghostmode-sanmarcsoft",
    "verifieddit.com": "ghostmode-verifieddit",
    "trusteddit.com": "ghostmode-trusteddit",
}

_COOLDOWN_SECONDS = 300
_MAX_ALERTS_PER_SCAN = 20      # beyond this, a single P3 rollup
_GLOBAL_MAX_PER_MIN = 30       # hard ceiling across scans

_recently_alerted: dict[str, float] = {}  # dedup key -> last-alert ts
_emit_window: list[float] = []             # global rate-limit ring of timestamps


def _ntfy_server() -> Optional[str]:
    """Validated ntfy base URL; refuse cleartext http (basic-auth in the clear)."""
    cfg = load_config()
    server = (cfg.get("ntfy_server") or "").rstrip("/")
    if not server:
        return None
    if server.startswith("http://") and not (
        server.startswith("http://localhost") or server.startswith("http://127.")
    ):
        logger.error("Refusing cleartext ntfy server %s (basic-auth would leak)", server)
        return None
    return server


def _dedup_ok(key: str, now: float, record: bool = True) -> bool:
    if now - _recently_alerted.get(key, 0) < _COOLDOWN_SECONDS:
        return False
    if record:
        _recently_alerted[key] = now
        cutoff = now - _COOLDOWN_SECONDS * 2
        for k in [k for k, t in _recently_alerted.items() if t < cutoff]:
            del _recently_alerted[k]
    return True


def _rate_ok(now: float) -> bool:
    cutoff = now - 60
    while _emit_window and _emit_window[0] < cutoff:
        _emit_window.pop(0)
    if len(_emit_window) >= _GLOBAL_MAX_PER_MIN:
        return False
    _emit_window.append(now)
    return True


def _publish(topic: str, title: str, body: str, priority: int) -> bool:
    server = _ntfy_server()
    if not server:
        return False
    cfg = load_config()
    auth = (cfg.get("ntfy_user"), cfg.get("ntfy_pass")) if cfg.get("ntfy_user") else None
    headers = {
        "Title": header_safe(title),
        "Priority": str(priority),
        "Tags": _TAGS.get(priority, "warning"),
        "Click": _DASHBOARD_URL,
    }
    try:
        resp = requests.post(f"{server}/{topic}", data=body.encode("utf-8"),
                             headers=headers, auth=auth, timeout=8)
        if resp.status_code == 200:
            return True
        logger.error("ntfy %s -> HTTP %s", topic, resp.status_code)
    except requests.RequestException as e:
        logger.error("ntfy %s failed: %s", topic, e)
    return False


def _signal_fallback(title: str, body: str) -> None:
    """P5 only: also page Signal so a single-transport ntfy failure can't blind us."""
    cfg = load_config()
    phone, recipient = cfg.get("signal_phone"), cfg.get("signal_recipient")
    if not (phone and recipient):
        return
    try:
        from ghostmode.alert import send_signal
        send_signal(f"{title}\n{body}"[:1000], phone, recipient)
    except Exception as e:  # never let the fallback break the primary path
        logger.warning("Signal fallback failed: %s", e)


def _emit(priority: int, title: str, body: str, *, domain: Optional[str] = None,
          operator_only: bool = False) -> bool:
    """Route by audience: operator topic always; stakeholder domain topic for P4+;
    P5 also pages Signal."""
    cfg = load_config()
    operator_topic = cfg.get("ntfy_topic", "ghostmode-alerts")
    ok = _publish(operator_topic, title, body, priority)
    if not operator_only and priority >= P4 and domain:
        dt = _DOMAIN_TOPICS.get(domain)
        if dt and dt != operator_topic:
            _publish(dt, title, body, priority)
    if priority >= P5:
        _signal_fallback(title, body)
    return ok


# --- formatting (host-first, all attacker fields sanitized) ------------------
def _aggregate_alert(ip, country, hosts, paths, action, count) -> tuple[str, str, int]:
    host0 = sanitize(sorted(hosts)[0]) if hosts else "?"
    title = f"{host0}: {count} recon/blocked hits from {sanitize(ip)}"
    body = (
        f"{sanitize(ip)} ({sanitize(country)}) — {count} high-severity events on "
        f"{', '.join(sanitize(h) for h in sorted(hosts)[:4])}\n"
        f"action: {sanitize(action)}\n"
        f"paths: {', '.join(sanitize(p) for p in list(paths)[:5])}"
    )
    return title, body, P4


def format_cross_domain_alert(c: dict) -> tuple[str, str, int]:
    """P5 — one actor hitting multiple owned domains (targeted recon)."""
    ip = sanitize(c.get("client_ip", "?"))
    domains = c.get("domains", [])
    body = (
        f"{ip} ({sanitize(c.get('country', '?'))}, {sanitize(c.get('asn', '?'))}) is "
        f"probing {len(domains)} owned domains:\n"
        f"{', '.join(sanitize(d) for d in domains)}\n"
        f"{c.get('event_count', 0)} events total — targeted reconnaissance."
    )
    return f"MULTI-DOMAIN recon: {ip} ({len(domains)} sites)", body, P5


def format_alert(event: dict) -> tuple[str, str, int]:
    """Single-event formatter (back-compat: MCP tool / tests). Host-first, sanitized."""
    ip, host = sanitize(event.get("client_ip", "?")), sanitize(event.get("host", "?"))
    path, action = sanitize(event.get("path", "/")), sanitize(event.get("action", "?"))
    country = sanitize(event.get("country", "?"))
    # P5 if it's a credential submission to a canary; else P4 recon/block.
    if event.get("is_credential") or event.get("action") in ("login", "credential"):
        return f"{host}: CANARY CREDENTIAL from {ip}", f"{ip} ({country}) submitted creds to a canary on {host}{path}", P5
    if event.get("is_recon"):
        return f"{host}: RECON {path}".rstrip(), f"{ip} ({country}) probing {host}{path}\naction: {action}", P4
    return f"{host}: BLOCKED", f"{ip} ({country}) blocked on {host}{path}\naction: {action}", P4


def should_alert(event: dict) -> bool:
    """Back-compat predicate: high-severity + per-(ip,action) cooldown (no raw path
    in the key, so a path-walker can't defeat dedup)."""
    if event.get("threat_level") != "high":
        return False
    return _dedup_ok(f"ip:{event.get('client_ip','')}:{event.get('action','')}", time.time())


def send_ntfy_alert(title: str, body: str, priority: int = P4,
                    domain: Optional[str] = None, click_url: Optional[str] = None) -> bool:
    """Back-compat sender; routes by audience. click_url is ignored (Click is pinned)."""
    return _emit(priority, title, body, domain=domain)


def process_surveillance_alerts(events: list[dict], correlated: Optional[list[dict]] = None,
                                prime: bool = False) -> int:
    """Aggregate HIGH events per source IP, dedup, cap, route by tier.

    prime=True (first scan after startup): record dedup state WITHOUT sending, so a
    restart doesn't replay the whole active backlog as a fresh alert storm.
    """
    now = time.time()
    sent = 0
    capped = 0

    # Burst aggregation: collapse all of one IP's high events into a single alert.
    by_ip: dict[str, dict] = {}
    for e in events:
        if e.get("threat_level") != "high":
            continue
        ip = e.get("client_ip", "?")
        g = by_ip.setdefault(ip, {"country": e.get("country", "?"), "hosts": set(),
                                  "paths": set(), "action": e.get("action", "?"),
                                  "domain": e.get("domain"), "count": 0})
        g["hosts"].add(e.get("host", "?"))
        g["paths"].add(e.get("path", "/"))
        g["count"] += 1

    for ip, g in by_ip.items():
        if not _dedup_ok(f"ip:{ip}:{g['action']}", now, record=not prime):
            continue
        if prime:
            continue
        if sent >= _MAX_ALERTS_PER_SCAN or not _rate_ok(now):
            capped += 1
            continue
        title, body, prio = _aggregate_alert(ip, g["country"], g["hosts"], g["paths"],
                                              g["action"], g["count"])
        if _emit(prio, title, body, domain=g["domain"]):
            sent += 1

    for c in (correlated or []):
        if not _dedup_ok(f"cross:{c.get('client_ip','')}", now, record=not prime):
            continue
        if prime:
            continue
        if not _rate_ok(now):
            capped += 1
            continue
        title, body, prio = format_cross_domain_alert(c)
        if _emit(prio, title, body):
            sent += 1

    if prime:
        logger.info("Surveillance alerter primed (%d active sources recorded, no pages)", len(by_ip))
    elif capped:
        _emit(P3, "Alert volume capped",
              f"{capped} more source(s) flagged this scan, suppressed to avoid flooding.",
              operator_only=True)
    return sent


def heartbeat(detail: str = "") -> bool:
    """P2 operator-only heartbeat so silence is trustworthy — a MISSING heartbeat
    is itself the signal that the alerting pipeline is dead."""
    body = "Ghost Mode alerting pipeline healthy. " + (detail or "No high-severity events outstanding.")
    return _emit(P2, "Ghost Mode: all clear", body, operator_only=True)
