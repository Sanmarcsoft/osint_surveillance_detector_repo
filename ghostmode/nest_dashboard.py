"""N.E.S.T. Ops wrapper page for dev-nest.thephenom.app.

Serves a ShadCN-styled sidebar + Grafana iframe + RSS ticker.
Ghost Mode is embedded full-screen inside a Grafana dashboard panel.
The sidebar controls navigation between Ghost Mode and Ops views.
"""

from ghostmode import __version__


def build_nest_wrapper() -> str:
    """Build the N.E.S.T. Ops wrapper HTML page."""
    return _NEST_HTML.replace("$version", __version__)


_NEST_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>N.E.S.T. Ops — dev-nest.thephenom.app</title>
<style>
:root {
  --bg: #09090b; --card: #141414; --border: #27272a; --text: #fafafa;
  --dim: #71717a; --green: #4ade80; --red: #f87171; --yellow: #fbbf24;
  --blue: #60a5fa; --purple: #c084fc; --accent: #3b82f6;
  --sidebar-w: 220px;
  --ticker-h: 40px;
  --mono: 'SF Mono','Cascadia Code','JetBrains Mono',monospace;
  --sans: 'Inter','Segoe UI',-apple-system,sans-serif;
}
* { margin:0; padding:0; box-sizing:border-box; }
html, body { height:100%; overflow:hidden; background:var(--bg); color:var(--text); font-family:var(--sans); }

