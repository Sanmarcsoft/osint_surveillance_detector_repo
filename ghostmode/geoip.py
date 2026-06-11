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

# Cloudflare gives an accurate ISO-3166 alpha-2 country code per event
# (clientCountryName). Threat-map markers are plotted at the country centroid
# from this code rather than MaxMind IP geolocation, which mislocates many IPs
# (notably IPv6) to the generic US-center fallback. Country-level accuracy that
# matches the surveillance log. Values are (lat, lng) per ISO alpha-2.
COUNTRY_CENTROIDS = {
    "US": (39.8, -98.6), "CA": (56.1, -106.3), "MX": (23.6, -102.5), "BR": (-14.2, -51.9),
    "AR": (-38.4, -63.6), "CL": (-35.7, -71.5), "CO": (4.6, -74.3), "PE": (-9.2, -75.0),
    "VE": (6.4, -66.6), "EC": (-1.8, -78.2), "BO": (-16.3, -63.6), "PY": (-23.4, -58.4),
    "UY": (-32.5, -55.8), "GB": (54.0, -2.0), "IE": (53.4, -8.2), "FR": (46.6, 2.2),
    "DE": (51.2, 10.4), "NL": (52.1, 5.3), "BE": (50.5, 4.5), "LU": (49.8, 6.1),
    "ES": (40.5, -3.7), "PT": (39.4, -8.2), "IT": (41.9, 12.6), "CH": (46.8, 8.2),
    "AT": (47.5, 14.6), "SE": (60.1, 18.6), "NO": (60.5, 8.5), "FI": (61.9, 25.7),
    "DK": (56.3, 9.5), "PL": (51.9, 19.1), "CZ": (49.8, 15.5), "SK": (48.7, 19.7),
    "HU": (47.2, 19.5), "RO": (45.9, 25.0), "BG": (42.7, 25.5), "GR": (39.1, 21.8),
    "HR": (45.1, 15.2), "RS": (44.0, 21.0), "SI": (46.1, 14.8), "LT": (55.2, 23.9),
    "LV": (56.9, 24.6), "EE": (58.6, 25.0), "IS": (64.9, -19.0), "UA": (48.4, 31.2),
    "BY": (53.7, 27.95), "RU": (61.5, 105.3), "TR": (39.0, 35.2), "IL": (31.0, 34.9),
    "SA": (23.9, 45.1), "AE": (23.4, 53.8), "QA": (25.3, 51.2), "KW": (29.3, 47.5),
    "BH": (26.0, 50.6), "OM": (21.5, 55.9), "JO": (30.6, 36.2), "LB": (33.9, 35.9),
    "IR": (32.4, 53.7), "IQ": (33.2, 43.7), "IN": (20.6, 79.0), "PK": (30.4, 69.3),
    "BD": (23.7, 90.4), "LK": (7.9, 80.8), "NP": (28.4, 84.1), "CN": (35.9, 104.2),
    "HK": (22.3, 114.2), "TW": (23.7, 121.0), "JP": (36.2, 138.25), "KR": (35.9, 127.8),
    "SG": (1.35, 103.8), "MY": (4.2, 102.0), "TH": (15.9, 101.0), "VN": (14.1, 108.3),
    "ID": (-0.8, 113.9), "PH": (12.9, 121.8), "KH": (12.6, 104.9), "MM": (21.9, 95.96),
    "AU": (-25.3, 133.8), "NZ": (-40.9, 174.9), "ZA": (-30.6, 22.9), "NG": (9.1, 8.7),
    "EG": (26.8, 30.8), "KE": (-0.02, 37.9), "MA": (31.8, -7.1), "DZ": (28.0, 1.7),
    "TN": (33.9, 9.6), "ET": (9.1, 40.5), "GH": (7.95, -1.0), "TZ": (-6.4, 34.9),
}


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
    """Enrich surveillance events with map coordinates.

    Hybrid geolocation: use MaxMind's city-level lat/lng when it is trustworthy
    (its country agrees with Cloudflare's per-event country code), otherwise fall
    back to the Cloudflare country centroid. MaxMind mislocates many IPs (notably
    IPv6) to a generic US-center point; trusting it only when it agrees with
    Cloudflare keeps city-level precision where real and country-level accuracy
    everywhere else. Returns {ip, lat, lng, city, country, count, threat_level, domains}.
    """
    # Aggregate by IP, capturing Cloudflare's country code for each.
    ip_data: dict[str, dict] = {}
    for evt in events:
        ip = evt.get("client_ip", "")
        if not ip:
            continue
        d = ip_data.setdefault(ip, {"count": 0, "domains": set(), "threat_levels": [], "cf_cc": ""})
        d["count"] += 1
        d["domains"].add(evt.get("domain", ""))
        d["threat_levels"].append(evt.get("threat_level", "info"))
        if not d["cf_cc"] and evt.get("country"):
            d["cf_cc"] = evt["country"].upper()

    markers = []
    for ip, agg in ip_data.items():
        cf_cc = agg["cf_cc"]
        geo = geolocate_ip(ip)
        mm_ok = bool(geo and geo.get("lat") is not None)
        mm_cc = (geo.get("country_code") or "").upper() if geo else ""

        if mm_ok and (not cf_cc or mm_cc == cf_cc):
            # MaxMind agrees with Cloudflare (or CF has no country) -> trust city-level
            lat, lng, city, cc = geo["lat"], geo["lng"], geo.get("city", ""), (mm_cc or cf_cc)
        elif cf_cc in COUNTRY_CENTROIDS:
            # MaxMind disagrees or has nothing -> Cloudflare country centroid
            lat, lng, city, cc = COUNTRY_CENTROIDS[cf_cc][0], COUNTRY_CENTROIDS[cf_cc][1], "", cf_cc
        elif mm_ok:
            # CF country unknown/no centroid, but MaxMind has something -> last resort
            lat, lng, city, cc = geo["lat"], geo["lng"], geo.get("city", ""), mm_cc
        else:
            logger.debug("threat-map: no geo for ip=%s cf_cc=%r — skipped", ip, cf_cc)
            continue

        levels = agg["threat_levels"]
        threat = "high" if "high" in levels else "medium" if "medium" in levels else "low"
        markers.append({
            "ip": ip,
            "lat": lat,
            "lng": lng,
            "city": city,
            "country": cc,
            "count": agg["count"],
            "domains": sorted(agg["domains"]),
            "threat_level": threat,
        })

    return markers
