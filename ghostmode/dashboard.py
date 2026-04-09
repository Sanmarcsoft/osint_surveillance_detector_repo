"""Interactive HTML dashboard for surveillance detection."""

from datetime import datetime, timezone
from string import Template

from ghostmode import __version__
from ghostmode.config import load_config, validate_config
from ghostmode.status import get_status


def _format_uptime(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.0f}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def build_dashboard() -> str:
    from ghostmode.cloudflare_monitor import get_zones
    cfg = load_config()
    status_data = get_status(
        ntfy_server=cfg["ntfy_server"],
        ntfy_topic=cfg["ntfy_topic"],
        canary_log=cfg["opencanary_log"],
    )
    zones = get_zones()
    domain_options = ''.join(
        f'<option value="{d}">{d}</option>' for d in sorted(zones.keys())
    )

    services_rows = []
    for svc_data in status_data["services"].values():
        name = svc_data["name"]
        status = svc_data["status"]
        if status in ("reachable", "running"):
            badge = '<span class="badge up">UP</span>'
        else:
            badge = f'<span class="badge down">{status}</span>'
        services_rows.append(f'<div class="status-row"><span class="label">{name}</span>{badge}</div>')
    services_rows.append('<div class="status-row"><span class="label">mcp_server</span><span class="badge up">UP</span></div>')

    config_result = validate_config()
    if config_result["ok"] and not config_result["issues"]:
        config_html = '<div class="status-row"><span class="label">Status</span><span class="badge up">OK</span></div>'
    else:
        config_rows = []
        for issue in config_result["issues"]:
            cls = "warn" if issue["severity"] == "warning" else "down"
            config_rows.append(f'<div class="status-row"><span class="label">{issue["key"]}</span><span class="badge {cls}">{issue["severity"]}</span></div>')
        config_html = "\n".join(config_rows) if config_rows else '<div class="status-row"><span class="badge up">OK</span></div>'

    return Template(_HTML).safe_substitute(
        version=__version__,
        services_html="\n".join(services_rows),
        uptime=_format_uptime(status_data["uptime_seconds"]),
        timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
        config_html=config_html,
        domain_options=domain_options,
    )


_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>watching the Watchers...</title>
<link rel="icon" type="image/png" href="data:image/png;base64,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">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin="">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
<style>
:root {
  --bg: #0a0a0a; --card: #141414; --border: #2a2a2a; --text: #e0e0e0;
  --dim: #666; --green: #4ade80; --red: #f87171; --yellow: #fbbf24;
  --blue: #60a5fa; --purple: #c084fc; --mono: 'SF Mono','Cascadia Code',monospace;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--bg); color:var(--text); font-family:var(--mono);
       font-size:13px; line-height:1.6; padding:1.5rem; max-width:960px; margin:0 auto; }
h1 { font-size:1.4rem; margin-bottom:0.3rem; }
.subtitle { color:var(--dim); margin-bottom:1.5rem; font-size:0.85rem; }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:0.8rem; margin-bottom:0.8rem; }
.card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:1rem; }
.card h2 { font-size:0.75rem; color:var(--dim); text-transform:uppercase;
           letter-spacing:0.08em; margin-bottom:0.6rem; display:flex;
           justify-content:space-between; align-items:center; }
