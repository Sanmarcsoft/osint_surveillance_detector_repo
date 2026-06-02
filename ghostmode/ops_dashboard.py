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

# (label, hostname, health path). Mirrors the blackbox monitoring targets for the
# thephenom.app estate. Access-gated hosts answer with a login redirect or 401/403
# — still "reachable", which is what this board reports (edge + cert health).
ASSETS = [
    ("Website", "www.thephenom.app", "/"),
    ("NEST", "nest.thephenom.app", "/"),
    ("Dev NEST", "dev-nest.thephenom.app", "/"),
    ("Drop", "drop.thephenom.app", "/"),
    ("Chat (Synapse)", "chat.thephenom.app", "/healthz"),
    ("API (staging)", "api-staging.thephenom.app", "/healthz"),
    ("Analytics", "dashboard.thephenom.app", "/"),
    ("Webmail", "webmail.thephenom.app", "/"),
    ("Ops", "nest-ops.thephenom.app", "/"),
]

_TIMEOUT = 5

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


def _check(asset):
    label, host, path = asset
    if host == _SELF_HOST:
        return {
            "label": label, "host": host, "code": 200, "latency_ms": None,
            "ssl_days": None, "reachable": True, "is_self": True,
        }
    code, latency_ms = _probe_http(host, path)
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
            "<tr><td>{}</td><td class='host'>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
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
    )


_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>Infrastructure — thephenom.app</title>
<style>
:root {
  --bg:#0a0a0a; --card:#141414; --border:#2a2a2a; --text:#e0e0e0; --dim:#666;
  --green:#4ade80; --red:#f87171; --yellow:#fbbf24; --blue:#60a5fa;
  --mono:'SF Mono','Cascadia Code',monospace;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--bg); color:var(--text); font-family:var(--mono); font-size:13px;
       line-height:1.6; padding:1.5rem; max-width:960px; margin:0 auto; }
h1 { font-size:1.3rem; margin-bottom:0.3rem; }
.subtitle { color:var(--dim); margin-bottom:1.2rem; font-size:0.85rem; }
.card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:1rem; }
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
