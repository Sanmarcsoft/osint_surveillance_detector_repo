"""Ops infrastructure dashboard: health, latency, and TLS for thephenom.app assets.

Served at GET /ops/ and embedded in the NEST "Infrastructure" tab. Rendered
server-side from live probes, so it has NO database dependency — the surveillance
board uses Postgres, but this board must stay up even when the DB is unreachable.
"""

import concurrent.futures
import socket
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from string import Template

from ghostmode import __version__
from ghostmode.brand import BACKDROP_CSS, backdrop_div

# (label, hostname, health path). Mirrors the blackbox monitoring targets for the
# thephenom.app estate. Access-gated hosts answer with a login redirect or 401/403
# — still "reachable", which is what this board reports (edge + cert health).
ASSETS = [
    {"label": "Website", "kind": "http", "host": "www.thephenom.app", "path": "/"},
    {"label": "NEST", "kind": "http", "host": "nest.thephenom.app", "path": "/"},
    {"label": "Dev NEST", "kind": "http", "host": "dev-nest.thephenom.app", "path": "/"},
    {"label": "Drop", "kind": "http", "host": "drop.thephenom.app", "path": "/"},
    {"label": "Chat (Synapse)", "kind": "http", "host": "chat.thephenom.app", "path": "/healthz"},
    {"label": "API (staging)", "kind": "http", "host": "api-staging.thephenom.app", "path": "/healthz"},
    {"label": "API (public)", "kind": "http", "host": "api.thephenom.app", "path": "/public/www-reports"},
    {"label": "Analytics", "kind": "http", "host": "analytics.thephenom.app", "path": "/"},
    {"label": "Webmail", "kind": "http", "host": "webmail.thephenom.app", "path": "/"},
    {"label": "Cloudflare edge", "kind": "http", "host": "www.thephenom.app", "path": "/cdn-cgi/trace"},
    # ADSB cache service — the globe's aircraft archive (Phenom-earth/adsb-archive
    # Lambda + S3, sourced from opensky/adsb.lol), served via the Worker. Gated, so
    # a 401 still means "reachable" = the cache API is serving.
    {"label": "ADSB cache (archive API)", "kind": "http", "host": "nest.thephenom.app", "path": "/api/adsb/window"},
    {"label": "Ops", "kind": "http", "host": "nest-ops.thephenom.app", "path": "/"},
    # AWS databases — RDS Postgres. Health comes from the RDS control-plane API
    # (DescribeDBInstances → status), NOT a TCP connect: AWS-managed services
    # aren't reliably socket-probable from inside the task (outbound :25 is
    # blocked, cross-VPC reach varies), so the API status is the authoritative
    # "is it healthy" signal. Requires rds:DescribeDBInstances on the task role.
    {"label": "DB · dev (RDS Postgres)", "kind": "aws_rds", "db_id": "phenom-dev-postgres",
     "host": "phenom-dev-postgres.c8toq6uq223c.us-east-1.rds.amazonaws.com"},
    {"label": "DB · prod (RDS Postgres)", "kind": "aws_rds", "db_id": "phenom-prod-postgres",
     "host": "phenom-prod-postgres.c8toq6uq223c.us-east-1.rds.amazonaws.com"},
    # Mail — SES (account sending status via the SESv2 API). Requires ses:GetAccount.
    {"label": "Mail · SES (us-east-1)", "kind": "aws_ses", "host": "email.us-east-1.amazonaws.com"},
]

_TIMEOUT = 5
_AWS_REGION = "us-east-1"

# This service's own public host. We can't verify it over HTTP from inside the
# request handler — a self-request would deadlock the single async worker — nor
# hairpin to our own public cert from inside the task. The self-row is reported
# "live" directly: this code executing is itself proof the service is up.
_SELF_HOST = "nest-ops.thephenom.app"


