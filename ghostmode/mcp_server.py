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
import threading
import logging
from typing import Optional

from fastmcp import FastMCP
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from ghostmode.config import load_config, validate_config
from ghostmode.status import get_status
from ghostmode.alert import send_ntfy
from ghostmode.logs import query_logs
from ghostmode import metrics as prom

logger = logging.getLogger(__name__)


def _start_event_collector(interval_seconds: int = 3600):
    """Background thread that fetches CF events hourly and stores them."""
    def _collector_loop():
        # Wait 30s after startup before first collection
        time.sleep(30)
        while True:
            try:
                from ghostmode.cloudflare_monitor import collect_and_store
                count = collect_and_store()
                logger.info("Event collector: stored %d new events", count)
            except Exception as e:
                logger.error("Event collector failed: %s", e)
            time.sleep(interval_seconds)

    t = threading.Thread(target=_collector_loop, daemon=True, name="event-collector")
    t.start()
    logger.info("Event collector started (interval=%ds)", interval_seconds)


def _start_surveillance_scanner(interval_seconds: int = 300):
    """Background thread: evaluate recent CF threat events on a clock and alert.

    The hourly event collector only warehouses events; nothing fired surveillance
    alerts on a schedule (process_surveillance_alerts ran only from the MCP tool).
    This loop closes that gap. Lookback == interval so each event is evaluated
    about once; alerter.should_alert's IP+action cooldown dedups any overlap.
    """
    lookback_hours = interval_seconds / 3600.0

    heartbeat_every = max(1, int(86400 / interval_seconds))  # ~ once a day

    def _loop():
        time.sleep(45)  # stagger after the collector + asset-monitor warmups
        logger.info("Surveillance scanner started (interval=%ds, lookback=%.3fh)",
                    interval_seconds, lookback_hours)
        from ghostmode.alerter import process_surveillance_alerts, heartbeat
        i = 0
        while True:
            try:
                from ghostmode.cloudflare_monitor import get_threat_summary
                result = get_threat_summary(hours_back=lookback_hours)
                if result.get("error"):
                    logger.warning("Surveillance scan error: %s", result["error"])
                else:
                    # First scan primes the dedup (no pages) so a restart can't
                    # replay the active backlog as an alert storm.
                    sent = process_surveillance_alerts(
                        result.get("events", []), result.get("correlated_ips", []),
                        prime=(i == 0))
                    if sent:
                        logger.info("Surveillance scan: %d alert(s) published", sent)
                # Heartbeat shortly after startup, then ~daily, so a SILENT pipeline
                # is detectable (a missing "all clear" is itself the signal).
                if i == 1 or (i > 0 and i % heartbeat_every == 0):
                    heartbeat()
            except Exception as e:
                logger.error("Surveillance scan failed: %s", e)
            i += 1
            time.sleep(interval_seconds)

    t = threading.Thread(target=_loop, daemon=True, name="surveillance-scanner")
    t.start()
    logger.info("Surveillance scanner started (interval=%ds)", interval_seconds)


def _is_truthy(val: str) -> bool:
    return (val or "").strip().lower() in ("1", "true", "yes", "on")


def _bearer_token(headers) -> str:
    """Extract a Bearer token from an Authorization header value."""
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _token_matches(presented: str, expected: str) -> bool:
    """Constant-time token comparison. Unset/empty expected NEVER matches."""
    import hmac
    if not expected or not presented:
        return False
    return hmac.compare_digest(presented, expected)


