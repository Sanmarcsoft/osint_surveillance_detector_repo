"""Interactive HTML dashboard for human operators at https://crabkey.sanmarcsoft.com/"""

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
    cfg = load_config()
    status_data = get_status(
        ntfy_server=cfg["ntfy_server"],
        ntfy_topic=cfg["ntfy_topic"],
        canary_log=cfg["opencanary_log"],
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
    )


_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ghost Mode — crabkey.sanmarcsoft.com</title>
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

@media (max-width:600px) { .grid{grid-template-columns:1fr;} .form-row{flex-direction:column;} }
</style>
</head>
<body>

<h1>Ghost Mode</h1>
<p class="subtitle">crabkey.sanmarcsoft.com — OSINT Honeypot + AI Agent Platform v$version
  <span id="live-dot" class="pulse" style="color:var(--green);">●</span></p>

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
      <span style="display:flex;gap:0.4rem;align-items:center;">
        <select id="surv-hours" style="width:70px;padding:2px 4px;font-size:0.7rem;">
          <option value="1">1h</option>
          <option value="6" selected>6h</option>
          <option value="12">12h</option>
          <option value="24">24h</option>
        </select>
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

<div class="footer">
  Ghost Mode — <a href="https://github.com/Sanmarcsoft/osint_surveillance_detector_repo">GitHub</a>
  · Monitored by <a href="https://ops.sanmarcsoft.com">ops.sanmarcsoft.com</a>
  · MCP endpoint: <code>/mcp</code>
</div>

<script>
const API = '';  // same origin

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

// --- Surveillance scan ---
async function loadSurveillance() {
  const hours = document.getElementById('surv-hours').value;
  document.getElementById('surv-summary').innerHTML = '<div class="event-empty" style="width:100%"><span class="spinner"></span> Scanning all domains...</div>';
  document.getElementById('surv-events').innerHTML = '';
  document.getElementById('surv-correlated').style.display = 'none';

  const data = await apiFetch('/api/surveillance?hours=' + hours);
  if (data.error) {
    document.getElementById('surv-summary').innerHTML = '<div class="event-empty" style="width:100%;color:var(--red)">' + data.error + '</div>';
    return;
  }

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
      '<span style="color:'+tcolor+';font-weight:bold;">'+e.action+'</span> ' +
      '<span class="event-service">'+e.host+'</span>' +
      '<span style="color:var(--dim)">'+e.path+'</span> ' +
      'from <span class="event-src">'+e.client_ip+'</span> ' +
      '<span class="event-time">'+e.country+'</span>' +
      (e.is_recon ? ' <span class="badge down" style="font-size:0.65rem;">RECON</span>' : '') +
      '</div>';
  }).join('');
}

// Enter key triggers search
document.getElementById('kb-query').addEventListener('keydown', e => { if(e.key==='Enter') searchDocs(); });
document.getElementById('q-src').addEventListener('keydown', e => { if(e.key==='Enter') queryLogs(); });

// Initial load
loadRecentEvents();
loadSurveillance();
</script>
</body>
</html>"""
