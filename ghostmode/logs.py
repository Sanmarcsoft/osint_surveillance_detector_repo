"""Structured log querying for OpenCanary JSON-lines log files."""

from typing import Optional

from ghostmode.watch import parse_event


def query_logs(
    path: str,
    service: Optional[str] = None,
    src_host: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """Query OpenCanary log file with filters. Returns list of event dicts."""
    results = []
    try:
        with open(path, "r") as f:
            for line in f:
                evt = parse_event(line)
                if evt is None:
                    continue
                if service and evt.service != service:
                    continue
                if src_host and evt.src_host != src_host:
                    continue
                if since and evt.timestamp < since:
                    continue
                results.append(evt.to_dict())
                if len(results) >= limit:
                    break
    except FileNotFoundError:
        pass
    return results
