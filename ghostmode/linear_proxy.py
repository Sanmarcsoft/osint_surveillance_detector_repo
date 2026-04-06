"""Server-side Linear.app GraphQL client for the RSS ticker.

Fetches recent issues from a Linear workspace and returns them
as ticker-compatible items. Requires LINEAR_API_KEY env var.
Caches responses for 2 minutes.
"""
from __future__ import annotations

import time
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_LINEAR_GRAPHQL = "https://api.linear.app/graphql"

# Cache: cache_key -> (timestamp, items)
_cache: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL = 120  # 2 minutes


def fetch_issues(
    api_key: str,
    team: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """Fetch recent issues from Linear.

    Returns: {"ok": bool, "items": [...], "error": str|None}
    Each item: {"title": str, "link": str, "status": str, "priority": int}
    """
    if not api_key:
        return {"ok": False, "items": [], "error": "Linear not configured"}

    cache_key = f"{team}:{status}:{limit}"
    now = time.time()
    if cache_key in _cache and (now - _cache[cache_key][0]) < _CACHE_TTL:
        return {"ok": True, "items": _cache[cache_key][1]}

    # Build GraphQL filter
    filters = []
    if team:
        filters.append(f'team: {{ key: {{ eq: "{team}" }} }}')
    if status:
        filters.append(f'state: {{ name: {{ eq: "{status}" }} }}')

    filter_str = ", ".join(filters)
    filter_clause = f"filter: {{ {filter_str} }}" if filter_str else ""

    query = f"""{{
      issues(first: {limit}, {filter_clause} orderBy: updatedAt) {{
        nodes {{
          title
          url
          state {{ name }}
          priority
          identifier
          updatedAt
        }}
      }}
    }}"""

    try:
        resp = requests.post(
            _LINEAR_GRAPHQL,
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            json={"query": query},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error("Linear API error: %s", e)
        return {"ok": False, "items": [], "error": str(e)}

    if "errors" in data:
        return {"ok": False, "items": [], "error": str(data["errors"])}

    items = []
    for node in data.get("data", {}).get("issues", {}).get("nodes", []):
        items.append({
            "title": f"[{node.get('identifier', '')}] {node.get('title', '')}",
            "link": node.get("url", ""),
            "status": node.get("state", {}).get("name", ""),
            "priority": node.get("priority", 0),
        })

    _cache[cache_key] = (now, items)
    return {"ok": True, "items": items}
