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

    # Clamp limit to a sane integer range (osint #26)
    try:
        limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        limit = 20

    cache_key = f"{team}:{status}:{limit}"
    now = time.time()
    if cache_key in _cache and (now - _cache[cache_key][0]) < _CACHE_TTL:
        return {"ok": True, "items": _cache[cache_key][1]}

    # User-controlled values travel as GraphQL VARIABLES, never interpolated
    # into the query document (osint #26 — GraphQL injection).
    variables: dict = {"first": limit}
    issue_filter: dict = {}
    if team:
        issue_filter["team"] = {"key": {"eq": team}}
    if status:
        issue_filter["state"] = {"name": {"eq": status}}
    if issue_filter:
        variables["filter"] = issue_filter

    query = """query Ticker($first: Int!, $filter: IssueFilter) {
      issues(first: $first, filter: $filter, orderBy: updatedAt) {
        nodes {
          title
          url
          state { name }
          priority
          identifier
          updatedAt
        }
      }
    }"""

    try:
        resp = requests.post(
            _LINEAR_GRAPHQL,
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            json={"query": query, "variables": variables},
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
