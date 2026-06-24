"""Best-effort GreyNoise lookups used to suppress background-scanner noise.

A huge share of Cloudflare WAF/recon events come from internet-wide background
scanners that Cloudflare has already blocked (managed_challenge). GreyNoise sees
that same mass-scanning and classifies the source. We use it to decide whether a
single-domain blocked source is worth paging: only IPs GreyNoise classifies as
``malicious`` page; everything else (benign, RIOT business services, or unseen)
is treated as background noise and suppressed.

The GreyNoise Community API works keyless; an optional ``GREYNOISE_API_KEY`` env
raises the rate limit. Every lookup is best-effort: any failure (timeout, rate
limit, network) returns a neutral result so the caller fails QUIET — genuine
targeting still pages via the cross-domain correlation path, which does not
depend on GreyNoise at all.
"""
from __future__ import annotations

import os
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_COMMUNITY_URL = "https://api.greynoise.io/v3/community/{}"
_TIMEOUT = float(os.getenv("GREYNOISE_TIMEOUT", "3.0"))

# Process-lifetime cache: classifications change slowly and one scan can repeat
# the same IP many times. None means "look it up".
_cache: dict[str, dict] = {}


def _neutral(ip: str) -> dict:
    return {"ip": ip, "classification": "unknown", "noise": False,
            "riot": False, "name": "", "ok": False}


def lookup(ip: str) -> dict:
    """Return GreyNoise's view of ``ip``. Never raises; neutral on any failure."""
    if not ip or ip == "?":
        return _neutral(ip)
    cached = _cache.get(ip)
    if cached is not None:
        return cached

    result = _neutral(ip)
    headers = {"accept": "application/json"}
    key = os.getenv("GREYNOISE_API_KEY")
    if key:
        headers["key"] = key
    try:
        resp = requests.get(_COMMUNITY_URL.format(ip), headers=headers, timeout=_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            result.update(
                classification=data.get("classification", "unknown"),
                noise=bool(data.get("noise")),
                riot=bool(data.get("riot")),
                name=data.get("name", ""),
                ok=True,
            )
        elif resp.status_code == 404:
            # Not observed by GreyNoise — a real lookup, just no data. Unknown.
            result["ok"] = True
        else:
            logger.debug("greynoise %s → HTTP %s", ip, resp.status_code)
    except requests.RequestException as e:
        logger.debug("greynoise lookup failed for %s: %s", ip, e)

    _cache[ip] = result
    return result


def is_malicious(ip: str) -> bool:
    """True only when GreyNoise positively classifies the IP as malicious.

    Conservative by design: a neutral/failed lookup is NOT malicious, so a
    GreyNoise outage suppresses single-domain background noise rather than
    re-opening the flood. Cross-domain targeting pages independently.
    """
    return lookup(ip).get("classification") == "malicious"