def _probe_url(url: str):
    """Return (status_code or None, latency_ms). None code means unreachable."""
    start = time.monotonic()
    code = None
    try:
        req = urllib.request.Request(
            url, method="GET", headers={"User-Agent": "ghostmode-ops/1.0"}
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            code = resp.status
    except urllib.error.HTTPError as exc:
        code = exc.code  # 401/403/5xx are still a server response
    except Exception:
        code = None
    return code, int((time.monotonic() - start) * 1000)


def _probe_http(host: str, path: str):
    """Probe a host over HTTPS."""
    return _probe_url("https://{}{}".format(host, path))


def _ssl_days_left(host: str):
    """Days until the host's TLS certificate expires, or None if unavailable."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=_TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                not_after = tls.getpeercert()["notAfter"]
        expires = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(
            tzinfo=timezone.utc
        )
        return (expires - datetime.now(timezone.utc)).days
    except Exception:
        return None


def _probe_rds(db_id: str):
    """Return (status_str or None, latency_ms) from the RDS control-plane API.

    Authoritative health for an RDS instance — "available" means healthy. Uses
    the task IAM role (rds:DescribeDBInstances); boto3 is imported lazily so a
    missing dependency degrades to "unknown" rather than failing the board.
    """
    start = time.monotonic()
    try:
        import boto3

        rds = boto3.client("rds", region_name=_AWS_REGION)
        resp = rds.describe_db_instances(DBInstanceIdentifier=db_id)
        status = resp["DBInstances"][0]["DBInstanceStatus"]
        return status, int((time.monotonic() - start) * 1000)
    except Exception:
        return None, int((time.monotonic() - start) * 1000)


def _probe_ses():
    """Return (status_str or None, latency_ms) from the SESv2 account API.

    "sending" means the account can send; "paused" means sending is disabled.
    Uses the task IAM role (ses:GetAccount).
    """
    start = time.monotonic()
    try:
        import boto3

        ses = boto3.client("sesv2", region_name=_AWS_REGION)
        enabled = ses.get_account().get("SendingEnabled", False)
        return ("sending" if enabled else "paused"), int((time.monotonic() - start) * 1000)
    except Exception:
        return None, int((time.monotonic() - start) * 1000)


def _check(asset):
    label = asset["label"]
    host = asset["host"]
    if host == _SELF_HOST:
        return {
            "label": label, "host": host, "code": 200, "latency_ms": None,
            "ssl_days": None, "reachable": True, "is_self": True,
        }
    if asset["kind"] == "aws_rds":
        status, latency_ms = _probe_rds(asset["db_id"])
        return {
            "label": label, "host": host,
            "code": status.upper() if status else None, "latency_ms": latency_ms,
            "ssl_days": None, "reachable": status == "available", "is_self": False,
        }
    if asset["kind"] == "aws_ses":
        status, latency_ms = _probe_ses()
        return {
            "label": label, "host": host,
            "code": status.upper() if status else None, "latency_ms": latency_ms,
            "ssl_days": None, "reachable": status == "sending", "is_self": False,
        }
    code, latency_ms = _probe_http(host, asset["path"])
    return {
        "label": label,
        "host": host,
        "code": code,
        "latency_ms": latency_ms,
        "ssl_days": _ssl_days_left(host),
        "reachable": code is not None and code < 500,
        "is_self": False,
    }


def _badge(text, cls):
    return '<span class="badge {}">{}</span>'.format(cls, text)


def build_ops_dashboard() -> str:
    """Build the Ops infrastructure dashboard HTML. Never raises."""
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(ASSETS)) as pool:
            results = list(pool.map(_check, ASSETS))
    except Exception:
        results = []

    rows = []
    up = 0
    for r in results:
        if r["reachable"]:
            up += 1
            status = _badge(r["code"], "up")
            if r.get("is_self") or r["latency_ms"] is None:
                latency = _badge("live", "up")
            else:
                lat = r["latency_ms"]
                lat_cls = "up" if lat < 800 else "warn" if lat < 2000 else "down"
                latency = _badge("{} ms".format(lat), lat_cls)
        else:
            status = _badge(r["code"] or "DOWN", "down")
            latency = _badge("&mdash;", "down")

        days = r["ssl_days"]
        if days is None:
            tls = _badge("&mdash;", "down")
        else:
            tls_cls = "up" if days > 21 else "warn" if days > 7 else "down"
            tls = _badge("{}d".format(days), tls_cls)

        rows.append(
            "<tr><td class='asset'>{}</td><td class='host'>{}</td>"
            "<td class='status'>{}</td><td class='lat'>{}</td>"
            "<td class='tls'>{}</td></tr>".format(
                r["label"], r["host"], status, latency, tls
            )
        )

    total = len(results)
    summary_cls = "up" if total and up == total else "warn" if up else "down"
    body = "\n".join(rows) or '<tr><td colspan="5" class="event-empty">No probe results</td></tr>'
    return Template(_HTML).safe_substitute(
        rows=body,
        up=up,
        total=total,
        summary_cls=summary_cls,
        ts=datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
        version=__version__,
        backdrop_css=BACKDROP_CSS,
    ).replace("<body>", "<body>\n" + backdrop_div(), 1)


_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;700&family=Roboto+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<title>Infrastructure — thephenom.app</title>
<style>
:root {
  --bg:#050406; --card:rgba(20,18,22,0.40); --border:rgba(255,255,255,0.10); --text:#e0e0e0; --dim:#a1a1aa;
  --green:#4ade80; --red:#f87171; --yellow:#fbbf24; --blue:#a5e3e8; --accent:#d73429;
  --mono:'Roboto Mono','SF Mono',monospace; --hero:'Oswald','Impact',sans-serif;
}
* { margin:0; padding:0; box-sizing:border-box; }
/* Phenom starfield backdrop — shared with all boards (brand.BACKDROP_CSS, osint #34) */
html { background:#060606; }
body { background:transparent; color:var(--text); font-family:var(--mono); font-size:13px;
       line-height:1.6; padding:1.5rem; max-width:960px; margin:0 auto; position:relative; z-index:0; }
$backdrop_css
h1 { font-size:1.6rem; margin-bottom:0.3rem; font-family:var(--hero); letter-spacing:0.3px; color:#fff; }
.subtitle { color:var(--dim); margin-bottom:1.2rem; font-size:0.85rem; }
.card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:1rem;
        -webkit-backdrop-filter:blur(20px) saturate(170%); backdrop-filter:blur(20px) saturate(170%);
        box-shadow:0 8px 24px rgba(0,0,0,.40), 0 0 0 1px rgba(215,52,41,.06); }
.card h2 { font-size:0.75rem; color:var(--dim); text-transform:uppercase; letter-spacing:0.08em;
           margin-bottom:0.8rem; display:flex; justify-content:space-between; align-items:center; }
table { width:100%; border-collapse:collapse; }
th { text-align:left; color:var(--dim); font-weight:normal; font-size:0.7rem; text-transform:uppercase;
     letter-spacing:0.06em; padding:0.4rem 0.5rem; border-bottom:1px solid var(--border); }
td { padding:0.45rem 0.5rem; border-bottom:1px solid var(--border); }
tr:last-child td { border-bottom:none; }
td.host { color:var(--dim); }
.badge { padding:2px 8px; border-radius:4px; font-size:0.72rem; font-weight:bold; }
.badge.up { background:#0a2e1a; color:var(--green); }
.badge.down { background:#2e0a0a; color:var(--red); }
.badge.warn { background:#2e2a0a; color:var(--yellow); }
.event-empty { color:var(--dim); padding:1rem 0; text-align:center; }
.footer { color:var(--dim); font-size:0.75rem; margin-top:1.2rem; text-align:center; }
.footer a { color:var(--blue); text-decoration:none; }
/* osint #34 (M directive, iteration 2): mobile must show EVERYTHING without
   horizontal scrolling — a sideways-scrolling table hides the Status/Latency/
   TLS columns, which are the whole point of the board. Each probe row becomes
   a stacked mini-card: asset + status on the first line, host underneath,
   latency/TLS as a labelled pair below. */
@media (max-width: 640px) {
  body { padding:0.75rem; font-size:12.5px; }
  h1 { font-size:1.3rem; }
  .subtitle { font-size:0.78rem; margin-bottom:0.9rem; }
  .card { padding:0.8rem; border-radius:10px; }
  .card h2 { flex-wrap:wrap; gap:0.3rem; }
  .footer { font-size:0.7rem; }

  table, tbody { display:block; width:100%; }
  thead { display:none; }
  tr { display:grid; grid-template-columns:1fr auto; align-items:center;
       gap:0.15rem 0.6rem; padding:0.6rem 0.1rem;
       border-bottom:1px solid var(--border); }
  tr:last-child { border-bottom:none; }
  td { display:block; padding:0; border:none; }
  td.asset { grid-column:1; grid-row:1; color:#fff; font-weight:600;
             font-size:0.85rem; }
  td.status { grid-column:2; grid-row:1; justify-self:end; }
  td.host { grid-column:1 / -1; grid-row:2; font-size:0.72rem;
            overflow-wrap:anywhere; }
  td.lat, td.tls { grid-row:3; font-size:0.75rem; }
  td.lat { grid-column:1; }
  td.tls { grid-column:2; justify-self:end; }
  td.lat::before { content:'latency '; color:var(--dim); font-size:0.65rem;
                   text-transform:uppercase; letter-spacing:0.05em; }
  td.tls::before { content:'tls '; color:var(--dim); font-size:0.65rem;
                   text-transform:uppercase; letter-spacing:0.05em; }
}
</style>
</head>
<body>
<h1>Infrastructure</h1>
<div class="subtitle">Health, latency &amp; TLS for thephenom.app assets · $up/$total reachable · $ts</div>
<div class="card">
  <h2>thephenom.app assets <span class="badge $summary_cls">$up/$total UP</span></h2>
  <table>
    <thead><tr><th>Asset</th><th>Host</th><th>Status</th><th>Latency</th><th>TLS</th></tr></thead>
    <tbody>
$rows
    </tbody>
  </table>
</div>
<div class="footer">ghostmode v$version · auto-refreshes every 60s · Monitored by <a href="https://ops.sanmarcsoft.com">ops.sanmarcsoft.com</a></div>
</body>
</html>"""