/* === ShadCN Sidebar === */
.sidebar {
  position:fixed; top:0; left:0; bottom:var(--ticker-h); width:var(--sidebar-w);
  background:var(--card); border-right:1px solid var(--border);
  display:flex; flex-direction:column; z-index:100;
}
.sidebar-header {
  padding:20px 16px 16px; border-bottom:1px solid var(--border);
}
.sidebar-header h1 { font-size:16px; font-weight:600; letter-spacing:-0.02em; }
.sidebar-header p { font-size:11px; color:var(--dim); margin-top:4px; font-family:var(--mono); }
.sidebar-nav { flex:1; padding:8px; overflow-y:auto; }
.sidebar-section { padding:4px 0; }
.sidebar-section-label {
  font-size:10px; font-weight:600; color:var(--dim); text-transform:uppercase;
  letter-spacing:0.08em; padding:8px 12px 4px;
}
.sidebar-item {
  display:flex; align-items:center; gap:10px; padding:8px 12px; border-radius:6px;
  font-size:13px; color:var(--dim); cursor:pointer; transition:all 0.15s;
  text-decoration:none; border:none; background:none; width:100%; text-align:left;
}
.sidebar-item:hover { background:var(--border); color:var(--text); }
.sidebar-item.active { background:var(--accent); color:#fff; }
.sidebar-item svg { width:16px; height:16px; flex-shrink:0; }
.sidebar-divider { height:1px; background:var(--border); margin:8px 12px; }
.sidebar-footer {
  padding:12px 16px; border-top:1px solid var(--border); font-size:11px; color:var(--dim);
}
.sidebar-badge {
  font-size:10px; padding:1px 6px; border-radius:10px; margin-left:auto;
  background:#1e3a5f; color:var(--blue); font-weight:600;
}

/* === Main Content === */
.main {
  position:fixed; top:0; left:var(--sidebar-w); right:0; bottom:var(--ticker-h);
}
.main iframe {
  width:100%; height:100%; border:none; background:var(--bg);
}

/* === RSS Ticker === */
.ticker {
  position:fixed; bottom:0; left:0; right:0; height:var(--ticker-h);
  background:var(--card); border-top:1px solid var(--border);
  display:flex; align-items:center; z-index:100;
}
.ticker-settings-btn {
  background:none; border:none; color:var(--dim); padding:0 14px;
  cursor:pointer; font-size:16px; transition:color 0.15s;
}
.ticker-settings-btn:hover { color:var(--text); }
.ticker-content {
  flex:1; overflow:hidden; white-space:nowrap; font-family:var(--mono); font-size:13px;
}
.ticker-text {
  display:inline-block; color:var(--text); transition:transform 0.5s linear;
}
.ticker-text a { color:inherit; text-decoration:none; }
.ticker-text a:hover { text-decoration:underline; }

/* === Settings Panel === */
.settings-overlay {
  display:none; position:fixed; top:0; left:0; right:0; bottom:0;
  background:rgba(0,0,0,0.5); z-index:200;
}
.settings-overlay.open { display:block; }
.settings-panel {
  position:fixed; bottom:var(--ticker-h); right:0; width:440px; max-height:calc(100vh - var(--ticker-h));
  background:var(--card); border:1px solid var(--border); border-radius:8px 0 0 0;
  box-shadow:0 -8px 32px rgba(0,0,0,0.5); z-index:201; overflow-y:auto; padding:24px;
}
.settings-panel h2 { font-size:15px; font-weight:600; margin-bottom:16px; }
.settings-panel h3 {
  font-size:10px; font-weight:600; color:var(--dim); text-transform:uppercase;
  letter-spacing:0.08em; margin:20px 0 8px;
}
.settings-group { margin-bottom:16px; }
.settings-row {
  display:flex; align-items:center; gap:8px; margin-bottom:8px;
}
.settings-row label { font-size:12px; color:var(--dim); min-width:70px; }
.settings-row input[type=text], .settings-row select {
  flex:1; background:var(--bg); color:var(--text); border:1px solid var(--border);
  border-radius:6px; padding:6px 10px; font-size:12px; font-family:var(--mono);
}
.settings-row input:focus, .settings-row select:focus { outline:none; border-color:var(--accent); }
.settings-row input[type=range] { flex:1; accent-color:var(--accent); }
.settings-row input[type=color] {
  width:36px; height:28px; border:1px solid var(--border); border-radius:4px;
  background:var(--bg); cursor:pointer; padding:2px;
}
.btn {
  background:var(--border); color:var(--text); border:1px solid #3f3f46;
  border-radius:6px; padding:6px 14px; font-size:12px; cursor:pointer;
  font-family:var(--sans); transition:background 0.15s;
}
.btn:hover { background:#3a3a3a; }
.btn-primary { background:var(--accent); border-color:var(--accent); color:#fff; }
.btn-primary:hover { background:#2563eb; }
.btn-sm { padding:4px 10px; font-size:11px; }
.btn-ghost { background:transparent; border-color:transparent; }
.btn-ghost:hover { background:var(--border); }
.feed-list-item {
  display:flex; align-items:center; gap:6px; padding:6px 0;
  border-bottom:1px solid var(--border); font-size:12px;
}
.feed-list-item span { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--dim); font-family:var(--mono); }
.test-result {
  background:var(--bg); border:1px solid var(--border); border-radius:6px;
  padding:8px; margin-top:8px; font-size:11px; font-family:var(--mono);
  max-height:150px; overflow-y:auto; display:none; white-space:pre-wrap; word-break:break-all;
}
.test-result.visible { display:block; }
/* Toggle switch */
.toggle { position:relative; display:inline-block; width:36px; height:20px; }
.toggle input { opacity:0; width:0; height:0; }
.toggle-slider {
  position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0;
  background:var(--border); border-radius:10px; transition:0.2s;
}
.toggle-slider:before {
  content:""; position:absolute; height:16px; width:16px; left:2px; bottom:2px;
  background:var(--text); border-radius:50%; transition:0.2s;
}
.toggle input:checked + .toggle-slider { background:var(--accent); }
.toggle input:checked + .toggle-slider:before { transform:translateX(16px); }
/* INT features disabled state */
.int-disabled { opacity:0.4; pointer-events:none; }
.int-notice { font-size:11px; color:var(--dim); padding:8px 0; font-style:italic; }

@media (max-width:768px) {
  .sidebar { width:60px; }
  .sidebar-header h1, .sidebar-header p, .sidebar-section-label,
  .sidebar-item span, .sidebar-footer, .sidebar-badge { display:none; }
  .sidebar-item { justify-content:center; padding:10px; }
  .main { left:60px; }
  .settings-panel { width:100%; border-radius:8px 8px 0 0; }
}
</style>
</head>
<body>

<!-- Sidebar -->
<nav class="sidebar">
  <div class="sidebar-header">
    <h1>N.E.S.T. Ops</h1>
    <p>dev-nest.thephenom.app</p>
  </div>
  <div class="sidebar-nav">
    <div class="sidebar-section">
      <div class="sidebar-section-label">Dashboards</div>
      <button class="sidebar-item active" id="nav-ghostmode" onclick="switchView('ghostmode')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M12 8v4l3 3"/></svg>
        <span>Ghost Mode</span>
      </button>
      <button class="sidebar-item" id="nav-ops" style="display:none;" onclick="switchView('ops')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
        <span>Ops</span>
        <span class="sidebar-badge">INT</span>
      </button>
    </div>

    <div class="sidebar-divider"></div>

    <div class="sidebar-section" id="int-links" style="display:none;">
      <div class="sidebar-section-label">Services</div>
      <a class="sidebar-item" id="nav-linear" href="#" target="_blank" rel="noopener" style="display:none;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l6 6"/></svg>
        <span>Linear</span>
        <span class="sidebar-badge">INT</span>
      </a>
      <a class="sidebar-item" id="nav-umami" href="/umami/" target="_blank" rel="noopener">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>
        <span>Analytics</span>
      </a>
    </div>
  </div>
  <div class="sidebar-footer">
    <button class="sidebar-item" onclick="toggleSettings()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
      <span>Settings</span>
    </button>
    <div style="padding:8px 12px;font-size:10px;color:var(--dim);font-family:var(--mono);">v$version</div>
  </div>
</nav>

<!-- Main Content (iframe) -->
<div class="main" id="main-content">
  <iframe id="view-frame" src="/ghostmode/" title="Ghost Mode"></iframe>
</div>

<!-- Settings Overlay -->
<div class="settings-overlay" id="settings-overlay" onclick="if(event.target===this)toggleSettings()">
  <div class="settings-panel">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
      <h2>Settings</h2>
      <button class="btn btn-ghost btn-sm" onclick="toggleSettings()">&times;</button>
    </div>

    <!-- RSS Feeds -->
    <h3>RSS Feeds</h3>
    <div class="settings-group">
      <div id="feed-list"></div>
      <div class="settings-row" style="margin-top:8px;">
        <input type="text" id="new-feed-url" placeholder="https://example.com/rss.xml" style="flex:1;">
        <button class="btn btn-sm btn-primary" onclick="addFeed()">Add</button>
        <button class="btn btn-sm" onclick="testFeed()">Test</button>
      </div>
      <div class="test-result" id="feed-test-result"></div>
    </div>

    <!-- Ticker Style -->
    <h3>Ticker Appearance</h3>
    <div class="settings-group">
      <div class="settings-row">
        <label>Speed</label>
        <span style="font-size:10px;color:var(--dim);">Slow</span>
        <input type="range" id="set-speed" min="20" max="200" value="50">
        <span style="font-size:10px;color:var(--dim);">Fast</span>
        <span id="set-speed-val" style="font-size:11px;min-width:45px;text-align:right;">50px/s</span>
      </div>
      <div class="settings-row">
        <label>Color</label>
        <input type="color" id="set-color" value="#fafafa">
        <span id="set-color-val" style="font-size:11px;color:var(--dim);">#fafafa</span>
      </div>
      <div class="settings-row">
        <label>Font</label>
        <select id="set-font">
          <option value="'SF Mono','Cascadia Code',monospace">Monospace</option>
          <option value="'Inter','Segoe UI',sans-serif">Sans-serif</option>
          <option value="'Georgia','Times New Roman',serif">Serif</option>
        </select>
      </div>
      <div class="settings-row">
        <label>Size</label>
        <span style="font-size:10px;color:var(--dim);">10</span>
        <input type="range" id="set-fontsize" min="10" max="24" value="13">
        <span style="font-size:10px;color:var(--dim);">24</span>
        <span id="set-fontsize-val" style="font-size:11px;min-width:35px;text-align:right;">13px</span>
      </div>
    </div>

    <!-- INT Features -->
    <div id="int-settings" style="display:none;">
      <h3>INT Team Features</h3>
      <div class="settings-group" id="int-settings-body">
        <div class="settings-row">
          <label>Ops view</label>
          <label class="toggle"><input type="checkbox" id="set-ops-enabled" onchange="saveSettings()"><span class="toggle-slider"></span></label>
          <span style="font-size:11px;color:var(--dim);">Show Ops dashboard in sidebar</span>
        </div>
        <div class="settings-row">
          <label>Linear link</label>
          <label class="toggle"><input type="checkbox" id="set-linear-enabled" onchange="saveSettings()"><span class="toggle-slider"></span></label>
          <span style="font-size:11px;color:var(--dim);">Show Linear in sidebar</span>
        </div>
        <div class="settings-row">
          <label>Linear URL</label>
          <input type="text" id="set-linear-url" placeholder="https://linear.app/your-workspace" value="">
        </div>
        <div class="settings-row">
          <label>Ticker</label>
          <label class="toggle"><input type="checkbox" id="set-linear-ticker" onchange="saveSettings()"><span class="toggle-slider"></span></label>
          <span style="font-size:11px;color:var(--dim);">Include Linear issues in ticker</span>
        </div>
      </div>
      <div class="int-notice" id="int-notice" style="display:none;">
        Restricted to Phenom-earth/INT team members.
      </div>
    </div>

    <!-- Actions -->
    <div style="display:flex;gap:8px;justify-content:flex-end;border-top:1px solid var(--border);padding-top:16px;margin-top:20px;">
      <button class="btn btn-sm" onclick="resetSettings()">Reset</button>
      <button class="btn btn-sm btn-primary" onclick="saveSettings();toggleSettings()">Save &amp; Close</button>
    </div>
  </div>
</div>

<!-- RSS Ticker -->
<div class="ticker">
  <button class="ticker-settings-btn" onclick="toggleSettings()" title="Settings">&#9881;</button>
  <div class="ticker-content">
    <span class="ticker-text" id="ticker-text"></span>
  </div>
</div>

<script>
// ============================================================
// View Switching
// ============================================================
let currentView = 'ghostmode';

function switchView(view) {
  currentView = view;
  const frame = document.getElementById('view-frame');

  // Update sidebar active state
  document.querySelectorAll('.sidebar-item').forEach(el => el.classList.remove('active'));
  const navEl = document.getElementById('nav-' + view);
  if (navEl) navEl.classList.add('active');

  // Switch iframe source
  if (view === 'ghostmode') {
    frame.src = '/ghostmode/';
  } else if (view === 'ops') {
    frame.src = '/grafana/d/nest-ops/nest-ops?kiosk';
  }
}

// ============================================================
// Settings
// ============================================================
const SETTINGS_KEY = 'nest-ops-settings';
let settings = loadSettings();
let isIntMember = false;

function defaultSettings() {
  return {
    feeds: [],
    speed: 50,
    fontColor: '#fafafa',
    fontFamily: "'SF Mono','Cascadia Code',monospace",
    fontSize: 13,
    opsEnabled: false,
    linearEnabled: false,
    linearUrl: 'https://linear.app/phenom',
    linearTicker: false,
  };
}

function loadSettings() {
  try {
    const saved = localStorage.getItem(SETTINGS_KEY);
    return saved ? {...defaultSettings(), ...JSON.parse(saved)} : defaultSettings();
  } catch(e) { return defaultSettings(); }
}

function saveSettings() {
  settings.speed = parseInt(document.getElementById('set-speed').value);
  settings.fontColor = document.getElementById('set-color').value;
  settings.fontFamily = document.getElementById('set-font').value;
  settings.fontSize = parseInt(document.getElementById('set-fontsize').value);
  settings.opsEnabled = document.getElementById('set-ops-enabled').checked;
  settings.linearEnabled = document.getElementById('set-linear-enabled').checked;
  settings.linearUrl = document.getElementById('set-linear-url').value.trim();
  settings.linearTicker = document.getElementById('set-linear-ticker').checked;
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  applySettings();
}

function resetSettings() {
  localStorage.removeItem(SETTINGS_KEY);
  settings = defaultSettings();
  applySettingsToUI();
  applySettings();
}

function applySettingsToUI() {
  document.getElementById('set-speed').value = settings.speed;
  document.getElementById('set-speed-val').textContent = settings.speed + 'px/s';
  document.getElementById('set-color').value = settings.fontColor;
  document.getElementById('set-color-val').textContent = settings.fontColor;
  document.getElementById('set-font').value = settings.fontFamily;
  document.getElementById('set-fontsize').value = settings.fontSize;
  document.getElementById('set-fontsize-val').textContent = settings.fontSize + 'px';
  document.getElementById('set-ops-enabled').checked = settings.opsEnabled;
  document.getElementById('set-linear-enabled').checked = settings.linearEnabled;
  document.getElementById('set-linear-url').value = settings.linearUrl;
  document.getElementById('set-linear-ticker').checked = settings.linearTicker;
  renderFeedList();
}

function applySettings() {
  // Sidebar visibility
  const opsNav = document.getElementById('nav-ops');
  const linearNav = document.getElementById('nav-linear');
  const intLinks = document.getElementById('int-links');

  if (isIntMember) {
    opsNav.style.display = settings.opsEnabled ? '' : 'none';
    linearNav.style.display = settings.linearEnabled ? '' : 'none';
    if (settings.linearEnabled && settings.linearUrl) {
      linearNav.href = settings.linearUrl;
    }
    intLinks.style.display = (settings.opsEnabled || settings.linearEnabled) ? '' : 'none';
  }

  // Ticker style
  const tickerEl = document.getElementById('ticker-text');
  tickerEl.style.color = settings.fontColor;
  tickerEl.style.fontFamily = settings.fontFamily;
  tickerEl.style.fontSize = settings.fontSize + 'px';
}

function toggleSettings() {
  const overlay = document.getElementById('settings-overlay');
  overlay.classList.toggle('open');
  if (overlay.classList.contains('open')) {
    applySettingsToUI();
  }
}

// Live preview for sliders
document.getElementById('set-speed').addEventListener('input', e => {
  document.getElementById('set-speed-val').textContent = e.target.value + 'px/s';
});
document.getElementById('set-fontsize').addEventListener('input', e => {
  document.getElementById('set-fontsize-val').textContent = e.target.value + 'px';
});
document.getElementById('set-color').addEventListener('input', e => {
  document.getElementById('set-color-val').textContent = e.target.value;
});

// ============================================================
// Feed Management
// ============================================================
function renderFeedList() {
  const list = document.getElementById('feed-list');
  if (settings.feeds.length === 0) {
    list.innerHTML = '<div style="color:var(--dim);font-size:12px;padding:4px 0;">No feeds configured</div>';
    return;
  }
  list.innerHTML = settings.feeds.map((url, i) =>
    '<div class="feed-list-item">' +
    '<span title="' + esc(url) + '">' + esc(url) + '</span>' +
    '<button class="btn btn-ghost btn-sm" onclick="removeFeed(' + i + ')">&times;</button>' +
    '</div>'
  ).join('');
}

function addFeed() {
  const input = document.getElementById('new-feed-url');
  const url = input.value.trim();
  if (!url || !url.match(/^https?:\/\/.+/)) {
    input.style.borderColor = 'var(--red)';
    return;
  }
  input.style.borderColor = '';
  if (!settings.feeds.includes(url)) {
    settings.feeds.push(url);
    saveSettings();
  }
  input.value = '';
  renderFeedList();
}

function removeFeed(index) {
  settings.feeds.splice(index, 1);
  saveSettings();
  renderFeedList();
}

async function testFeed() {
  const url = document.getElementById('new-feed-url').value.trim();
  const result = document.getElementById('feed-test-result');
  if (!url) return;
  result.classList.add('visible');
  result.textContent = 'Fetching...';
  result.style.borderColor = 'var(--border)';
  try {
    const resp = await fetch('/ghostmode/api/rss?url=' + encodeURIComponent(url) + '&max=5');
    const data = await resp.json();
    if (!data.ok) {
      result.textContent = 'Error: ' + (data.error || 'Unknown');
      result.style.borderColor = 'var(--red)';
      return;
    }
    result.textContent = data.items.length + ' headlines found:\n' +
      data.items.map(i => '  ' + i.title).join('\n');
    result.style.borderColor = 'var(--green)';
  } catch(e) {
    result.textContent = 'Error: ' + e.message;
    result.style.borderColor = 'var(--red)';
  }
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

// ============================================================
// RSS Ticker Engine
// ============================================================
const Ticker = {
  headlines: [],
  currentIndex: 0,
  timeout: null,

  async fetchAll() {
    this.headlines = [];

    // RSS feeds
    for (const feedUrl of settings.feeds) {
      try {
        const resp = await fetch('/ghostmode/api/rss?url=' + encodeURIComponent(feedUrl));
        const data = await resp.json();
        if (data.ok && data.items) {
          for (const item of data.items) {
            this.headlines.push({ title: item.title, link: item.link });
          }
        }
      } catch(e) { /* skip */ }
    }

    // Linear issues (if INT member and enabled)
    if (isIntMember && settings.linearTicker) {
      try {
        const resp = await fetch('/ghostmode/api/linear/issues?limit=10');
        const data = await resp.json();
        if (data.ok && data.items) {
          for (const item of data.items) {
            this.headlines.push({ title: item.title, link: item.link });
          }
        }
      } catch(e) { /* skip */ }
    }

    if (this.headlines.length === 0) {
      this.headlines = [{ title: 'No feeds configured \u2014 click \u2699 to add RSS feeds', link: '' }];
    }
  },

  async start() {
    await this.fetchAll();
    this.cycle();
    // Refresh feeds every 5 minutes
    setInterval(() => this.fetchAll(), 300000);
  },

  cycle() {
    if (this.headlines.length === 0) return;
    const el = document.getElementById('ticker-text');
    const h = this.headlines[this.currentIndex];
    const container = el.parentElement;

    // Set content
    if (h.link) {
      el.innerHTML = '<a href="' + esc(h.link) + '" target="_blank" rel="noopener">' + esc(h.title) + '</a>';
    } else {
      el.textContent = h.title;
    }

    // Slide in from right
    const cw = container.offsetWidth;
    el.style.transition = 'none';
    el.style.transform = 'translateX(' + cw + 'px)';

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        // Scroll to center
        const slideDuration = cw / settings.speed;
        el.style.transition = 'transform ' + slideDuration + 's linear';
        el.style.transform = 'translateX(0)';

        // Pause 3 seconds, then slide out
        this.timeout = setTimeout(() => {
          const ew = el.offsetWidth;
          const exitDuration = ew / settings.speed;
          el.style.transition = 'transform ' + exitDuration + 's linear';
          el.style.transform = 'translateX(-' + ew + 'px)';

          this.timeout = setTimeout(() => {
            this.currentIndex = (this.currentIndex + 1) % this.headlines.length;
            this.cycle();
          }, exitDuration * 1000);
        }, 3000);
      });
    });
  },
};

// ============================================================
// Auth & Permissions
// ============================================================
async function checkPermissions() {
  try {
    const resp = await fetch('/ghostmode/api/auth/permissions');
    const data = await resp.json();
    isIntMember = data.int_team_member === true;
  } catch(e) {
    isIntMember = false;
  }

  // Show/hide INT features
  const intSettings = document.getElementById('int-settings');
  const intNotice = document.getElementById('int-notice');
  const intBody = document.getElementById('int-settings-body');

  intSettings.style.display = '';
  if (isIntMember) {
    intBody.classList.remove('int-disabled');
    intNotice.style.display = 'none';
  } else {
    intBody.classList.add('int-disabled');
    intNotice.style.display = '';
  }

  applySettings();
}

// ============================================================
// Init
// ============================================================
checkPermissions();
applySettings();
Ticker.start();
</script>
</body>
</html>"""
