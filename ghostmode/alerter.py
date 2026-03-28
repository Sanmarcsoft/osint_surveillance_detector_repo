"""Push alert engine — sends ntfy notifications for high-severity surveillance events.

Only fires for:
  - HIGH threat events (WAF blocks, recon scanning)
  - Cross-domain actors (same IP hitting 2+ domains)
  - New IPs not seen in the last alert cycle

Deduplicates by IP+action to avoid flooding.
"""
from __future__ import annotations

import time
import logging
from typing import Optional

import requests

from ghostmode.config import load_config

logger = logging.getLogger(__name__)

# Track recently alerted IPs to avoid flooding (ip:action -> timestamp)
_recently_alerted: dict[str, float] = {}
_COOLDOWN_SECONDS = 300  # 5 minutes between duplicate alerts

# Per-domain topic routing — domain -> ntfy topic
# Subscribe to these individually in the ntfy app for domain-specific alerts
_DOMAIN_TOPICS = {
    "thephenom.app": "ghostmode-phenom",
    "sanmarcsoft.com": "ghostmode-sanmarcsoft",
    "verifieddit.com": "ghostmode-verifieddit",
    "trusteddit.com": "ghostmode-trusteddit",
}


def should_alert(event: dict) -> bool:
    """Determine if an event warrants a push notification."""
    threat = event.get("threat_level", "info")
    if threat != "high":
        return False

    # Deduplicate: same IP + same action within cooldown
    key = f"{event.get('client_ip', '')}:{event.get('action', '')}:{event.get('path', '')}"
    now = time.time()
    last = _recently_alerted.get(key, 0)
    if now - last < _COOLDOWN_SECONDS:
        return False

    _recently_alerted[key] = now

    # Prune old entries
    cutoff = now - _COOLDOWN_SECONDS * 2
    for k in list(_recently_alerted):
        if _recently_alerted[k] < cutoff:
            del _recently_alerted[k]

    return True


def format_alert(event: dict) -> tuple[str, str, int]:
    """Format an event into (title, body, priority) for ntfy.

    Priority: 5=urgent, 4=high, 3=default, 2=low, 1=min
    """
    ip = event.get("client_ip", "?")
    host = event.get("host", "?")
    path = event.get("path", "/")
    action = event.get("action", "?")
    country = event.get("country", "?")
    is_recon = event.get("is_recon", False)

    if is_recon:
        title = f"RECON: {host}{path}"
        body = f"IP {ip} ({country}) probing {host}{path}\nAction: {action}\nThis path is a known reconnaissance target."
        priority = 4
    else:
        title = f"BLOCKED: {host}"
        body = f"IP {ip} ({country}) blocked on {host}{path}\nAction: {action}"
        priority = 4

    return title, body, priority


def format_cross_domain_alert(correlated: dict) -> tuple[str, str, int]:
    """Format a cross-domain correlation into an alert."""
    ip = correlated.get("client_ip", "?")
    domains = correlated.get("domains", [])
    count = correlated.get("event_count", 0)
    country = correlated.get("country", "?")
    asn = correlated.get("asn", "?")

    title = f"MULTI-DOMAIN: {ip} ({len(domains)} sites)"
    body = (
        f"IP {ip} is probing {len(domains)} of your domains:\n"
        f"{', '.join(domains)}\n"
        f"{count} events total — {country}, {asn}\n"
        f"This indicates targeted reconnaissance."
    )
    return title, body, 5  # urgent priority


def send_ntfy_alert(title: str, body: str, priority: int = 4, domain: Optional[str] = None) -> bool:
    """Send push notifications via ntfy.

    Sends to the main ghostmode-alerts topic AND the domain-specific topic
    if the event is associated with a particular domain.
    """
    cfg = load_config()
    server = cfg.get("ntfy_server", "").rstrip("/")
    if not server:
        return False

    topics = [cfg.get("ntfy_topic", "ghostmode-alerts")]
    # Also send to domain-specific topic
    if domain:
        domain_topic = _DOMAIN_TOPICS.get(domain)
        if domain_topic:
            topics.append(domain_topic)

    auth = (cfg.get("ntfy_user"), cfg.get("ntfy_pass")) if cfg.get("ntfy_user") else None
    ok = False
    for topic in topics:
        try:
            resp = requests.post(
                f"{server}/{topic}",
                data=body.encode("utf-8"),
                headers={
                    "Title": title,
                    "Priority": str(priority),
                    "Tags": "skull,warning" if priority >= 4 else "eyes",
                },
                auth=auth,
                timeout=5,
            )
            if resp.status_code == 200:
                ok = True
        except requests.RequestException as e:
            logger.error("ntfy alert to %s failed: %s", topic, e)
    return ok


def process_surveillance_alerts(events: list[dict], correlated: Optional[list[dict]] = None):
    """Process surveillance events and send alerts for high-severity items.

    Call this after each surveillance scan.
    """
    sent = 0

    # High-severity individual events
    for evt in events:
        if should_alert(evt):
            title, body, priority = format_alert(evt)
            if send_ntfy_alert(title, body, priority, domain=evt.get("domain")):
                sent += 1

    # Cross-domain actors (always alert — these are targeted)
    if correlated:
        for c in correlated:
            key = f"cross:{c.get('client_ip', '')}"
            now = time.time()
            if now - _recently_alerted.get(key, 0) < _COOLDOWN_SECONDS:
                continue
            _recently_alerted[key] = now
            title, body, priority = format_cross_domain_alert(c)
            if send_ntfy_alert(title, body, priority):
                sent += 1

    return sent
