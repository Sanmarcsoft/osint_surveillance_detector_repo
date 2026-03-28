"""MaxMind GeoLite2 IP geolocation for threat mapping.

Uses the MaxMind GeoLite2 web API (no local database needed).
Credentials from MAXMIND_ACCOUNT_ID / MAXMIND_LICENSE_KEY env vars
or pass store at sanmarcsoft/maxmind/.
"""
from __future__ import annotations

import os
import logging
import subprocess
from functools import lru_cache
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_API_URL = "https://geolite.info/geoip/v2.1/city"


def _get_maxmind_auth() -> tuple[str, str]:
    account = os.getenv("MAXMIND_ACCOUNT_ID", "")
    key = os.getenv("MAXMIND_LICENSE_KEY", "")
    if not account or not key:
        try:
            account = subprocess.run(
                ["pass", "show", "sanmarcsoft/maxmind/account-id"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            key = subprocess.run(
                ["pass", "show", "sanmarcsoft/maxmind/license-key"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return account, key


@lru_cache(maxsize=1024)
def geolocate_ip(ip: str) -> Optional[dict]:
    """Look up lat/lng/city/country for an IP address. Results are cached."""
    account, key = _get_maxmind_auth()
    if not account or not key:
        return None

    try:
        resp = requests.get(f"{_API_URL}/{ip}", auth=(account, key), timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
        loc = data.get("location", {})
        return {
            "ip": ip,
            "lat": loc.get("latitude"),
            "lng": loc.get("longitude"),
            "city": data.get("city", {}).get("names", {}).get("en", ""),
            "country": data.get("country", {}).get("names", {}).get("en", ""),
            "country_code": data.get("country", {}).get("iso_code", ""),
        }
    except requests.RequestException as e:
        logger.debug("GeoIP lookup failed for %s: %s", ip, e)
        return None


def geolocate_events(events: list[dict]) -> list[dict]:
    """Enrich a list of surveillance events with lat/lng coordinates.

    Deduplicates IPs before lookup to minimize API calls.
    Returns list of {ip, lat, lng, city, country, count, threat_level, domains}.
    """
    # Aggregate by IP
    ip_data: dict[str, dict] = {}
    for evt in events:
        ip = evt.get("client_ip", "")
        if not ip:
            continue
        if ip not in ip_data:
            ip_data[ip] = {
                "count": 0,
                "domains": set(),
                "threat_levels": [],
            }
        ip_data[ip]["count"] += 1
        ip_data[ip]["domains"].add(evt.get("domain", ""))
        ip_data[ip]["threat_levels"].append(evt.get("threat_level", "info"))

    # Geolocate unique IPs
    markers = []
    for ip, agg in ip_data.items():
        geo = geolocate_ip(ip)
        if not geo or not geo.get("lat"):
            continue

        # Highest threat level wins
        levels = agg["threat_levels"]
        if "high" in levels:
            threat = "high"
        elif "medium" in levels:
            threat = "medium"
        else:
            threat = "low"

        markers.append({
            "ip": ip,
            "lat": geo["lat"],
            "lng": geo["lng"],
            "city": geo["city"],
            "country": geo["country"],
            "count": agg["count"],
            "domains": sorted(agg["domains"]),
            "threat_level": threat,
        })

    return markers