.status-row { display:flex; justify-content:space-between; align-items:center; padding:0.25rem 0; }
.status-row .label { color:var(--dim); }
.badge { padding:2px 8px; border-radius:4px; font-size:0.75rem; font-weight:bold; }
.badge.up { background:#0a2e1a; color:var(--green); }
.badge.down { background:#2e0a0a; color:var(--red); }
.badge.warn { background:#2e2a0a; color:var(--yellow); }
.badge.info { background:#0a1a2e; color:var(--blue); }
.full-width { grid-column:1/-1; }

/* Interactive elements */
btn, .btn { background:var(--border); color:var(--text); border:1px solid #444;
       border-radius:4px; padding:6px 14px; font-family:var(--mono); font-size:0.8rem;
       cursor:pointer; transition:background 0.15s; }
.btn:hover { background:#3a3a3a; }
.btn:active { background:#4a4a4a; }
.btn.primary { background:#1a365d; border-color:var(--blue); color:var(--blue); }
.btn.primary:hover { background:#2a4a7d; }
.btn.danger { background:#3b1a1a; border-color:var(--red); color:var(--red); }
.btn-sm { padding:3px 10px; font-size:0.75rem; }

input[type=text], input[type=number], select {
  background:var(--bg); color:var(--text); border:1px solid var(--border);
  border-radius:4px; padding:6px 10px; font-family:var(--mono); font-size:0.8rem;
  width:100%;
}
input:focus, select:focus { outline:none; border-color:var(--blue); }

.form-row { display:flex; gap:0.5rem; margin-bottom:0.5rem; align-items:center; }
.form-row label { color:var(--dim); min-width:60px; font-size:0.75rem; }
.form-row input, .form-row select { flex:1; }

.result-box { background:var(--bg); border:1px solid var(--border); border-radius:4px;
              padding:0.6rem; margin-top:0.6rem; max-height:300px; overflow-y:auto;
              font-size:0.75rem; white-space:pre-wrap; word-break:break-all; display:none; }
.result-box.visible { display:block; }

.event-row { padding:0.4rem 0; border-bottom:1px solid var(--border); font-size:0.75rem; }
.event-row:last-child { border-bottom:none; }
.event-time { color:var(--dim); }
.event-service { color:var(--purple); font-weight:bold; }
.event-src { color:var(--yellow); }
.event-empty { color:var(--dim); padding:1rem 0; text-align:center; }

.spinner { display:inline-block; width:12px; height:12px; border:2px solid var(--border);
           border-top-color:var(--blue); border-radius:50%; animation:spin 0.6s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }

.pulse { animation:pulse-glow 2s ease-in-out infinite; }
@keyframes pulse-glow { 0%,100%{opacity:1} 50%{opacity:0.5} }

.footer { color:var(--dim); font-size:0.75rem; margin-top:1.5rem; text-align:center; }
a { color:var(--blue); text-decoration:none; }
a:hover { text-decoration:underline; }

#threat-map { height:400px; border-radius:8px; background:var(--card); border:1px solid var(--border); }
.leaflet-container { background:var(--bg) !important; }
.map-legend { position:absolute; bottom:20px; right:20px; background:var(--card); border:1px solid var(--border);
              border-radius:6px; padding:8px 12px; z-index:1000; font-size:0.7rem; }
.map-legend .dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:4px; }
@media (max-width:600px) { .grid{grid-template-columns:1fr;} .form-row{flex-direction:column;} #threat-map{height:250px;} }
</style>
</head>
<body>

<h1>watching the Watchers...</h1>
<p class="subtitle">v$version
  <span id="live-dot" class="pulse" style="color:var(--green);">●</span></p>

<!-- Threat Map -->
<div class="card" style="margin-bottom:0.8rem;position:relative;">
  <h2>Threat Map
    <span style="display:flex;gap:0.4rem;align-items:center;flex-wrap:wrap;">
      <select id="map-hours" style="width:55px;padding:2px 4px;font-size:0.7rem;">
        <option value="1">1h</option>
        <option value="6" selected>6h</option>
        <option value="12">12h</option>
        <option value="24">24h</option>
      </select>
      <select id="map-domain" style="width:130px;padding:2px 4px;font-size:0.7rem;">
        <option value="">All domains</option>
        $domain_options
      </select>
      <input type="text" id="map-host" placeholder="FQDN filter" style="width:140px;padding:2px 4px;font-size:0.7rem;">
      <button class="btn btn-sm" onclick="loadThreatMap()">Load</button>
    </span>
  </h2>
  <div id="threat-map"></div>
  <div class="map-legend">
    <div><span class="dot" style="background:#f87171"></span> High threat</div>
    <div><span class="dot" style="background:#fbbf24"></span> Medium threat</div>
    <div><span class="dot" style="background:#60a5fa"></span> Low / info</div>
    <div style="margin-top:4px;color:var(--dim);" id="map-status">Click Load to populate</div>
  </div>
</div>

<!-- Row 1: Services + System -->
<div class="grid">
  <div class="card" id="services-card">
    <h2>Services <span id="refresh-timer" style="font-size:0.7rem;color:var(--dim)"></span></h2>
    <div id="services-body">$services_html</div>
  </div>
  <div class="card">
    <h2>System</h2>
    <div class="status-row"><span class="label">Uptime</span><span id="sys-uptime">$uptime</span></div>
    <div class="status-row"><span class="label">Version</span><span>$version</span></div>
    <div class="status-row"><span class="label">Checked</span><span id="sys-time">$timestamp</span></div>
  </div>
</div>

<!-- Row 2: Actions + Config -->
<div class="grid">
  <div class="card">
    <h2>Actions</h2>
    <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
      <button class="btn primary" onclick="sendTestAlert()">Send Test Alert</button>
      <button class="btn" onclick="validateConfig()">Validate Config</button>
      <button class="btn" onclick="refreshStatus()">Refresh Now</button>
    </div>
    <div id="action-result" class="result-box"></div>
  </div>
  <div class="card">
    <h2>Config</h2>
    <div id="config-body">$config_html</div>
  </div>
</div>

<!-- Row 3: Log Query -->
<div class="grid">
  <div class="card full-width">
    <h2>Query Honeypot Logs</h2>
    <div class="form-row">
      <label>Service</label>
      <select id="q-service"><option value="">all</option><option value="http">http</option><option value="ftp">ftp</option></select>
      <label>Source IP</label>
      <input type="text" id="q-src" placeholder="e.g. 203.0.113.42">
      <label>Limit</label>
      <input type="number" id="q-limit" value="20" min="1" max="200" style="width:60px;">
      <button class="btn primary btn-sm" onclick="queryLogs()">Search</button>
    </div>
    <div id="logs-body">
      <div class="event-empty">Run a query to see honeypot events</div>
    </div>
  </div>
</div>

<!-- Row 4: Surveillance Feed (Cloudflare Security Events) -->
<div class="grid">
  <div class="card full-width">
    <h2>Surveillance Detection
      <span style="display:flex;gap:0.4rem;align-items:center;flex-wrap:wrap;">
        <select id="surv-hours" style="width:55px;padding:2px 4px;font-size:0.7rem;">
          <option value="1">1h</option>
          <option value="6" selected>6h</option>
          <option value="12">12h</option>
          <option value="24">24h</option>
        </select>
        <select id="surv-domain" style="width:130px;padding:2px 4px;font-size:0.7rem;">
          <option value="">All domains</option>
          $domain_options
        </select>
        <input type="text" id="surv-host" placeholder="FQDN filter" style="width:120px;padding:2px 4px;font-size:0.7rem;">
        <input type="text" id="surv-path" placeholder="Path filter" style="width:100px;padding:2px 4px;font-size:0.7rem;">
        <button class="btn btn-sm" onclick="loadSurveillance()">Scan</button>
      </span>
    </h2>
    <div id="surv-summary" style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:0.6rem;">
      <div class="event-empty" style="width:100%">Click Scan to check all domains</div>
    </div>
    <div id="surv-correlated" style="display:none;margin-bottom:0.6rem;"></div>
    <div id="surv-events" style="max-height:350px;overflow-y:auto;"></div>
  </div>
</div>

<!-- Row 5: Honeypot Events -->
<div class="grid">
  <div class="card full-width">
    <h2>Honeypot Events <button class="btn btn-sm" onclick="loadRecentEvents()" style="margin-left:auto;">Refresh</button></h2>
    <div id="events-body">
      <div class="event-empty">Loading...</div>
    </div>
  </div>
</div>

<!-- Row 6: Knowledge Base -->
<div class="grid">
  <div class="card full-width">
    <h2>Knowledge Base</h2>
    <div class="form-row">
      <input type="text" id="kb-query" placeholder="Ask anything... e.g. 'how to investigate a brute force attempt'">
      <button class="btn primary btn-sm" onclick="searchDocs()">Search</button>
    </div>
    <div id="kb-result" class="result-box"></div>
  </div>
</div>

<!-- IP Drill-Down Panel (hidden by default) -->
<div class="card full-width" id="ip-drilldown" style="display:none;margin-bottom:0.8rem;border-color:var(--yellow);">
  <h2>
    <span>IP Investigation: <span id="dd-ip" style="color:var(--yellow)"></span></span>
    <button class="btn btn-sm" onclick="closeIpDrilldown()">Close</button>
  </h2>
  <div id="dd-geo" style="color:var(--dim);margin-bottom:0.6rem;"></div>
  <div id="dd-assessment" style="display:none;margin-bottom:0.8rem;"></div>
  <div id="dd-loading" class="event-empty"><span class="spinner"></span> Loading events...</div>
  <table id="dd-table" style="width:100%;border-collapse:collapse;display:none;font-size:0.75rem;">
    <thead>
      <tr style="border-bottom:2px solid var(--border);text-align:left;">
        <th style="padding:6px;color:var(--dim);">Time</th>
        <th style="padding:6px;color:var(--dim);">Action</th>
        <th style="padding:6px;color:var(--dim);">Domain</th>
        <th style="padding:6px;color:var(--dim);">Path</th>
        <th style="padding:6px;color:var(--dim);">Source</th>
      </tr>
    </thead>
    <tbody id="dd-tbody"></tbody>
  </table>
</div>

<!-- Action Intel Panel (hidden by default) -->
<div class="card full-width" id="action-intel" style="display:none;margin-bottom:0.8rem;border-color:var(--blue);">
  <h2>
    <span>Threat Intel: <span id="ai-title" style="color:var(--blue)"></span></span>
    <button class="btn btn-sm" onclick="closeActionIntel()">Close</button>
  </h2>
  <div id="ai-body"></div>
</div>

<div class="footer">
  watching the Watchers... — <a href="https://github.com/Sanmarcsoft/osint_surveillance_detector_repo">GitHub</a>
  · Monitored by <a href="https://ops.sanmarcsoft.com">ops.sanmarcsoft.com</a>
  · MCP endpoint: <code>/mcp</code>
</div>

<script>
const API = '';  // same origin
let cachedSurvEvents = [];  // client-side cache of last surveillance scan

function showResult(id, data, isError) {
  const el = document.getElementById(id);
  el.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  el.style.borderColor = isError ? 'var(--red)' : 'var(--border)';
  el.classList.add('visible');
}

async function apiFetch(path, opts) {
  try {
    const r = await fetch(API + path, opts);
    return await r.json();
  } catch(e) {
    return {error: e.message};
  }
}

// --- Auto-refresh status every 30s ---
let countdown = 30;
async function refreshStatus() {
  countdown = 30;
  const data = await apiFetch('/health');
  if (data.error) return;

  const svcDiv = document.getElementById('services-body');
  let html = '';
  if (data.data && data.data.services) {
    for (const [k,v] of Object.entries(data.data.services)) {
      const up = v.status === 'reachable' || v.status === 'running';
      html += '<div class="status-row"><span class="label">' + v.name + '</span>' +
              '<span class="badge ' + (up?'up':'down') + '">' + (up?'UP':v.status) + '</span></div>';
    }
  }
  html += '<div class="status-row"><span class="label">mcp_server</span><span class="badge up">UP</span></div>';
  svcDiv.innerHTML = html;

  if (data.data) {
    const u = data.data.uptime_seconds;
    document.getElementById('sys-uptime').textContent = u<60? u.toFixed(0)+'s' : u<3600? (u/60).toFixed(0)+'m' : u<86400? (u/3600).toFixed(1)+'h' : (u/86400).toFixed(1)+'d';
  }
  document.getElementById('sys-time').textContent = new Date().toISOString().slice(11,19)+' UTC';
}

setInterval(() => {
  countdown--;
  document.getElementById('refresh-timer').textContent = countdown + 's';
  if (countdown <= 0) refreshStatus();
}, 1000);

// --- Send test alert ---
async function sendTestAlert() {
  showResult('action-result', 'Sending...', false);
  const data = await apiFetch('/api/alert-test', {method:'POST'});
  showResult('action-result', data, !!data.error);
}

// --- Validate config ---
async function validateConfig() {
  showResult('action-result', 'Validating...', false);
  const data = await apiFetch('/api/config-validate');
  showResult('action-result', data, !data.ok);

  // Also update the config card
  const body = document.getElementById('config-body');
  if (data.ok && (!data.issues || data.issues.length === 0)) {
    body.innerHTML = '<div class="status-row"><span class="label">Status</span><span class="badge up">OK</span></div>';
  } else if (data.issues) {
    body.innerHTML = data.issues.map(i =>
      '<div class="status-row"><span class="label">'+i.key+'</span>' +
      '<span class="badge '+(i.severity==='warning'?'warn':'down')+'">'+i.severity+'</span></div>'
    ).join('');
  }
}

// --- Query logs ---
async function queryLogs() {
  const svc = document.getElementById('q-service').value;
  const src = document.getElementById('q-src').value.trim();
  const limit = document.getElementById('q-limit').value;
  const params = new URLSearchParams();
  if (svc) params.set('service', svc);
  if (src) params.set('src_host', src);
  params.set('limit', limit);

  document.getElementById('logs-body').innerHTML = '<div class="event-empty"><span class="spinner"></span> Querying...</div>';
  const data = await apiFetch('/api/logs?' + params);
  renderEvents('logs-body', data);
}

// --- Recent events ---
async function loadRecentEvents() {
  const data = await apiFetch('/api/logs?limit=10');
  renderEvents('events-body', data);
}

function renderEvents(containerId, data) {
  const el = document.getElementById(containerId);
  if (data.error) { el.innerHTML = '<div class="event-empty" style="color:var(--red)">'+data.error+'</div>'; return; }
  if (!data.events || data.events.length === 0) { el.innerHTML = '<div class="event-empty">No events found</div>'; return; }

  el.innerHTML = data.events.map(e =>
    '<div class="event-row">' +
    '<span class="event-time">' + (e.timestamp||'?') + '</span> ' +
    '<span class="event-service">' + (e.service||'?') + '</span>:' + (e.port||'?') + ' ' +
    'from <span class="event-src">' + (e.src_host||'?') + '</span>' +
    (e.logdata && e.logdata.USERNAME ? ' user='+e.logdata.USERNAME : '') +
    (e.logdata && e.logdata.URL ? ' url='+e.logdata.URL : '') +
    '</div>'
  ).join('');
}

// --- Knowledge base search ---
async function searchDocs() {
  const q = document.getElementById('kb-query').value.trim();
  if (!q) return;
  showResult('kb-result', 'Searching...', false);
  const data = await apiFetch('/api/docs?q=' + encodeURIComponent(q));
  if (data.error) { showResult('kb-result', data.error, true); return; }
  if (!data.results || data.results.length === 0) { showResult('kb-result', 'No results found.', false); return; }

  let text = '';
  for (const r of data.results) {
    text += '=== ' + r.id + ' (' + (r.metadata?.type||'?') + ') ===\n';
    text += (r.document||'').slice(0, 500) + '\n\n';
  }
  showResult('kb-result', text, false);
}

// --- Threat Map (Leaflet + MaxMind GeoIP) ---
const map = L.map('threat-map', {
  center: [30, 0], zoom: 2, zoomControl: true,
  attributionControl: false, minZoom: 2, maxZoom: 12,
});
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  subdomains: 'abcd', maxZoom: 19,
}).addTo(map);

const threatColors = { high: '#f87171', medium: '#fbbf24', low: '#60a5fa', info: '#60a5fa' };
let mapMarkers = L.layerGroup().addTo(map);

async function loadThreatMap() {
  const hours = document.getElementById('map-hours').value;
  const domain = document.getElementById('map-domain').value;
  const host = document.getElementById('map-host').value.trim();
  const params = new URLSearchParams({hours});
  if (domain) params.set('domain', domain);
  if (host) params.set('host', host);
  document.getElementById('map-status').textContent = 'Loading GeoIP data...';
  mapMarkers.clearLayers();

  const data = await apiFetch('/api/threat-map?' + params);
  if (data.error) {
    document.getElementById('map-status').textContent = 'Error: ' + data.error;
    return;
  }
  if (!data.markers || data.markers.length === 0) {
    document.getElementById('map-status').textContent = 'No geolocated threats found';
    return;
  }

  for (const m of data.markers) {
    const color = threatColors[m.threat_level] || '#60a5fa';
    const radius = Math.max(6, Math.min(25, m.count * 3));
    const circle = L.circleMarker([m.lat, m.lng], {
      radius: radius, color: color, fillColor: color, fillOpacity: 0.6,
      weight: 2, opacity: 0.9,
    }).addTo(mapMarkers);
    circle.bindPopup(
      '<div style="font-family:monospace;font-size:12px;">' +
      '<a href="#" onclick="map.closePopup();drilldownIp(\'' + m.ip + '\');return false;" style="color:' + color + ';font-size:14px;font-weight:bold;">' + m.ip + '</a><br>' +
      m.city + ', ' + m.country + '<br>' +
      '<span style="color:' + color + ';">' + m.threat_level.toUpperCase() + '</span>' +
      ' — ' + m.count + ' event' + (m.count>1?'s':'') + '<br>' +
      'Domains: ' + m.domains.join(', ') + '<br>' +
      '<a href="#" onclick="map.closePopup();drilldownIp(\'' + m.ip + '\');return false;" style="color:var(--blue);font-size:11px;background:var(--border);padding:3px 8px;border-radius:3px;display:inline-block;margin-top:4px;">Investigate this IP &rarr;</a>' +
      '</div>'
    );
  }
  document.getElementById('map-status').textContent = data.markers.length + ' sources plotted';
  if (data.markers.length > 0) {
    const bounds = data.markers.map(m => [m.lat, m.lng]);
    map.fitBounds(bounds, {padding: [30,30], maxZoom: 6});
  }
}

// --- Surveillance scan ---
async function loadSurveillance() {
  const hours = document.getElementById('surv-hours').value;
  const domain = document.getElementById('surv-domain').value;
  const host = document.getElementById('surv-host').value.trim();
  const pathF = document.getElementById('surv-path').value.trim();
  const params = new URLSearchParams({hours});
  if (domain) params.set('domain', domain);
  if (host) params.set('host', host);
  if (pathF) params.set('path', pathF);
  document.getElementById('surv-summary').innerHTML = '<div class="event-empty" style="width:100%"><span class="spinner"></span> Scanning' + (domain ? ' ' + domain : ' all domains') + '...</div>';
  document.getElementById('surv-events').innerHTML = '';
  document.getElementById('surv-correlated').style.display = 'none';

  const data = await apiFetch('/api/surveillance?' + params);
  if (data.error) {
    document.getElementById('surv-summary').innerHTML = '<div class="event-empty" style="width:100%;color:var(--red)">' + data.error + '</div>';
    return;
  }
  cachedSurvEvents = data.events || [];

  // Summary badges
  const s = document.getElementById('surv-summary');
  const high = data.by_threat_level?.high || 0;
  const med = data.by_threat_level?.medium || 0;
  s.innerHTML =
    '<div class="badge '+(high>0?'down':'up')+'" style="padding:6px 12px;font-size:0.85rem;">'+data.total_events+' events</div>' +
    '<div class="badge info" style="padding:6px 12px;">'+data.unique_ips+' unique IPs</div>' +
    '<div class="badge '+(data.recon_attempts>0?'down':'up')+'" style="padding:6px 12px;">'+data.recon_attempts+' recon</div>' +
    '<div class="badge '+(data.cross_domain_actors>0?'warn':'up')+'" style="padding:6px 12px;">'+data.cross_domain_actors+' cross-domain</div>' +
    Object.entries(data.by_domain||{}).map(([d,c]) =>
      '<div style="font-size:0.75rem;color:var(--dim);padding:4px 8px;">'+d+': '+c+'</div>'
    ).join('');

  // Correlated IPs (cross-domain threats)
  if (data.correlated_ips && data.correlated_ips.length > 0) {
    const cd = document.getElementById('surv-correlated');
    cd.style.display = 'block';
    cd.innerHTML = '<div style="font-size:0.75rem;color:var(--yellow);margin-bottom:0.3rem;">Cross-domain actors (same IP, multiple sites):</div>' +
      data.correlated_ips.map(c =>
        '<div class="event-row"><span class="event-src">'+c.client_ip+'</span> ' +
        '<span class="badge warn" style="font-size:0.7rem;">'+c.domain_count+' domains</span> ' +
        c.domains.join(', ') + ' ' +
        '<span class="event-time">'+c.country+' / '+c.asn+'</span></div>'
      ).join('');
  }

  // Event list
  const el = document.getElementById('surv-events');
  if (!data.events || data.events.length === 0) {
    el.innerHTML = '<div class="event-empty">No security events in this period</div>';
    return;
  }
  el.innerHTML = data.events.map(e => {
    const tcolor = e.threat_level==='high' ? 'var(--red)' : e.threat_level==='medium' ? 'var(--yellow)' : 'var(--dim)';
    return '<div class="event-row">' +
      '<span class="event-time">'+e.timestamp.slice(11,19)+'</span> ' +
      '<a href="#" onclick="showActionIntel(\''+esc(e.action)+"','"+esc(e.source)+"','"+esc(e.path)+'\');return false;" style="color:'+tcolor+';font-weight:bold;text-decoration:underline;cursor:pointer;">'+e.action+'</a> ' +
      '<span class="event-service">'+e.host+'</span>' +
      '<a href="#" onclick="showActionIntel(\''+esc(e.action)+"','"+esc(e.source)+"','"+esc(e.path)+'\');return false;" style="color:var(--dim);">'+e.path+'</a> ' +
      'from <a href="#" onclick="drilldownIp(\''+esc(e.client_ip)+'\');return false;" class="event-src" style="text-decoration:underline;cursor:pointer;">'+e.client_ip+'</a> ' +
      '<span class="event-time">'+e.country+'</span>' +
      (e.is_recon ? ' <span class="badge down" style="font-size:0.65rem;">RECON</span>' : '') +
      '</div>';
  }).join('');
}

// --- IP Drill-Down ---
async function drilldownIp(ip) {
  const panel = document.getElementById('ip-drilldown');
  const loading = document.getElementById('dd-loading');
  const table = document.getElementById('dd-table');
  const tbody = document.getElementById('dd-tbody');

  document.getElementById('dd-ip').textContent = ip;
  document.getElementById('dd-geo').textContent = '';
  document.getElementById('dd-assessment').style.display = 'none';
  loading.style.display = 'block';
  table.style.display = 'none';
  tbody.innerHTML = '';
  panel.style.display = 'block';
  panel.scrollIntoView({behavior:'smooth'});

  // Use cached surveillance events first (same data that plotted the map)
  let events = cachedSurvEvents.filter(e => e.client_ip === ip);
  let geoData = null;

  if (events.length > 0) {
    // We have cached data — show immediately, fetch geo in background
    loading.style.display = 'none';
    renderDrilldownEvents(events, tbody, table);
    // Fetch geo async
    const geoResp = await apiFetch('/api/ip-events?ip=' + encodeURIComponent(ip) + '&hours=24');
    geoData = geoResp.geo;
    // Merge any additional events from API that weren't in cache
    if (geoResp.events && geoResp.events.length > events.length) {
      events = geoResp.events;
      tbody.innerHTML = '';
      renderDrilldownEvents(events, tbody, table);
    }
  } else {
    // No cached data — full API call
    const data = await apiFetch('/api/ip-events?ip=' + encodeURIComponent(ip) + '&hours=24');
    loading.style.display = 'none';
    if (data.error) {
      tbody.innerHTML = '<tr><td colspan="5" style="color:var(--red);padding:8px;">'+data.error+'</td></tr>';
      table.style.display = 'table';
      return;
    }
    events = data.events || [];
    geoData = data.geo;
    renderDrilldownEvents(events, tbody, table);
  }

  // Geo line
  if (geoData) {
    document.getElementById('dd-geo').textContent = (geoData.city||'Unknown') + ', ' + (geoData.country||'Unknown') + ' — ' + events.length + ' events';
  } else {
    document.getElementById('dd-geo').textContent = events.length + ' events found';
  }

  // AI threat assessment
  if (events.length > 0) {
    generateThreatAssessment(ip, events, geoData);
  }
}

function renderDrilldownEvents(events, tbody, table) {
  if (!events || events.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="color:var(--dim);padding:8px;">No events found for this IP</td></tr>';
    table.style.display = 'table';
    return;
  }
  for (const e of events) {
    const tcolor = e.threat_level==='high' ? 'var(--red)' : e.threat_level==='medium' ? 'var(--yellow)' : 'var(--dim)';
    const tr = document.createElement('tr');
    tr.style.borderBottom = '1px solid var(--border)';
    tr.innerHTML =
      '<td style="padding:5px;color:var(--dim);white-space:nowrap;">' + (e.timestamp||'').slice(11,19) + '</td>' +
      '<td style="padding:5px;"><a href="#" onclick="showActionIntel(\'' +
        esc(e.action) + "','" + esc(e.source) + "','" + esc(e.path) +
        '\');return false;" style="color:'+tcolor+';font-weight:bold;text-decoration:underline;cursor:pointer;">' + esc(e.action) + '</a>' +
        (e.is_recon ? ' <span class="badge down" style="font-size:0.6rem;">RECON</span>' : '') + '</td>' +
      '<td style="padding:5px;color:var(--purple);">' + esc(e.host) + '</td>' +
      '<td style="padding:5px;"><a href="#" onclick="showActionIntel(\'' +
        esc(e.action) + "','" + esc(e.source) + "','" + esc(e.path) +
        '\');return false;" style="color:var(--text);">' + esc(e.path) + '</a></td>' +
      '<td style="padding:5px;color:var(--dim);">' + esc(e.source) + '</td>';
    tbody.appendChild(tr);
  }
  table.style.display = 'table';
}

// --- AI Threat Assessment ---
function generateThreatAssessment(ip, events, geo) {
  const el = document.getElementById('dd-assessment');
  el.style.display = 'block';

  // Analyze patterns
  const domains = [...new Set(events.map(e => e.domain))];
  const hosts = [...new Set(events.map(e => e.host))];
  const paths = [...new Set(events.map(e => e.path))];
  const actions = [...new Set(events.map(e => e.action))];
  const sources = [...new Set(events.map(e => e.source))];
  const reconEvents = events.filter(e => e.is_recon);
  const highEvents = events.filter(e => e.threat_level === 'high');
  const timestamps = events.map(e => new Date(e.timestamp).getTime()).sort();
  const asn = events[0]?.asn || '';
  const ua = events[0]?.user_agent || '';

  // Time analysis
  let burstRate = 0;
  if (timestamps.length > 1) {
    const spanMs = timestamps[timestamps.length-1] - timestamps[0];
    burstRate = spanMs > 0 ? (events.length / (spanMs / 1000)).toFixed(2) : 0;
  }

  // Classification
  let classification = 'Unclassified';
  let confidence = 'Low';
  let intent = '';
  let indicators = [];
  let recommendation = '';

  // Multi-domain = targeted campaign
  if (domains.length >= 2) {
    classification = 'Targeted Reconnaissance Campaign';
    confidence = 'High';
    intent = 'This IP is systematically probing multiple domains in your portfolio, indicating a targeted campaign rather than opportunistic scanning.';
    indicators.push('Cross-domain activity: ' + domains.join(', '));
    recommendation = 'Add this IP to a Cloudflare IP block list across all zones. Monitor the ASN for related IPs.';
  }
  // WordPress probing
  else if (paths.some(p => p.includes('wp-') || p.includes('wordpress'))) {
    classification = 'WordPress Vulnerability Scanner';
    confidence = 'High';
    intent = 'Automated scanner checking for WordPress installations to exploit known vulnerabilities (login brute force, plugin exploits, XML-RPC amplification).';
    indicators.push('WordPress-specific paths targeted');
    recommendation = 'No action if you do not run WordPress. If you do, ensure it is patched and wp-login.php is protected.';
  }
  // .env / .git / sensitive file probing
  else if (paths.some(p => p.includes('.env') || p.includes('.git') || p.includes('backup') || p.includes('phpinfo'))) {
    classification = 'Sensitive File Enumeration';
    confidence = 'High';
    intent = 'Scanning for accidentally exposed configuration files, source code, or backups that would reveal credentials and infrastructure details.';
    indicators.push('Sensitive file paths targeted: ' + paths.filter(p => p.includes('.env') || p.includes('.git') || p.includes('backup')).join(', '));
    recommendation = 'CRITICAL: Verify none of these files are accessible on your production servers. Add WAF rules to block these paths.';
  }
  // High volume = automated
  else if (events.length >= 5 || burstRate > 0.5) {
    classification = 'Automated Scanner / Bot';
    confidence = 'Medium';
    intent = 'High-frequency requests indicate automated tooling (Nmap, Nikto, sqlmap, or custom scanner).';
    indicators.push('Request rate: ' + burstRate + ' req/sec');
    recommendation = 'Cloudflare is handling this with challenges/blocks. Monitor for adaptation.';
  }
  // Bot fight
  else if (sources.includes('botFight') || sources.includes('linkMaze')) {
    classification = 'Bot / Crawler';
    confidence = 'Medium';
    intent = 'Automated traffic detected by Cloudflare behavioral analysis. May be a scraper, SEO bot, or reconnaissance tool.';
    indicators.push('Cloudflare bot detection triggered');
    recommendation = 'No immediate action — Cloudflare is mitigating. Check if the User-Agent is a known crawler.';
  }
  // Single blocked request
  else if (actions.includes('block')) {
    classification = 'Blocked Attack Attempt';
    confidence = 'Medium';
    intent = 'Request matched a known attack signature in the Cloudflare WAF managed rules.';
    indicators.push('WAF block triggered');
    recommendation = 'Cloudflare blocked this. Monitor for repeat attempts from same IP or ASN.';
  }
  // Fallback
  else {
    classification = 'Suspicious Activity';
    confidence = 'Low';
    intent = 'Activity flagged by Cloudflare but does not match a specific attack pattern.';
    recommendation = 'Monitor. No immediate action required.';
  }

  // ASN analysis
  const knownBadASNs = ['DIGITALOCEAN', 'LINODE', 'VULTR', 'HETZNER', 'OVH', 'LATITUDE', 'CHOOPA'];
  const isVPS = knownBadASNs.some(a => asn.toUpperCase().includes(a));
  if (isVPS) {
    indicators.push('VPS/cloud provider ASN: ' + asn + ' — commonly used for scanning infrastructure');
  }

  // Bot UA detection
  const knownBots = ['bot', 'crawler', 'spider', 'scan', 'nikto', 'nmap', 'sqlmap', 'dirbuster', 'gobuster', 'masscan'];
  const isBotUA = knownBots.some(b => ua.toLowerCase().includes(b));
  if (isBotUA) indicators.push('Known scanner User-Agent detected: ' + ua.slice(0, 80));
  if (ua === 'Mozilla/5.0' && ua.length < 20) indicators.push('Suspiciously short User-Agent (likely spoofed): "' + ua + '"');

  // Render
  const confColor = confidence === 'High' ? 'var(--red)' : confidence === 'Medium' ? 'var(--yellow)' : 'var(--dim)';
  let html = '<div style="border-left:3px solid '+confColor+';padding-left:10px;">';
  html += '<div style="font-size:0.95rem;font-weight:bold;color:'+confColor+';margin-bottom:4px;">'+classification+'</div>';
  html += '<div style="margin-bottom:6px;"><span class="badge" style="background:'+confColor+'22;color:'+confColor+';">Confidence: '+confidence+'</span>';
  html += ' <span style="color:var(--dim);font-size:0.75rem;">'+events.length+' events across '+domains.length+' domain(s), '+paths.length+' unique path(s)</span></div>';
  html += '<div style="margin-bottom:8px;">'+intent+'</div>';

  if (indicators.length > 0) {
    html += '<div style="margin-bottom:8px;"><strong style="color:var(--dim);font-size:0.7rem;">INDICATORS</strong><ul style="margin:4px 0 0 1.2rem;">';
    for (const i of indicators) html += '<li style="padding:1px 0;">'+i+'</li>';
    html += '</ul></div>';
  }

  if (geo) html += '<div style="margin-bottom:8px;"><strong style="color:var(--dim);font-size:0.7rem;">ORIGIN</strong><br>'+
    (geo.city||'?')+', '+(geo.country||'?')+' — ASN: '+(asn||'unknown')+'</div>';

  html += '<div style="border-top:1px solid var(--border);padding-top:6px;margin-top:6px;">';
  html += '<strong style="color:var(--green);font-size:0.7rem;">RECOMMENDED ACTION</strong><br>';
  const isCrit = recommendation.startsWith('CRITICAL');
  html += '<span style="'+(isCrit?'color:var(--red);font-weight:bold;':'')+'">'+recommendation+'</span></div>';
  html += '</div>';

  el.innerHTML = html;
}

function closeIpDrilldown() {
  document.getElementById('ip-drilldown').style.display = 'none';
}

// --- Action Intel Panel ---
async function showActionIntel(action, source, path) {
  const panel = document.getElementById('action-intel');
  const body = document.getElementById('ai-body');
  document.getElementById('ai-title').textContent = action + (path ? ' on ' + path : '');
  body.innerHTML = '<div class="event-empty"><span class="spinner"></span> Loading intel...</div>';
  panel.style.display = 'block';
  panel.scrollIntoView({behavior:'smooth'});

  const params = new URLSearchParams({action, source, path});
  const data = await apiFetch('/api/action-intel?' + params);

  if (data.error) {
    body.innerHTML = '<div style="color:var(--red);">' + data.error + '</div>';
    return;
  }

  const sevColor = data.severity==='high' ? 'var(--red)' : data.severity==='medium' ? 'var(--yellow)' : 'var(--blue)';

  let html = '<div style="margin-bottom:1rem;">';
  html += '<span class="badge" style="background:' + sevColor + '22;color:' + sevColor + ';font-size:0.85rem;padding:4px 10px;">' + (data.severity||'info').toUpperCase() + '</span>';
  if (data.source_description) html += ' <span style="color:var(--dim);">via ' + data.source_description + '</span>';
  html += '</div>';

  if (data.description) {
    html += '<div style="margin-bottom:0.8rem;"><strong style="color:var(--dim);font-size:0.7rem;">WHAT</strong><br>' + data.description + '</div>';
  }
  if (data.what_happened) {
    html += '<div style="margin-bottom:0.8rem;"><strong style="color:var(--dim);font-size:0.7rem;">WHAT HAPPENED</strong><br>' + data.what_happened + '</div>';
  }
  if (data.path_name) {
    html += '<div style="margin-bottom:0.8rem;border-left:3px solid var(--yellow);padding-left:8px;">' +
      '<strong style="color:var(--yellow);font-size:0.7rem;">RECON PATTERN: ' + data.path_name.toUpperCase() + '</strong><br>' +
      data.path_detail + '</div>';
  }
  if (data.source_detail) {
    html += '<div style="margin-bottom:0.8rem;"><strong style="color:var(--dim);font-size:0.7rem;">SOURCE</strong><br>' + data.source_detail + '</div>';
  }
  if (data.risk) {
    html += '<div style="margin-bottom:0.8rem;"><strong style="color:var(--dim);font-size:0.7rem;">RISK ASSESSMENT</strong><br>' + data.risk + '</div>';
  }
  if (data.remediation && data.remediation.length > 0) {
    html += '<div style="margin-bottom:0.8rem;"><strong style="color:var(--green);font-size:0.7rem;">REMEDIATION</strong><ul style="margin:0.3rem 0 0 1.2rem;">';
    for (const r of data.remediation) {
      const isCritical = r.startsWith('CRITICAL');
      html += '<li style="padding:2px 0;' + (isCritical?'color:var(--red);font-weight:bold;':'') + '">' + r + '</li>';
    }
    html += '</ul></div>';
  }
  if (data.references && data.references.length > 0) {
    html += '<div><strong style="color:var(--dim);font-size:0.7rem;">REFERENCES</strong><ul style="margin:0.3rem 0 0 1.2rem;color:var(--dim);">';
    for (const ref of data.references) {
      if (ref.includes('http')) {
        const parts = ref.split(' — ');
        const url = parts.length > 1 ? parts[1] : ref;
        const label = parts.length > 1 ? parts[0] : ref;
        html += '<li style="padding:2px 0;"><a href="' + url + '" target="_blank" rel="noopener">' + label + '</a></li>';
      } else {
        html += '<li style="padding:2px 0;">' + ref + '</li>';
      }
    }
    html += '</ul></div>';
  }

  body.innerHTML = html;
}

function closeActionIntel() {
  document.getElementById('action-intel').style.display = 'none';
}

function esc(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/'/g,'&#39;').replace(/"/g,'&quot;'); }

// Enter key triggers search
document.getElementById('kb-query').addEventListener('keydown', e => { if(e.key==='Enter') searchDocs(); });
document.getElementById('q-src').addEventListener('keydown', e => { if(e.key==='Enter') queryLogs(); });

// Initial load
loadRecentEvents();
loadSurveillance();
loadThreatMap();
</script>
</body>
</html>"""