class GhostmodeAuthMiddleware:
    """Fail-closed auth on EVERY route (osint #22, #28).

    Policy:
    - /health           anonymous (ALB target-group health checks)
    - /metrics          Bearer GHOSTMODE_METRICS_TOKEN (Prometheus scrape)
    - /mcp*             Bearer GHOSTMODE_MCP_TOKEN (AI agents)
    - everything else   verified x-amzn-oidc-data identity (ES256 signature
                        checked against the ALB regional public key)
    - GHOSTMODE_DEV_NO_AUTH=1 disables enforcement (explicit local-dev only)

    Default is DENY: a route not matching an allow rule returns 401.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import os
        from starlette.datastructures import Headers
        from starlette.responses import JSONResponse
        from ghostmode import alb_auth

        if _is_truthy(os.getenv("GHOSTMODE_DEV_NO_AUTH", "")):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        headers = Headers(scope=scope)

        if path == "/health":
            await self.app(scope, receive, send)
            return

        if path == "/metrics":
            if _token_matches(_bearer_token(headers),
                              os.getenv("GHOSTMODE_METRICS_TOKEN", "")):
                await self.app(scope, receive, send)
                return
            await JSONResponse({"error": "unauthorized"}, status_code=401)(
                scope, receive, send)
            return

        if path == "/mcp" or path.startswith("/mcp/"):
            if _token_matches(_bearer_token(headers),
                              os.getenv("GHOSTMODE_MCP_TOKEN", "")):
                await self.app(scope, receive, send)
                return
            await JSONResponse({"error": "unauthorized"}, status_code=401)(
                scope, receive, send)
            return

        # Everything else requires a verified ALB OIDC identity.
        claims = alb_auth.verify_alb_jwt(headers.get("x-amzn-oidc-data", ""))
        if claims is None:
            await JSONResponse({"error": "unauthorized"}, status_code=401)(
                scope, receive, send)
            return

        scope.setdefault("state", {})["oidc_claims"] = claims
        await self.app(scope, receive, send)


def create_server(port: int = 3200) -> FastMCP:
    mcp = FastMCP("ghostmode")
    mcp._ghostmode_port = port

    # Fail-closed auth on every HTTP route + the MCP mount (osint #22, #28).
    # run_http_async() and tests both build the app via http_app(), so an
    # instance-level wrapper guarantees the middleware is always applied.
    from starlette.middleware import Middleware
    _original_http_app = mcp.http_app

    def _http_app_with_auth(*args, **kwargs):
        middleware = list(kwargs.pop("middleware", None) or [])
        middleware.insert(0, Middleware(GhostmodeAuthMiddleware))
        return _original_http_app(*args, middleware=middleware, **kwargs)

    mcp.http_app = _http_app_with_auth

    # Start background event collector (hourly CF → PostgreSQL)
    # Table auto-creates via _ensure_schema() on first query/insert
    _start_event_collector(interval_seconds=3600)

    # Start the asset-down monitor: probes the Ops board assets on an interval
    # and pages the per-asset ntfy topic on an up->down transition (+ recovery).
    from ghostmode.asset_monitor import start_asset_monitor
    start_asset_monitor()

    # Scheduled surveillance scan (~5 min) — fires threat-event alerts on a clock.
    _start_surveillance_scanner(interval_seconds=300)

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
    def ghostmode_docs_query(query: str, n_results: int = 5, doc_type: Optional[str] = None) -> dict:
        """Search the Ghost Mode agent knowledge base in ChromaDB."""
        prom.mcp_calls.labels(tool="ghostmode_docs_query").inc()
        from ghostmode.docs import query_docs
        return query_docs(query, n_results=n_results, doc_type=doc_type)

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
    def ghostmode_surveillance_scan(hours_back: float = 6) -> dict:
        """Scan all monitored domains for surveillance activity. Returns threat summary with cross-domain correlation, recon attempts, and classified events from sanmarcsoft.com, thephenom.app, verifieddit.com, trusteddit.com. Sends push alerts for high-severity events."""
        prom.mcp_calls.labels(tool="ghostmode_surveillance_scan").inc()
        start = time.monotonic()
        from ghostmode.cloudflare_monitor import get_threat_summary
        from ghostmode.alerter import process_surveillance_alerts
        result = get_threat_summary(hours_back=hours_back)
        if not result.get("error"):
            alerts_sent = process_surveillance_alerts(
                result.get("events", []),
                result.get("correlated_ips", []),
            )
            result["alerts_sent"] = alerts_sent
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

    # osint #24: CSP for every HTML render. Inline scripts/handlers are part
    # of the dashboard design, so 'unsafe-inline' stays — escaping at render
    # is the primary XSS defense; CSP blocks remote script/object injection.
    _CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; "
        "font-src https://fonts.gstatic.com; "
        # chat.thephenom.app: Matrix profile avatars (osint #43) — the wrapper
        # fetches /profile/{mxid}/avatar_url and renders the /download media.
        "img-src 'self' data: https://*.basemaps.cartocdn.com https://unpkg.com https://chat.thephenom.app; "
        "connect-src 'self' https://chat.thephenom.app; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'self'; "
        "form-action 'self'"
    )

    def _html_headers() -> dict:
        return {
            "Cache-Control": "no-store",
            "Content-Security-Policy": _CSP,
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        }

    def _check_perm(request, perm_key: str):
        """Server-side permission gate (osint #22 — perms were client-side only).

        Returns None when access is allowed, or a 403 JSONResponse.
        Identity comes from the signature-verified claims the auth middleware
        stashed on request.state; fail closed when absent. The explicit
        GHOSTMODE_DEV_NO_AUTH opt-out (which bypasses the middleware) also
        bypasses tier checks — local dev only.
        """
        import os
        from starlette.responses import JSONResponse
        if _is_truthy(os.getenv("GHOSTMODE_DEV_NO_AUTH", "")):
            return None
        import ghostmode.github_auth as _ga
        claims = getattr(request.state, "oidc_claims", None) or {}
        email = claims.get("email", "")
        if not email:
            return JSONResponse({"error": "forbidden"}, status_code=403)
        cfg = load_config()
        perms = _ga.get_user_permissions(
            email=email, github_token=cfg.get("github_org_token"))
        if not perms.get(perm_key, False):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        return None

    @mcp.custom_route("/", methods=["GET"])
    async def dashboard(request):
        from starlette.responses import HTMLResponse
        cfg = load_config()
        if cfg["nest_mode"]:
            from ghostmode.nest_dashboard import build_nest_wrapper
            return HTMLResponse(build_nest_wrapper(), headers=_html_headers())
        from ghostmode.dashboard import build_dashboard
        return HTMLResponse(build_dashboard(), headers=_html_headers())

    @mcp.custom_route("/ops/", methods=["GET"])
    async def ops_dashboard(request):
        """Serve the Ops infrastructure dashboard (ops_enabled tier)."""
        denied = _check_perm(request, "ops_enabled")
        if denied is not None:
            return denied
        from starlette.responses import HTMLResponse
        from ghostmode.ops_dashboard import build_ops_dashboard
        # no-store: the board is live infra status — never serve a stale render
        # (e.g. an old asset count) from the browser/edge cache.
        return HTMLResponse(build_ops_dashboard(), headers=_html_headers())

    @mcp.custom_route("/ghostmode/", methods=["GET"])
    async def ghostmode_embed(request):
        """Serve the Ghost Mode dashboard for iframe embedding."""
        from starlette.responses import HTMLResponse
        from ghostmode.dashboard import build_dashboard
        return HTMLResponse(build_dashboard(), headers=_html_headers())

    # osint #34: brand backdrop assets, served from 'self' so the boards'
    # CSP (img-src 'self' ...) allows them. Strict allowlist — the name is
    # never used to touch the filesystem outside this map.
    _FIGMA_ASSETS = {
        "bg-image.jpg": "image/jpeg",
        "home-overlay.png": "image/png",
        "floor.svg": "image/svg+xml",
    }

    # osint #45: self-hosted OpenUI browser bundle (pinned npm artifact) — the
    # wrapper renders board views from OpenUI Lang without any iframe.
    _OPENUI_ASSETS = {
        "openui-bundle.min.js": "text/javascript",
        "openui-styles.css": "text/css",
    }

    def _static_asset(subdir: str, name: str, allowlist: dict):
        from pathlib import Path
        from starlette.responses import JSONResponse, Response
        ctype = allowlist.get(name)
        if ctype is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        path = Path(__file__).parent / "static" / subdir / name
        if not path.is_file():
            return JSONResponse({"error": "not found"}, status_code=404)
        return Response(
            path.read_bytes(),
            media_type=ctype,
            # immutable-ish brand assets; cut repeat fetches on every board load
            headers={"Cache-Control": "public, max-age=86400"},
        )

    @mcp.custom_route("/assets/figma/{name}", methods=["GET"])
    async def figma_asset(request):
        return _static_asset("figma", request.path_params.get("name", ""),
                             _FIGMA_ASSETS)

    @mcp.custom_route("/assets/openui/{name}", methods=["GET"])
    async def openui_asset(request):
        return _static_asset("openui", request.path_params.get("name", ""),
                             _OPENUI_ASSETS)

    @mcp.custom_route("/api/ui/ops", methods=["GET"])
    async def ui_ops(request):
        """Infrastructure board as an OpenUI Lang document (osint #45).
        Same server-side gate as the HTML board."""
        denied = _check_perm(request, "ops_enabled")
        if denied is not None:
            return denied
        from starlette.responses import PlainTextResponse
        from ghostmode.openui_views import build_ops_lang
        import ghostmode.ops_dashboard as _ops
        return PlainTextResponse(
            build_ops_lang(_ops.run_probes()),
            headers={"Cache-Control": "no-store"},
        )

    @mcp.custom_route("/health", methods=["GET"])
    async def health_endpoint(request):
        from starlette.responses import JSONResponse
        # In NEST mode, return 200 always (ntfy/canary not deployed to AWS)
        cfg = load_config()
        if cfg["nest_mode"]:
            return JSONResponse({"ok": True, "command": "health", "mode": "nest"})
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


    @mcp.custom_route("/api/surveillance", methods=["GET"])
    async def api_surveillance(request):
        from starlette.responses import JSONResponse
        from ghostmode.cloudflare_monitor import get_threat_summary, fetch_security_events, correlate_ips
        hours = float(request.query_params.get("hours", "6"))
        domain = request.query_params.get("domain", "")
        host = request.query_params.get("host", "")
        path_filter = request.query_params.get("path", "")

        # If filters are present, do filtered query
        if domain or host or path_filter:
            events = fetch_security_events(hours_back=hours, limit_per_zone=100)
            if domain:
                events = [e for e in events if e.get("domain") == domain]
            if host:
                events = [e for e in events if e.get("host") == host]
            if path_filter:
                events = [e for e in events if path_filter in e.get("path", "")]
            correlated = correlate_ips(events)
            unique_ips = set(e.get("client_ip") for e in events)
            by_domain = {}
            by_action = {}
            by_threat = {}
            recon_count = 0
            for evt in events:
                d = evt.get("domain", ""); by_domain[d] = by_domain.get(d, 0) + 1
                a = evt.get("action", ""); by_action[a] = by_action.get(a, 0) + 1
                t = evt.get("threat_level", ""); by_threat[t] = by_threat.get(t, 0) + 1
                if evt.get("is_recon"): recon_count += 1
            return JSONResponse({
                "period_hours": hours,
                "total_events": len(events),
                "unique_ips": len(unique_ips),
                "recon_attempts": recon_count,
                "cross_domain_actors": len(correlated),
                "by_domain": by_domain, "by_action": by_action, "by_threat_level": by_threat,
                "correlated_ips": correlated[:10], "events": events,
            })
        result = get_threat_summary(hours_back=hours)
        if not result.get("error"):
            from ghostmode.alerter import process_surveillance_alerts
            result["alerts_sent"] = process_surveillance_alerts(
                result.get("events", []), result.get("correlated_ips", []))
        return JSONResponse(result)

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
        domain = request.query_params.get("domain", "")
        host = request.query_params.get("host", "")
        events = fetch_security_events(hours_back=hours, limit_per_zone=50)
        if domain:
            events = [e for e in events if e.get("domain") == domain]
        if host:
            events = [e for e in events if e.get("host") == host]
        markers = geolocate_events(events)
        return JSONResponse({"count": len(markers), "markers": markers})

    @mcp.custom_route("/api/store-stats", methods=["GET"])
    async def api_store_stats(request):
        """Get event store statistics — total events, date range, by domain."""
        from starlette.responses import JSONResponse
        from ghostmode.event_store import get_stats
        return JSONResponse(get_stats())

    @mcp.custom_route("/api/ip-events", methods=["GET"])
    async def api_ip_events(request):
        """Get all surveillance events for a specific IP address."""
        from starlette.responses import JSONResponse
        from ghostmode.cloudflare_monitor import fetch_security_events
        from ghostmode.geoip import geolocate_ip
        ip = request.query_params.get("ip", "")
        hours = float(request.query_params.get("hours", "24"))
        if not ip:
            return JSONResponse({"error": "Missing ?ip= parameter"}, status_code=400)
        events = fetch_security_events(hours_back=hours, limit_per_zone=100)
        ip_events = [e for e in events if e.get("client_ip") == ip]
        geo = geolocate_ip(ip)
        return JSONResponse({
            "ip": ip,
            "geo": geo,
            "count": len(ip_events),
            "events": ip_events,
        })

    @mcp.custom_route("/api/action-intel", methods=["GET"])
    async def api_action_intel(request):
        """Get threat intelligence and remediation for a Cloudflare action/source type."""
        from starlette.responses import JSONResponse
        action = request.query_params.get("action", "")
        source = request.query_params.get("source", "")
        path = request.query_params.get("path", "")
        intel = _get_action_intel(action, source, path)
        return JSONResponse(intel)

    # ---- N.E.S.T. Ops API endpoints ----

    @mcp.custom_route("/api/rss", methods=["GET"])
    async def api_rss(request):
        """Proxy an RSS/Atom feed to avoid CORS. Returns parsed headlines as JSON."""
        from starlette.responses import JSONResponse
        from ghostmode.rss_proxy import fetch_rss
        url = request.query_params.get("url", "")
        if not url:
            return JSONResponse({"ok": False, "error": "Missing ?url= parameter"}, status_code=400)
        max_items = int(request.query_params.get("max", "20"))
        result = fetch_rss(url, max_items=max_items)
        return JSONResponse(result, status_code=200 if result["ok"] else 502)

    @mcp.custom_route("/api/linear/issues", methods=["GET"])
    async def api_linear_issues(request):
        """Fetch recent Linear issues for the ticker. Requires LINEAR_API_KEY
        and the linear_enabled permission tier (osint #22)."""
        denied = _check_perm(request, "linear_enabled")
        if denied is not None:
            return denied
        from starlette.responses import JSONResponse
        from ghostmode.linear_proxy import fetch_issues
        cfg = load_config()
        if not cfg.get("linear_api_key"):
            return JSONResponse({"ok": False, "items": [], "error": "Linear not configured"})
        team = request.query_params.get("team") or None
        status_filter = request.query_params.get("status") or None
        limit = int(request.query_params.get("limit", "20"))
        result = fetch_issues(cfg["linear_api_key"], team=team, status=status_filter, limit=limit)
        return JSONResponse(result)

    @mcp.custom_route("/api/auth/permissions", methods=["GET"])
    async def api_auth_permissions(request):
        """Check user permissions based on GitHub org team membership.

        Identity comes ONLY from the signature-verified ALB OIDC claims set
        by GhostmodeAuthMiddleware (osint #22). There is deliberately no
        query-param or unverified-decode fallback — those were the
        identity-forgery vectors this endpoint used to have.
        """
        from starlette.responses import JSONResponse
        from ghostmode.github_auth import get_user_permissions
        cfg = load_config()

        claims = getattr(request.state, "oidc_claims", None) or {}
        email = claims.get("email", "")
        if not email:
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        permissions = get_user_permissions(
            email=email,
            github_token=cfg.get("github_org_token"),
        )
        # Surface the verified identity so the wrapper can render the
        # profile avatar (initials + email) in the top bar. `sub` is the
        # Cognito subject — Matrix MXIDs on the phenom homeserver are
        # @{sub}:chat.thephenom.app (see matrixUserIdFor in the dev-nest SPA).
        return JSONResponse({**permissions, "email": email,
                             "sub": claims.get("sub", "")})

    return mcp


# --- Threat intelligence reference ---
def _get_action_intel(action: str, source: str, path: str) -> dict:
    """Return human-readable intel and remediation for a Cloudflare action."""
    intel = {
        "action": action,
        "source": source,
        "path": path,
        "severity": "info",
        "description": "",
        "what_happened": "",
        "risk": "",
        "remediation": [],
        "references": [],
    }

    # Action-based intel
    actions = {
        "block": {
            "severity": "high",
            "description": "Request was blocked by Cloudflare firewall",
            "what_happened": "Cloudflare detected a malicious pattern in the request and dropped it before it reached your server.",
            "risk": "The attacker knows your site exists and is actively probing it. Blocked requests indicate automated scanning or targeted attack attempts.",
            "remediation": [
                "No immediate action needed — Cloudflare blocked it",
                "Monitor if the same IP returns with different techniques",
                "Consider adding the IP to a Cloudflare IP block list if persistent",
                "Review Cloudflare WAF rules to ensure they match your application",
            ],
        },
        "managed_challenge": {
            "severity": "medium",
            "description": "Cloudflare issued a challenge (CAPTCHA/JS challenge) to the client",
            "what_happened": "The request looked suspicious (bot-like behavior, bad reputation, etc). Cloudflare forced the client to prove it's human before proceeding.",
            "risk": "Moderate — could be a bot, scraper, or reconnaissance tool. Legitimate users occasionally trigger challenges too.",
            "remediation": [
                "Check if the User-Agent is a known scanner (Nmap, Nikto, sqlmap, etc.)",
                "If the IP is a repeat offender, escalate to block",
                "Review Cloudflare Bot Fight Mode settings if too many false positives",
            ],
        },
        "link_maze_injected": {
            "severity": "low",
            "description": "Cloudflare Link Maze was injected — a bot trap that sends crawlers into infinite loops",
            "what_happened": "Cloudflare detected a bot and served it a link maze — an infinite set of fake links designed to waste the bot's time and resources while protecting your real content.",
            "risk": "Low — this is defensive. The bot is being trapped, not reaching your actual site.",
            "remediation": [
                "No action needed — Link Maze is working as intended",
                "Monitor if the same bot adapts to bypass the maze",
                "Good sign — your bot protection is active",
            ],
        },
        "jschallenge": {
            "severity": "medium",
            "description": "JavaScript challenge issued — client must execute JS to proceed",
            "what_happened": "Similar to managed_challenge but specifically requires JavaScript execution, which most simple bots cannot do.",
            "risk": "The requester may be a headless browser or sophisticated scraper.",
            "remediation": [
                "Monitor for successful challenge solves from the same IP — indicates a sophisticated actor",
                "Review if the challenged path contains sensitive data",
            ],
        },
    }

    # Source-based intel
    sources = {
        "firewallManaged": {
            "description": "Cloudflare Managed WAF Rules",
            "detail": "Triggered by Cloudflare's curated ruleset that detects known attack signatures (SQLi, XSS, RCE, etc.).",
        },
        "botFight": {
            "description": "Cloudflare Bot Fight Mode",
            "detail": "Detected automated traffic based on behavioral analysis, IP reputation, and fingerprinting.",
        },
        "firewallCustom": {
            "description": "Custom Firewall Rule",
            "detail": "Triggered by a custom rule you configured in Cloudflare dashboard.",
        },
        "linkMaze": {
            "description": "Cloudflare Link Maze (Bot Trap)",
            "detail": "Automated detection led to serving a bot trap that wastes attacker resources.",
        },
    }

    # Path-based intel (recon indicators)
    recon_paths = {
        "/wp-admin": ("WordPress admin probe", "Attacker is checking if you run WordPress. Common automated scanner behavior.", ["Ensure you don't have WordPress installed or exposed", "If you do run WordPress, enable 2FA on wp-admin"]),
        "/wp-login.php": ("WordPress login probe", "Brute force attempt against WordPress login.", ["Block /wp-login.php at the WAF if you don't use WordPress"]),
        "/wp-includes/wlwmanifest.xml": ("WordPress WLW manifest probe", "Scanner checking for Windows Live Writer integration — a known WordPress enumeration technique.", ["This is pure reconnaissance — no action needed if you don't run WordPress"]),
        "/.env": ("Environment file probe", "Attacker trying to read your .env file which may contain API keys, database passwords, and secrets.", ["CRITICAL: Verify .env is not accessible on any of your sites", "Add a Cloudflare WAF rule to block /.env requests"]),
        "/.git/config": ("Git repository probe", "Attacker checking if your .git directory is exposed, which would reveal source code and commit history.", ["Verify .git is not accessible — test with curl", "Add a Cloudflare WAF rule to block /.git/ requests"]),
        "/xmlrpc.php": ("WordPress XML-RPC probe", "Can be used for brute force amplification or DDoS.", ["Disable XML-RPC if not needed", "Block at WAF level"]),
        "/admin": ("Admin panel probe", "Generic admin page discovery.", ["Ensure admin panels require authentication", "Use non-obvious admin URLs"]),
        "/phpinfo.php": ("PHP info disclosure probe", "Checking for phpinfo() output which reveals server configuration.", ["Remove any phpinfo.php files from production"]),
        "/backup.sql": ("Database backup probe", "Checking for accidentally exposed database dumps.", ["CRITICAL: Scan all sites for exposed backup files"]),
        "/swagger.json": ("API documentation probe", "Checking for exposed Swagger/OpenAPI docs that reveal your API structure.", ["Restrict API docs to authenticated users in production"]),
        "/actuator": ("Spring Boot actuator probe", "Checking for exposed Spring Boot management endpoints.", ["Restrict actuator endpoints to internal networks"]),
    }

    # Apply action intel
    if action in actions:
        for k, v in actions[action].items():
            intel[k] = v

    # Apply source intel
    if source in sources:
        intel["source_description"] = sources[source]["description"]
        intel["source_detail"] = sources[source]["detail"]

    # Apply path-specific intel
    for prefix, (name, detail, remediations) in recon_paths.items():
        if path.startswith(prefix) or path == prefix:
            intel["path_name"] = name
            intel["path_detail"] = detail
            intel["remediation"] = remediations + intel.get("remediation", [])
            intel["severity"] = "high"
            intel["references"].append(f"OWASP: Forced Browsing — testing for exposed files/directories")
            break

    intel["references"].extend([
        "Cloudflare Docs: Firewall Events — https://developers.cloudflare.com/waf/analytics/",
        "OWASP Top 10 — https://owasp.org/www-project-top-ten/",
    ])

    return intel
