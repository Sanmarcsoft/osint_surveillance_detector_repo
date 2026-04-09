"""Cloudflare Security Events Monitor — multi-domain surveillance detection.

Pulls firewall events from all monitored Cloudflare zones via GraphQL API.
Detects: WAF triggers, bot activity, recon scanning, cross-domain correlation.
"""
from __future__ import annotations

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

from ghostmode.sanitize import sanitize

logger = logging.getLogger(__name__)

# Zone registry: domain -> zone_id
# Loaded from GHOSTMODE_CF_ZONES env var (JSON) or defaults
_DEFAULT_ZONES = {
    "sanmarcsoft.com": "54fc4be809963772a22ce2389dc87672",
    "thephenom.app": "637c0036b564b56f7257815b23bd2e17",
    "verifieddit.com": "de3653a6f82acf3eaad7c854a9980f29",
    "trusteddit.com": "959bc4897b409235ecae27b07d48625b",
}

_GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"

# Known-safe IPs — excluded from threat analysis
# Override with GHOSTMODE_SAFE_IPS env var (comma-separated)
_DEFAULT_SAFE_IPS = {
    "84.112.12.104",  # Home network (DNS records for internal services)
}


def _get_safe_ips() -> set[str]:
    raw = os.getenv("GHOSTMODE_SAFE_IPS", "")
    if raw:
        return set(ip.strip() for ip in raw.split(",") if ip.strip())
    return set(_DEFAULT_SAFE_IPS)

# Recon patterns — paths that indicate scanning/enumeration
RECON_PATHS = {
    "/.env", "/wp-admin", "/wp-login.php", "/admin", "/administrator",
    "/backup.sql", "/.git/config", "/config.php", "/phpinfo.php",
    "/wp-includes/wlwmanifest.xml", "/xmlrpc.php", "/.well-known/",
    "/api/v1", "/swagger.json", "/debug", "/trace", "/actuator",
    "/solr/admin", "/manager/html", "/.DS_Store", "/server-status",
    "/wp-content/uploads", "/cgi-bin/", "/shell", "/cmd",
}


