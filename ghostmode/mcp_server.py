"""FastMCP server with human dashboard, /health, and /metrics endpoints.

Exposes all ghostmode tools as MCP tools. Also serves:
  - GET /         — Human-readable status dashboard (HTML)
  - GET /health   — JSON health check (HTTP 200 or 503)
  - GET /metrics  — Prometheus metrics for ops.sanmarcsoft.com
  - POST /mcp     — MCP protocol endpoint for AI agents
"""

import json
import time
from datetime import datetime, timezone
from typing import Optional

from fastmcp import FastMCP
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from ghostmode import __version__
from ghostmode.config import load_config, validate_config
from ghostmode.status import get_status
from ghostmode.alert import send_ntfy
from ghostmode.logs import query_logs
from ghostmode import metrics as prom

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ghost Mode — crabkey.sanmarcsoft.com</title>
<style>
  :root { --bg: #0a0a0a; --card: #141414; --border: #2a2a2a; --text: #e0e0e0;
          --dim: #666; --green: #4ade80; --red: #f87171; --yellow: #fbbf24;
          --blue: #60a5fa; --mono: 'SF Mono', 'Cascadia Code', monospace; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: var(--bg); color: var(--text); font-family: var(--mono);
         font-size: 14px; line-height: 1.6; padding: 2rem; max-width: 900px; margin: 0 auto; }
  h1 { font-size: 1.4rem; margin-bottom: 0.5rem; }
  .subtitle { color: var(--dim); margin-bottom: 2rem; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 2rem; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1.2rem; }
  .card h2 { font-size: 0.85rem; color: var(--dim); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.8rem; }
  .status-row { display: flex; justify-content: space-between; align-items: center; padding: 0.3rem 0; }
  .status-row .label { color: var(--dim); }
  .badge { padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
  .badge.up { background: #0a2e1a; color: var(--green); }
  .badge.down { background: #2e0a0a; color: var(--red); }
  .badge.warn { background: #2e2a0a; color: var(--yellow); }
  .tools-list { list-style: none; }
  .tools-list li { padding: 0.3rem 0; border-bottom: 1px solid var(--border); }
  .tools-list li:last-child { border-bottom: none; }
  .tool-name { color: var(--blue); }
  .endpoints { margin-top: 1rem; }
  .endpoints code { background: var(--card); border: 1px solid var(--border); padding: 2px 6px; border-radius: 3px; }
  .footer { color: var(--dim); font-size: 0.8rem; margin-top: 2rem; text-align: center; }
  a { color: var(--blue); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .full-width { grid-column: 1 / -1; }
  @media (max-width: 600px) { .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<h1>Ghost Mode</h1>
<p class="subtitle">crabkey.sanmarcsoft.com &mdash; OSINT Honeypot + AI Agent Platform v{version}</p>

<div class="grid">
  <div class="card">
    <h2>Services</h2>
    {services_html}
  </div>
  <div class="card">
    <h2>System</h2>
    <div class="status-row"><span class="label">Uptime</span><span>{uptime}</span></div>
    <div class="status-row"><span class="label">Version</span><span>{version}</span></div>
    <div class="status-row"><span class="label">Checked</span><span>{timestamp}</span></div>
  </div>
  <div class="card">
    <h2>Config</h2>
    {config_html}
  </div>
  <div class="card">
    <h2>MCP Tools</h2>
    <ul class="tools-list">
      <li><span class="tool-name">ghostmode_status</span></li>
      <li><span class="tool-name">ghostmode_alert_test</span></li>
      <li><span class="tool-name">ghostmode_config_validate</span></li>
      <li><span class="tool-name">ghostmode_logs_query</span></li>
      <li><span class="tool-name">ghostmode_alerts_list</span></li>
      <li><span class="tool-name">ghostmode_watch_events</span></li>
      <li><span class="tool-name">ghostmode_docs_query</span></li>
    </ul>
  </div>
  <div class="card full-width">
    <h2>Endpoints</h2>
    <div class="endpoints">
      <div class="status-row"><span class="label">Dashboard</span><code>GET /</code></div>
      <div class="status-row"><span class="label">MCP (agents)</span><code>POST /mcp</code></div>
      <div class="status-row"><span class="label">Health probe</span><code>GET /health</code></div>
      <div class="status-row"><span class="label">Prometheus</span><code>GET /metrics</code></div>
    </div>
  </div>
</div>

<div class="footer">
  Ghost Mode &mdash; <a href="https://github.com/Sanmarcsoft/osint_surveillance_detector_repo">GitHub</a>
  &middot; Monitored by <a href="https://ops.sanmarcsoft.com">ops.sanmarcsoft.com</a>
</div>
</body>
</html>"""


def _format_uptime(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.0f}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def _build_dashboard() -> str:
    cfg = load_config()
    status_data = get_status(
        ntfy_server=cfg["ntfy_server"],
        ntfy_topic=cfg["ntfy_topic"],
        canary_log=cfg["opencanary_log"],
    )

    # Services HTML
    services_rows = []
    for svc_data in status_data["services"].values():
        name = svc_data["name"]
        status = svc_data["status"]
        if status in ("reachable", "running"):
            badge = '<span class="badge up">UP</span>'
        else:
            badge = f'<span class="badge down">{status}</span>'
        services_rows.append(f'<div class="status-row"><span class="label">{name}</span>{badge}</div>')
    # MCP server is always up if we're serving this page
    services_rows.append('<div class="status-row"><span class="label">mcp_server</span><span class="badge up">UP</span></div>')

    # Config HTML
    config_result = validate_config()
    if config_result["ok"] and not config_result["issues"]:
        config_html = '<div class="status-row"><span class="label">Status</span><span class="badge up">OK</span></div>'
    else:
        config_rows = []
        for issue in config_result["issues"]:
            cls = "warn" if issue["severity"] == "warning" else "down"
            config_rows.append(f'<div class="status-row"><span class="label">{issue["key"]}</span><span class="badge {cls}">{issue["severity"]}</span></div>')
        config_html = "\n".join(config_rows) if config_rows else '<div class="status-row"><span class="badge up">OK</span></div>'

    return _DASHBOARD_HTML.format(
        version=__version__,
        services_html="\n".join(services_rows),
        uptime=_format_uptime(status_data["uptime_seconds"]),
        timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
        config_html=config_html,
    )


def create_server(port: int = 3200) -> FastMCP:
    mcp = FastMCP("ghostmode")
    mcp._ghostmode_port = port

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

    # --- HTTP endpoints for humans and ops ---

    @mcp.custom_route("/", methods=["GET"])
    async def dashboard(request):
        from starlette.responses import HTMLResponse
        return HTMLResponse(_build_dashboard())

    @mcp.custom_route("/health", methods=["GET"])
    async def health_endpoint(request):
        from starlette.responses import JSONResponse
        cfg = load_config()
        status_data = get_status(
            ntfy_server=cfg["ntfy_server"],
            ntfy_topic=cfg["ntfy_topic"],
            canary_log=cfg["opencanary_log"],
        )
        all_up = all(
            s.get("status") in ("reachable", "running")
            for s in status_data["services"].values()
        )
        code = 200 if all_up else 503
        return JSONResponse({"ok": all_up, "command": "health", "data": status_data}, status_code=code)

    @mcp.custom_route("/metrics", methods=["GET"])
    async def metrics_endpoint(request):
        from starlette.responses import Response
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return mcp
