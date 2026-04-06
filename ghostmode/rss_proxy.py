"""Server-side RSS/Atom feed proxy to avoid CORS issues.

Fetches RSS/Atom feeds and returns parsed headlines as JSON.
Caches responses for 5 minutes to avoid hammering upstream feeds.
"""
from __future__ import annotations

import time
import logging
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)

# In-memory cache: url -> (timestamp, parsed_items)
_cache: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL = 300  # 5 minutes


def fetch_rss(url: str, max_items: int = 20) -> dict:
    """Fetch and parse an RSS/Atom feed URL.

    Returns: {"ok": bool, "url": str, "items": [...], "error": str|None}
    Each item: {"title": str, "link": str, "published": str}
    """
    if not url or not url.startswith(("http://", "https://")):
        return {"ok": False, "url": url, "items": [], "error": "Invalid URL"}

    now = time.time()
    if url in _cache and (now - _cache[url][0]) < _CACHE_TTL:
        return {"ok": True, "url": url, "items": _cache[url][1]}

    try:
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "NEST-Ops-RSS/1.0",
        })
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("RSS fetch failed for %s: %s", url, e)
        return {"ok": False, "url": url, "items": [], "error": str(e)}

    items = _parse_feed(resp.text, max_items)
    _cache[url] = (now, items)
    return {"ok": True, "url": url, "items": items}


def _parse_feed(xml_text: str, max_items: int) -> list[dict]:
    """Parse RSS 2.0 or Atom feed XML into headline items."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items: list[dict] = []

    # RSS 2.0: <rss><channel><item>
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if title:
            items.append({"title": title, "link": link, "published": pub})
        if len(items) >= max_items:
            break

    # Atom: <feed><entry>
    if not items:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall(".//atom:entry", ns) or list(root.iter("entry"))
        for entry in entries:
            title = ""
            link = ""
            pub = ""
            t = entry.find("atom:title", ns)
            if t is None:
                t = entry.find("title")
            if t is not None:
                title = (t.text or "").strip()
            l_el = entry.find("atom:link", ns)
            if l_el is None:
                l_el = entry.find("link")
            if l_el is not None:
                link = l_el.get("href", "")
            for tag in ("atom:published", "published", "atom:updated", "updated"):
                p = entry.find(tag, ns) if "atom:" in tag else entry.find(tag)
                if p is not None and p.text:
                    pub = p.text.strip()
                    break
            if title:
                items.append({"title": title, "link": link, "published": pub})
            if len(items) >= max_items:
                break

    return items