def _get_cf_auth() -> tuple[str, str]:
    """Get Cloudflare credentials from env or pass."""
    email = os.getenv("CF_AUTH_EMAIL", "")
    key = os.getenv("CF_AUTH_KEY", "")
    if not email or not key:
        # Try loading from pass via subprocess
        import subprocess
        try:
            email = subprocess.run(
                ["pass", "show", "verifieddit/CLOUDFLARE_AUTH_EMAIL"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            key = subprocess.run(
                ["pass", "show", "verifieddit/CLOUDFLARE_API_KEY"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return email, key


def get_zones() -> dict[str, str]:
    """Return monitored zones as {domain: zone_id}.

    In NEST mode, only thephenom.app is monitored.
    """
    if os.getenv("NEST_MODE", "").lower() in ("true", "1", "yes"):
        zone_id = os.getenv("NEST_ZONE_ID", "637c0036b564b56f7257815b23bd2e17")
        return {"thephenom.app": zone_id}

    raw = os.getenv("GHOSTMODE_CF_ZONES", "")
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return dict(_DEFAULT_ZONES)


def fetch_security_events(
    hours_back: float = 6,
    limit_per_zone: int = 20,
    zones: Optional[dict[str, str]] = None,
) -> list[dict]:
    """Fetch firewall events from all monitored Cloudflare zones.

    Returns a flat list of events sorted by datetime (newest first),
    enriched with domain name and threat classification.
    """
    email, key = _get_cf_auth()
    if not email or not key:
        return [{"error": "Cloudflare credentials not configured"}]

    zones = zones or get_zones()
    zone_ids = list(zones.values())

    now = datetime.now(timezone.utc)

    # For ranges >23h, serve from persistent store (PostgreSQL).
    # The store is populated by the hourly collector (collect_and_store).
    if hours_back > 23:
        try:
            from ghostmode.event_store import query_events
            return query_events(hours_back=hours_back, limit=limit_per_zone * len(zone_ids))
        except Exception as e:
            logger.warning("Event store unavailable, falling back to CF API (capped 23h): %s", e)
            hours_back = 23  # fallback

    # Cloudflare free plan: max 23h window per query
    since = (now - timedelta(hours=min(hours_back, 23))).strftime("%Y-%m-%dT%H:%M:%SZ")
    until = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    all_events: list[dict] = []
    zone_filter = json.dumps(zone_ids)

    query = f"""{{
      viewer {{
        zones(filter: {{zoneTag_in: {zone_filter}}}) {{
          zoneTag
          firewallEventsAdaptive(
            filter: {{datetime_gt: "{since}", datetime_lt: "{until}"}},
            limit: {limit_per_zone},
            orderBy: [datetime_DESC]
          ) {{
            action
            clientIP
            clientRequestHTTPHost
            clientRequestPath
            clientRequestHTTPMethodName
            datetime
            source
            userAgent
            clientCountryName
            clientASNDescription
          }}
        }}
      }}
    }}"""

    try:
        resp = requests.post(
            _GRAPHQL_URL,
            headers={"X-Auth-Email": email, "X-Auth-Key": key, "Content-Type": "application/json"},
            json={"query": query},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error("Cloudflare API error: %s", e)
        return [{"error": f"Cloudflare API: {e}"}]

    if data.get("errors"):
        return [{"error": str(data["errors"])}]

    # Reverse-map zone IDs to domain names
    id_to_domain = {v: k for k, v in zones.items()}
    safe_ips = _get_safe_ips()

    for zone_data in data.get("data", {}).get("viewer", {}).get("zones", []):
        zone_tag = zone_data.get("zoneTag", "")
        domain = id_to_domain.get(zone_tag, zone_tag)

        for evt in zone_data.get("firewallEventsAdaptive", []):
            if evt.get("clientIP", "") in safe_ips:
                continue

            path = evt.get("clientRequestPath", "")
            is_recon = any(path.startswith(p) or path == p for p in RECON_PATHS)

            all_events.append({
                "timestamp": evt.get("datetime", ""),
                "domain": domain,
                "host": sanitize(evt.get("clientRequestHTTPHost", "")),
                "path": sanitize(path),
                "method": evt.get("clientRequestHTTPMethodName", ""),
                "action": evt.get("action", ""),
                "source": evt.get("source", ""),
                "client_ip": evt.get("clientIP", ""),
                "country": evt.get("clientCountryName", ""),
                "asn": sanitize(evt.get("clientASNDescription", "")),
                "user_agent": sanitize(evt.get("userAgent", "")),
                "is_recon": is_recon,
                "threat_level": _classify_threat(evt, is_recon),
            })

    # Sort by timestamp descending
    all_events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return all_events


def _classify_threat(evt: dict, is_recon: bool) -> str:
    """Classify threat level based on event characteristics."""
    action = evt.get("action", "")
    source = evt.get("source", "")

    if action == "block" and source == "firewallManaged":
        return "high"
    if is_recon:
        return "high"
    if action in ("block", "drop"):
        return "medium"
    if action == "managed_challenge":
        return "medium"
    if source == "botFight":
        return "low"
    return "info"


def correlate_ips(events: list[dict]) -> list[dict]:
    """Find IPs that appear across multiple domains — indicates targeted recon."""
    ip_domains: dict[str, set[str]] = {}
    ip_events: dict[str, list[dict]] = {}

    for evt in events:
        if evt.get("error"):
            continue
        ip = evt.get("client_ip", "")
        domain = evt.get("domain", "")
        if ip and domain:
            ip_domains.setdefault(ip, set()).add(domain)
            ip_events.setdefault(ip, []).append(evt)

    # Only return IPs hitting 2+ domains
    correlated = []
    for ip, domains in ip_domains.items():
        if len(domains) >= 2:
            correlated.append({
                "client_ip": ip,
                "domains": sorted(domains),
                "domain_count": len(domains),
                "event_count": len(ip_events[ip]),
                "country": ip_events[ip][0].get("country", ""),
                "asn": ip_events[ip][0].get("asn", ""),
                "events": ip_events[ip],
            })

    correlated.sort(key=lambda x: x["domain_count"], reverse=True)
    return correlated


def get_threat_summary(hours_back: float = 6) -> dict:
    """High-level threat summary across all monitored domains."""
    events = fetch_security_events(hours_back=hours_back, limit_per_zone=50)

    if events and events[0].get("error"):
        return {"error": events[0]["error"]}

    total = len(events)
    by_domain: dict[str, int] = {}
    by_action: dict[str, int] = {}
    by_threat: dict[str, int] = {}
    recon_count = 0
    unique_ips = set()

    for evt in events:
        d = evt.get("domain", "unknown")
        by_domain[d] = by_domain.get(d, 0) + 1
        a = evt.get("action", "unknown")
        by_action[a] = by_action.get(a, 0) + 1
        t = evt.get("threat_level", "info")
        by_threat[t] = by_threat.get(t, 0) + 1
        if evt.get("is_recon"):
            recon_count += 1
        unique_ips.add(evt.get("client_ip", ""))

    correlated = correlate_ips(events)

    return {
        "period_hours": hours_back,
        "total_events": total,
        "unique_ips": len(unique_ips),
        "recon_attempts": recon_count,
        "cross_domain_actors": len(correlated),
        "by_domain": by_domain,
        "by_action": by_action,
        "by_threat_level": by_threat,
        "correlated_ips": correlated[:10],
        "events": events,
    }


def collect_and_store() -> int:
    """Fetch latest events from Cloudflare and persist to the event store.

    Called hourly by the background collector. Fetches 23h of events
    (the max CF allows) and upserts into PostgreSQL. The UNIQUE constraint
    on (timestamp, client_ip, domain, path) deduplicates overlapping windows.
    """
    events = fetch_security_events(hours_back=23, limit_per_zone=100)
    if not events or (events and events[0].get("error")):
        logger.warning("collect_and_store: no events or error")
        return 0
    try:
        from ghostmode.event_store import store_events
        return store_events(events)
    except Exception as e:
        logger.error("collect_and_store failed: %s", e)
        return 0
