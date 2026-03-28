"""FastMCP server with /health and /metrics endpoints.

Exposes all ghostmode tools as MCP tools. Also serves:
  - GET /health  — JSON health check (HTTP 200 or 503)
  - GET /metrics — Prometheus metrics for ops.sanmarcsoft.com
"""

import time
from typing import Optional

from fastmcp import FastMCP
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from ghostmode.config import load_config, validate_config
from ghostmode.status import get_status
from ghostmode.alert import send_ntfy
from ghostmode.logs import query_logs
from ghostmode import metrics as prom


def create_server(port: int = 3200) -> FastMCP:
    mcp = FastMCP("ghostmode")
    mcp._ghostmode_port = port  # stored for use by the serve CLI command

    @mcp.tool()
    def ghostmode_status() -> dict:
        """Check health of all Ghost Mode services. Returns service status, uptime, and alert counts."""
        prom.mcp_calls.labels(tool="ghostmode_status").inc()
        start = time.monotonic()
        cfg = load_config()
        result = get_status(
            ntfy_server=cfg["ntfy_server"],
            ntfy_topic=cfg["ntfy_topic"],
            canary_log=cfg["opencanary_log"],
        )
        prom.mcp_latency.labels(tool="ghostmode_status").observe(time.monotonic() - start)
        return result

    @mcp.tool()
    def ghostmode_alert_test(message: str = "Ghost Mode MCP test alert") -> dict:
        """Send a test alert via ntfy. Returns delivery status."""
        prom.mcp_calls.labels(tool="ghostmode_alert_test").inc()
        cfg = load_config()
        result = send_ntfy(message, server=cfg["ntfy_server"], topic=cfg["ntfy_topic"],
                           user=cfg["ntfy_user"], password=cfg["ntfy_pass"])
        return result.to_dict()

    @mcp.tool()
    def ghostmode_config_validate() -> dict:
        """Validate all Ghost Mode configuration. Returns issues list."""
        prom.mcp_calls.labels(tool="ghostmode_config_validate").inc()
        return validate_config()

    @mcp.tool()
    def ghostmode_logs_query(
        service: Optional[str] = None,
        src_host: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 50,
    ) -> dict:
        """Query structured OpenCanary honeypot logs. Filter by service, source IP, or timestamp."""
        prom.mcp_calls.labels(tool="ghostmode_logs_query").inc()
        start = time.monotonic()
        cfg = load_config()
        events = query_logs(cfg["opencanary_log"], service=service, src_host=src_host,
                            since=since, limit=limit)
        prom.mcp_latency.labels(tool="ghostmode_logs_query").observe(time.monotonic() - start)
        return {"count": len(events), "events": events}

    @mcp.tool()
    def ghostmode_alerts_list(
        since: Optional[str] = None,
        limit: int = 50,
        service: Optional[str] = None,
    ) -> dict:
        """List recent honeypot alert events. Filter by timestamp or service."""
        prom.mcp_calls.labels(tool="ghostmode_alerts_list").inc()
        cfg = load_config()
        events = query_logs(cfg["opencanary_log"], service=service, since=since, limit=limit)
        return {"count": len(events), "events": events}

    @mcp.tool()
    def ghostmode_watch_events(limit: int = 10, since: Optional[str] = None) -> dict:
        """Get recent honeypot events from the log (non-streaming)."""
        prom.mcp_calls.labels(tool="ghostmode_watch_events").inc()
        cfg = load_config()
        events = query_logs(cfg["opencanary_log"], since=since, limit=limit)
        return {"count": len(events), "events": events}

    @mcp.tool()
    def ghostmode_docs_query(query: str, n_results: int = 5, doc_type: Optional[str] = None) -> dict:
        """Search the Ghost Mode agent knowledge base in ChromaDB."""
        prom.mcp_calls.labels(tool="ghostmode_docs_query").inc()
        from ghostmode.docs import query_docs
        return query_docs(query, n_results=n_results, doc_type=doc_type)

    return mcp
