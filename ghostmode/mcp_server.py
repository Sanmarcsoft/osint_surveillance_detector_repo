"""FastMCP server with interactive dashboard, JSON API, /health, and /metrics.

Endpoints:
  - GET /            — Interactive HTML dashboard for humans
  - GET /health      — JSON health check (HTTP 200 or 503)
  - GET /metrics     — Prometheus metrics for ops.sanmarcsoft.com
  - POST /mcp        — MCP protocol endpoint for AI agents
  - GET /api/logs    — Query honeypot logs (JSON)
  - POST /api/alert-test  — Send test alert (JSON)
  - GET /api/config-validate — Validate config (JSON)
  - GET /api/docs    — Search knowledge base (JSON)
"""

import json
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
    mcp._ghostmode_port = port

    # ---- MCP Tools (for AI agents) ----

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

    @mcp.tool()
    def ghostmode_surveillance_scan(hours_back: float = 6) -> dict:
        """Scan all monitored domains for surveillance activity. Returns threat summary with cross-domain correlation, recon attempts, and classified events from sanmarcsoft.com, thephenom.app, verifieddit.com, trusteddit.com."""
        prom.mcp_calls.labels(tool="ghostmode_surveillance_scan").inc()
        start = time.monotonic()
        from ghostmode.cloudflare_monitor import get_threat_summary
        result = get_threat_summary(hours_back=hours_back)
        prom.mcp_latency.labels(tool="ghostmode_surveillance_scan").observe(time.monotonic() - start)
        return result

    @mcp.tool()
    def ghostmode_correlated_threats(hours_back: float = 12) -> dict:
        """Find IPs probing multiple domains — indicates targeted reconnaissance campaigns against the portfolio."""
        prom.mcp_calls.labels(tool="ghostmode_correlated_threats").inc()
        from ghostmode.cloudflare_monitor import fetch_security_events, correlate_ips
        events = fetch_security_events(hours_back=hours_back, limit_per_zone=50)
        correlated = correlate_ips(events)
        return {"cross_domain_actors": len(correlated), "threats": correlated}

    # ---- HTTP endpoints for humans and ops ----

    @mcp.custom_route("/", methods=["GET"])
    async def dashboard(request):
        from starlette.responses import HTMLResponse
        from ghostmode.dashboard import build_dashboard
        return HTMLResponse(build_dashboard())

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

    # ---- JSON API for dashboard interactivity ----

    @mcp.custom_route("/api/logs", methods=["GET"])
    async def api_logs(request):
        from starlette.responses import JSONResponse
        cfg = load_config()
        params = request.query_params
        events = query_logs(
            cfg["opencanary_log"],
            service=params.get("service") or None,
            src_host=params.get("src_host") or None,
            since=params.get("since") or None,
            limit=int(params.get("limit", "50")),
        )
        return JSONResponse({"count": len(events), "events": events})

    @mcp.custom_route("/api/alert-test", methods=["POST"])
    async def api_alert_test(request):
        from starlette.responses import JSONResponse
        cfg = load_config()
        result = send_ntfy(
            "Ghost Mode dashboard test alert",
            server=cfg["ntfy_server"],
            topic=cfg["ntfy_topic"],
            user=cfg["ntfy_user"],
            password=cfg["ntfy_pass"],
        )
        return JSONResponse(result.to_dict())

    @mcp.custom_route("/api/config-validate", methods=["GET"])
    async def api_config_validate(request):
        from starlette.responses import JSONResponse
        return JSONResponse(validate_config())

    @mcp.custom_route("/api/docs", methods=["GET"])
    async def api_docs_search(request):
        from starlette.responses import JSONResponse
        q = request.query_params.get("q", "")
        if not q:
            return JSONResponse({"error": "Missing ?q= parameter"}, status_code=400)
        try:
            from ghostmode.docs import query_docs
            cfg = load_config()
            result = query_docs(q, n_results=5, host=cfg["chromadb_host"], port=cfg["chromadb_port"])
            return JSONResponse(result)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @mcp.custom_route("/api/surveillance", methods=["GET"])
    async def api_surveillance(request):
        from starlette.responses import JSONResponse
        from ghostmode.cloudflare_monitor import get_threat_summary
        hours = float(request.query_params.get("hours", "6"))
        return JSONResponse(get_threat_summary(hours_back=hours))

    @mcp.custom_route("/api/correlated", methods=["GET"])
    async def api_correlated(request):
        from starlette.responses import JSONResponse
        from ghostmode.cloudflare_monitor import fetch_security_events, correlate_ips
        hours = float(request.query_params.get("hours", "12"))
        events = fetch_security_events(hours_back=hours, limit_per_zone=50)
        correlated = correlate_ips(events)
        return JSONResponse({"cross_domain_actors": len(correlated), "threats": correlated})

    @mcp.custom_route("/api/threat-map", methods=["GET"])
    async def api_threat_map(request):
        from starlette.responses import JSONResponse
        from ghostmode.cloudflare_monitor import fetch_security_events
        from ghostmode.geoip import geolocate_events
        hours = float(request.query_params.get("hours", "6"))
        events = fetch_security_events(hours_back=hours, limit_per_zone=50)
        markers = geolocate_events(events)
        return JSONResponse({"count": len(markers), "markers": markers})

    return mcp
