"""N.E.S.T. Ops wrapper page for nest-ops.thephenom.app.

Serves a frosted top bar (title, Ghost Mode <-> Ops board toggle, profile
avatar) over a full-bleed board iframe, plus the RSS ticker. Settings live
in a dropdown under the avatar; identity comes from the verified ALB OIDC
claims via /api/auth/permissions. The boards themselves are served by this
host at /ghostmode/ and /ops/.
"""

from ghostmode import __version__
from ghostmode.brand import BACKDROP_CSS, backdrop_div


def build_nest_wrapper() -> str:
    """Build the N.E.S.T. Ops wrapper — full composition, no iframes (#45).

    The ghostmode board is inlined server-side (scoped fragment); the
    Infrastructure board renders client-side from OpenUI Lang fetched at
    /api/ui/ops via the self-hosted @openuidev/browser-bundle."""
    from ghostmode.dashboard import build_dashboard_fragment
    frag = build_dashboard_fragment()
    # board head extras: only leaflet (the wrapper has its own fonts/favicon)
    leaflet = "\n".join(
        line for line in frag["head_extras"].splitlines() if "leaflet" in line
    )
    # content-hash cache-busting (osint #50 follow-up): the bundle is served
    # with max-age=86400, so a patched artifact under the same URL kept
    # serving stale from browser caches (M saw the pre-patch pager).
    import hashlib
    from pathlib import Path
    def _v(name: str) -> str:
        f = Path(__file__).parent / "static" / "openui" / name
        try:
            return hashlib.sha256(f.read_bytes()).hexdigest()[:10]
        except OSError:
            return "0"
    board_head = (
        leaflet
        + f'\n<link rel="stylesheet" href="/assets/openui/openui-styles.css?v={_v("openui-styles.css")}">'
        + f'\n<script src="/assets/openui/openui-bundle.min.js?v={_v("openui-bundle.min.js")}"></script>'
    )
    html = (_NEST_HTML
            .replace("$version", __version__)
            .replace("$backdrop_css", BACKDROP_CSS)
            .replace("$board_head", board_head)
            .replace("$ghostmode_css", frag["css"])
            .replace("$ghostmode_body", frag["body"])
            .replace("$ghostmode_js", frag["js"]))
    return html.replace("<body>", "<body>\n" + backdrop_div(), 1)


_NEST_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;700&family=Roboto+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAA7EAAAOxAGVKw4bAAADxklEQVRYhaXXW4iVVRQH8N8chmEokRARCfGDwYcIkwi+7thNwuhCFAUWXciKICLmQSYfJERCJHowE7LsXuKDRQSFUYSYBHkiI0JIotoiIiYyyCDDEKce1j4zZ47n8s34h8Oc8317r/Xfa639X2sGVEC9KJbiSyxDA7Uen3NYV6Z0oIrtgQrOB7EZL2UHVfAVHixTmuy3sIrBK/DcHJzDGtxXL4q+C3sarRfFAmzCojk4hyG8IlI2fwK4E2vn6LyJFXi+XhRD8yJQL4qFGMPCeRKAx3H1nAnUi6KGp/ttroDLsaVXFLpFYASjIpcXi9V4JB/qAgx22bQGp3Gi7Xm7kcWCbC8M4wXsw0T7ywt0IOd+gRCcbo5rgvwQfsRlPQg0sBsvYqpMqdXu7Ajka/cJbu5hsElgP57ANiFU3dL1d16zCUdEJGYZajqH+3G7OFGvz3lsz0q3Gz91cf4vdmVyT2GsXhSLOxLIhl/GJV2MteL9ptMypTNCdM51WHcYe7EBS7AKz7YWZA3yNRkV4tEPx7CtTGmq5dl3+LBt3aRIzZVCD2oiEmOtfppMVuLJCs7Pi9OOtz7MqdiK4/lRA59lsmNm19pCbM7FrpbDMYrlFQgcwr4ypU7vTuFVcfKJTGgtbuyw9h5x1Q3Ui+JhvCOuXi+cwr1lSt0KTr0ohsXccAjv4XvdG9IvuKsmQtTPObyVN3VFTsVodr5BSHE3rMToQL0o/qvg/DRKcZoRTJmpn9abVBP5XyRqpV8jGx8U+eoXgSW4Xly1nRUMV0EDe2p4QwhGP2wUveFjs2V6vjiG7TXswG8VNqwS0rtVpORi0MCuMqVjtTKlk9iiQ6dqQ03I6YjQ9r4DZw9MC9cA001op1CsfjiIx/ABbp2H8wk8KtJ+brod14tihWitVQbQ9aIePlXtCjfRECc/kvdd2nqF/hRKNtVhYzs24qQoyLnguNCISZzFjmkCeVB4Ez9XMLRCCNhrOFPR+ZQo+ENYKqap0U4T0UrRwWoiTBNirJps+d0QDWa/0PqR/H5YaMVU/i7/HhIN7IcypfF6USzDNRjvNCgOiyJbLkI8hM+zwz1CXteJzjiOW3AAf5QpvZ5Pt15c7b3iP6vDuK1JqkzpRJnSF2VKBzsRWJ4335RPXIrrd10mcxW+xq95/QN4CEty9Ip8gGfEkHODmLRWt0RlGp0INERYPzLT99vnvXEzafhWzJCDZvr+kJmh9RTuyHsumMK7EdhWprQvfz+Ld/FPfj+Ju3Ft/v27aME1HM1/38Y3ee1fovqPdvDlfz6c/nVOJQiPAAAAAElFTkSuQmCC">
<title>N.E.S.T. Ops — dev-nest.thephenom.app</title>
$board_head
<style>
:root {
  --bg: #050406; --card: rgba(20,18,22,0.10); --border: rgba(255,255,255,0.10); --text: #fafafa;
  --dim: #a1a1aa; --green: #4ade80; --red: #d73429; --yellow: #fbbf24;
  --blue: #a5e3e8; --purple: #c084fc; --accent: #d73429;
  --topbar-h: 48px;
  --ticker-h: 40px;
  --mono: 'Roboto Mono','SF Mono','JetBrains Mono',monospace;
  --sans: 'Roboto Mono','Inter',-apple-system,sans-serif;
  --hero: 'Oswald','Impact',sans-serif;
}
* { margin:0; padding:0; box-sizing:border-box; }
html { background:#060606; }
html, body { height:100%; overflow:hidden; color:var(--text); font-family:var(--sans); }
/* Phenom perspective-floor backdrop (matches www.thephenom.app) */
body { background:transparent; }
$backdrop_css

/* === Top Bar (replaces the sidebar — M directive 2026-06-04: the board
   toggle does the trick, settings live under the profile avatar) === */
.topbar {
  position:fixed; top:0; left:0; right:0; height:var(--topbar-h);
  display:flex; align-items:center; justify-content:space-between; padding:0 12px;
  background:var(--card); border-bottom:1px solid var(--border);
  -webkit-backdrop-filter:blur(18px) saturate(160%); backdrop-filter:blur(18px) saturate(160%);
  z-index:100;
}
.topbar-title { display:flex; align-items:baseline; gap:10px; }
/* Oswald hero type runs cyan-500, matching www feature/114 tokens.css */
.topbar-title h1 { font-size:19px; font-weight:700; letter-spacing:0.3px; font-family:var(--hero); color:var(--blue); }
.topbar-version { font-size:10px; color:var(--dim); font-family:var(--mono); }
.topbar-controls { display:flex; align-items:center; gap:14px; }
.board-toggle { display:flex; align-items:center; gap:8px; }
.board-label { font-size:12px; color:var(--dim); font-family:var(--mono); transition:color 0.15s; }
.board-label.active { color:var(--text); }
.badge-int {
  font-size:10px; padding:1px 6px; border-radius:10px;
  background:rgba(215,52,41,.18); color:#d73429; font-weight:600;
}
.avatar-btn {
  width:32px; height:32px; border-radius:50%; border:1px solid var(--blue);
  background:var(--card); color:var(--blue); font-weight:700; font-size:13px;
  cursor:pointer; display:flex; align-items:center; justify-content:center;
  font-family:var(--sans); transition:box-shadow 0.15s;
}
.avatar-btn:hover { box-shadow:0 0 0 3px rgba(165,227,232,0.25); }
.avatar-btn, .avatar-lg { overflow:hidden; }
.avatar-img { width:100%; height:100%; border-radius:50%; object-fit:cover; display:block; }
.profile-head {
  display:flex; align-items:center; gap:12px; padding-bottom:14px;
  border-bottom:1px solid var(--border); margin-bottom:14px;
}
.avatar-lg {
  width:40px; height:40px; border-radius:50%; border:1px solid var(--blue);
  color:var(--blue); font-weight:700; font-size:16px; flex-shrink:0;
  display:flex; align-items:center; justify-content:center;
}
.profile-email { font-size:12px; color:var(--text); font-family:var(--mono); word-break:break-all; }
.profile-sub { font-size:10px; color:var(--dim); margin-top:2px; }

/* === Main Content (composed panes, no iframes — osint #45) === */
.main {
  position:fixed; top:var(--topbar-h); left:0; right:0; bottom:var(--ticker-h);
  overflow-y:auto; -webkit-overflow-scrolling:touch;
}
.board-pane { max-width:960px; margin:0 auto; padding:1.5rem; }
/* osint #48: re-skin the OpenUI bundle to the Phenom design system.
   The bundle has no dark mode — theming is via --openui-* custom props,
   which inherit, so scoping the overrides to the pane is sufficient. */
#pane-ops {
  color:var(--text);
  /* match the brand .card alpha exactly (M: 'not transparent enough', x3) —
     the frosted blur carries readability, not the fill */
  --openui-background: rgba(20,18,22,0.10);
  --openui-foreground: rgba(28,26,32,0.92);
  --openui-popover-background: rgba(28,26,32,0.97);
  --openui-sunk-light: rgba(255,255,255,0.02);
  --openui-sunk: rgba(255,255,255,0.04);
  --openui-sunk-deep: rgba(255,255,255,0.08);
  --openui-elevated-light: rgba(255,255,255,0.04);
  --openui-elevated: rgba(255,255,255,0.08);
  --openui-elevated-strong: rgba(255,255,255,0.14);
  --openui-elevated-intense: rgba(255,255,255,0.24);
  --openui-highlight-subtle: rgba(255,255,255,0.02);
  --openui-highlight: rgba(255,255,255,0.04);
  --openui-highlight-strong: rgba(255,255,255,0.08);
  --openui-highlight-intense: rgba(255,255,255,0.24);
  --openui-inverted-background: rgba(236,236,240,1);
  --openui-text-neutral-primary: #ececf0;
  --openui-text-neutral-secondary: rgba(236,236,240,0.55);
  --openui-text-neutral-tertiary: rgba(236,236,240,0.28);
  --openui-text-neutral-link: #a5e3e8;
  --openui-text-brand: #a5e3e8;
  --openui-border-default: rgba(255,255,255,0.10);
  --openui-font-body: 'Roboto Mono','SF Mono',monospace;
  --openui-font-heading: 'Oswald','Impact',sans-serif;
  --openui-font-label: 'Roboto Mono','SF Mono',monospace;
  --openui-font-code: 'Roboto Mono','SF Mono',monospace;
  --openui-font-numbers: 'Roboto Mono','SF Mono',monospace;
  --openui-success-background: rgba(74,222,128,0.14);
  --openui-alert-background: rgba(251,191,36,0.16);
  --openui-danger-background: rgba(215,52,41,0.16);
  --openui-info-background: rgba(165,227,232,0.14);
}
/* M directive: Infrastructure table data reads in brand cyan. Status/
   latency/TLS Tags keep their variant colors (they set their own). */
#pane-ops table td { color:#a5e3e8 !important; }
/* osint #50: long cell content must wrap, never clip — the bundle's table
   truncates with ellipsis/hidden overflow at our column count */
#pane-ops table td, #pane-ops table th,
#pane-ops [class*="table"] td, #pane-ops [class*="table"] th {
  white-space: normal !important;
  overflow: visible !important;
  text-overflow: clip !important;
  word-break: break-word;
}
/* frosted-glass treatment on the OpenUI card to match the brand panes */
#pane-ops .openui-card, #pane-ops [class*="card"] {
  -webkit-backdrop-filter: blur(18px) saturate(160%);
  backdrop-filter: blur(18px) saturate(160%);
}
$ghostmode_css

/* === RSS Ticker === */
.ticker {
  position:fixed; bottom:0; left:0; right:0; height:var(--ticker-h);
  background:var(--card); border-top:1px solid var(--border);
  -webkit-backdrop-filter:blur(18px) saturate(160%); backdrop-filter:blur(18px) saturate(160%);
  display:flex; align-items:center; z-index:100;
}
.ticker-content {
  flex:1; overflow:hidden; white-space:nowrap; font-family:var(--mono); font-size:13px;
}
.ticker-text {
  display:inline-block; color:var(--text); transition:transform 0.5s linear;
}
.ticker-text a { color:inherit; text-decoration:none; cursor:pointer; }
.ticker-text a:hover { text-decoration:underline; color:var(--accent); }

/* === Settings Panel === */
.settings-overlay {
  display:none; position:fixed; top:0; left:0; right:0; bottom:0;
  background:rgba(0,0,0,0.5); z-index:200;
}
.settings-overlay.open { display:block; }
.settings-panel {
  position:fixed; top:calc(var(--topbar-h) + 4px); right:8px; width:440px;
  max-height:calc(100vh - var(--topbar-h) - var(--ticker-h) - 16px);
  background:var(--card); border:1px solid var(--border); border-radius:12px;
  -webkit-backdrop-filter:blur(18px) saturate(160%); backdrop-filter:blur(18px) saturate(160%);
  box-shadow:0 8px 32px rgba(0,0,0,0.5); z-index:201; overflow-y:auto; padding:24px;
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
  .topbar { padding:0 8px; }
  /* Hide the inactive label but keep the ACTIVE board named — a bare switch
     with no indicator is anonymous on mobile (Moneypenny 390px audit). */
  .board-label { display:none; }
  .board-label.active { display:inline; }
  .settings-panel { width:100%; right:0; border-radius:0 0 8px 8px; }
}
</style>
</head>
<body>

<!-- Top bar: title, board toggle, profile avatar (sidebar retired — M, 2026-06-04) -->
<header class="topbar">
  <div class="topbar-title">
    <h1>N.E.S.T. Ops</h1>
    <span class="topbar-version">v$version</span>
  </div>
  <div class="topbar-controls">
    <div class="board-toggle" id="board-toggle-wrap" style="display:none;">
      <span class="board-label active" id="label-ghostmode">Ghost Mode</span>
      <label class="toggle"><input type="checkbox" id="board-toggle" onchange="onBoardToggle(this)"><span class="toggle-slider"></span></label>
      <span class="board-label" id="label-ops">Ops <span class="badge-int">INT</span></span>
    </div>
    <button class="avatar-btn" id="avatar-btn" onclick="toggleSettings()" title="Account &amp; settings">
      <span id="avatar-initial">?</span>
    </button>
  </div>
</header>

<!-- Main Content: composed board panes (osint #45 — no iframes) -->
<div class="main" id="main-content">
  <div id="pane-ghostmode" class="board-pane">
$ghostmode_body
  </div>
  <div id="pane-ops" class="board-pane" style="display:none"></div>
</div>

<!-- Settings Overlay -->
<div class="settings-overlay" id="settings-overlay" onclick="if(event.target===this)toggleSettings()">
  <div class="settings-panel">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
      <h2>Settings</h2>
      <button class="btn btn-ghost btn-sm" onclick="toggleSettings()">&times;</button>
    </div>

    <!-- Signed-in identity (verified ALB OIDC claims via /api/auth/permissions) -->
    <div class="profile-head">
      <div class="avatar-lg" id="avatar-initial-lg">?</div>
      <div>
        <div class="profile-email" id="profile-email">&hellip;</div>
        <div class="profile-sub">Signed in via Cognito (ALB OIDC)</div>
      </div>
    </div>

    <!-- RSS Feed Catalog -->
    <h3>RSS Feeds</h3>
    <div class="settings-group" id="feed-catalog" style="max-height:280px;overflow-y:auto;border:1px solid var(--border);border-radius:6px;padding:4px;"></div>

    <!-- Ticker Behaviour -->
    <h3>Ticker Behaviour</h3>
    <div class="settings-group">
      <div class="settings-row">
        <label>Refresh</label>
        <select id="set-refresh">
          <option value="600000">10 min</option>
          <option value="1800000">30 min</option>
          <option value="3600000">1 hour</option>
          <option value="86400000">1 day</option>
        </select>
      </div>
      <div class="settings-row">
        <label>Max age</label>
        <select id="set-maxage">
          <option value="1">1 day</option>
          <option value="3">3 days</option>
          <option value="7">7 days</option>
          <option value="14">14 days</option>
          <option value="30">30 days</option>
        </select>
      </div>
      <div class="settings-row">
        <label>Playlist</label>
        <span style="font-size:10px;color:var(--dim);">5</span>
        <input type="range" id="set-maxitems" min="5" max="100" value="25">
        <span style="font-size:10px;color:var(--dim);">100</span>
        <span id="set-maxitems-val" style="font-size:11px;min-width:35px;text-align:right;">25</span>
      </div>
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
          <span style="font-size:11px;color:var(--dim);">Show the Ghost Mode &#8644; Ops board toggle</span>
        </div>
        <div class="settings-row">
          <label>Linear link</label>
          <label class="toggle"><input type="checkbox" id="set-linear-enabled" onchange="saveSettings()"><span class="toggle-slider"></span></label>
          <span style="font-size:11px;color:var(--dim);">Show the Linear quick link below</span>
        </div>
        <div class="settings-row">
          <label>Linear URL</label>
          <input type="text" id="set-linear-url" placeholder="https://linear.app/phenom-earth/" value="https://linear.app/phenom-earth/">
        </div>
        <div class="settings-row">
          <label>Ticker</label>
          <label class="toggle"><input type="checkbox" id="set-linear-ticker" onchange="saveSettings()"><span class="toggle-slider"></span></label>
          <span style="font-size:11px;color:var(--dim);">Include Linear issues in ticker</span>
        </div>
        <div class="settings-row">
          <a id="nav-linear" href="https://linear.app/phenom-earth/" target="_blank" rel="noopener" style="display:none;font-size:12px;color:var(--blue);text-decoration:none;">Open Linear &#8599;</a>
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

<!-- RSS Ticker (settings moved under the profile avatar) -->
<div class="ticker">
  <div class="ticker-content">
    <span class="ticker-text" id="ticker-text"></span>
  </div>
</div>

<script>
// ============================================================
// View Switching
// ============================================================
// Base path detection — works behind reverse proxies (e.g. /proxy/3201/)
const BASE = (function() {
  // Use the current page's path as the base, stripping trailing filename
  const p = window.location.pathname;
  // If path ends with / it's already a directory
  return p.endsWith('/') ? p : p.substring(0, p.lastIndexOf('/') + 1);
})();
function apiUrl(path) { return BASE + path.replace(/^\//, ''); }

let currentView = 'ghostmode';

let opsRefreshTimer = null;
let opsRoot = null;

async function renderOpsBoard() {
  // OpenUI Lang from the server, rendered by the self-hosted bundle (#45)
  try {
    const resp = await fetch(apiUrl('api/ui/ops'));
    if (!resp.ok) {
      document.getElementById('pane-ops').innerHTML =
        '<p style="color:var(--dim);padding:2rem;text-align:center;">' +
        (resp.status === 403 ? 'Infrastructure requires INT access.' : 'Failed to load board (' + resp.status + ').') + '</p>';
      return;
    }
    const lang = await resp.text();
    const pane = document.getElementById('pane-ops');
    const { React, createRoot, Renderer, openuiChatLibrary } = window.__OpenUI;
    if (!opsRoot) {
      pane.innerHTML = '<div id="openui-ops-root"></div>';
      opsRoot = createRoot(document.getElementById('openui-ops-root'));
    }
    // verified contract of the published bundle (#45): prop is `response`,
    // and openuiChatLibrary IS the library object (README's destructure lies)
    opsRoot.render(React.createElement(Renderer, {
      response: lang, library: openuiChatLibrary,
    }));
  } catch (e) {
    document.getElementById('pane-ops').textContent = 'Board error: ' + e;
  }
}

function switchView(view) {
  currentView = view;

  // Sync the board toggle (checked = Ops)
  const cb = document.getElementById('board-toggle');
  if (cb) cb.checked = (view === 'ops');
  document.getElementById('label-ghostmode').classList.toggle('active', view === 'ghostmode');
  document.getElementById('label-ops').classList.toggle('active', view === 'ops');

  // Pane swap — both boards live in this document (#45, no iframes)
  document.getElementById('pane-ghostmode').style.display = (view === 'ghostmode') ? '' : 'none';
  document.getElementById('pane-ops').style.display = (view === 'ops') ? '' : 'none';

  if (view === 'ops') {
    renderOpsBoard();  // fresh probes on entry
    if (!opsRefreshTimer) opsRefreshTimer = setInterval(renderOpsBoard, 60000);
  } else if (opsRefreshTimer) {
    clearInterval(opsRefreshTimer); opsRefreshTimer = null;
  }
}

function onBoardToggle(cb) {
  switchView(cb.checked ? 'ops' : 'ghostmode');
}

// ============================================================
// Settings
// ============================================================
const SETTINGS_KEY = 'nest-ops-settings-v2';  // v2: opsEnabled defaults true (#45)
let settings = loadSettings();
let isIntMember = false;

// Curated feed catalog — verified, well-known, safe XML feeds
const FEED_CATALOG = [
  { id: 'bbc-world',      name: 'BBC World News',          url: 'https://feeds.bbci.co.uk/news/world/rss.xml',               category: 'News' },
  { id: 'bbc-tech',       name: 'BBC Technology',           url: 'https://feeds.bbci.co.uk/news/technology/rss.xml',           category: 'Tech' },
  { id: 'reuters-world',  name: 'Reuters World',            url: 'https://www.reutersagency.com/feed/?best-topics=world',      category: 'News' },
  { id: 'reuters-tech',   name: 'Reuters Technology',       url: 'https://www.reutersagency.com/feed/?best-topics=tech',       category: 'Tech' },
  { id: 'hn-front',       name: 'Hacker News (Front Page)', url: 'https://hnrss.org/frontpage',                               category: 'Tech' },
  { id: 'hn-best',        name: 'Hacker News (Best)',       url: 'https://hnrss.org/best',                                    category: 'Tech' },
  { id: 'ars-tech',       name: 'Ars Technica',             url: 'https://feeds.arstechnica.com/arstechnica/index',            category: 'Tech' },
  { id: 'tc-news',        name: 'TechCrunch',               url: 'https://techcrunch.com/feed/',                               category: 'Tech' },
  { id: 'wired-top',      name: 'WIRED Top Stories',        url: 'https://www.wired.com/feed/rss',                             category: 'Tech' },
  { id: 'verge-all',      name: 'The Verge',                url: 'https://www.theverge.com/rss/index.xml',                     category: 'Tech' },
  { id: 'krebs-sec',      name: 'Krebs on Security',        url: 'https://krebsonsecurity.com/feed/',                          category: 'Security' },
  { id: 'schneier',       name: 'Schneier on Security',     url: 'https://www.schneier.com/feed/atom/',                        category: 'Security' },
  { id: 'thehackernews',  name: 'The Hacker News',          url: 'https://feeds.feedburner.com/TheHackersNews',                category: 'Security' },
  { id: 'bleeping',       name: 'BleepingComputer',         url: 'https://www.bleepingcomputer.com/feed/',                     category: 'Security' },
  { id: 'nist-vuln',      name: 'NIST NVD (CVEs)',          url: 'https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml',        category: 'Security' },
  { id: 'github-blog',    name: 'GitHub Blog',              url: 'https://github.blog/feed/',                                  category: 'Dev' },
  { id: 'aws-whats-new',  name: 'AWS What\'s New',          url: 'https://aws.amazon.com/about-aws/whats-new/recent/feed/',    category: 'Cloud' },
  { id: 'gcp-blog',       name: 'Google Cloud Blog',        url: 'https://cloudblog.withgoogle.com/rss/',                      category: 'Cloud' },
  { id: 'cf-blog',        name: 'Cloudflare Blog',          url: 'https://blog.cloudflare.com/rss/',                           category: 'Cloud' },
  { id: 'ap-top',         name: 'AP News Top Stories',      url: 'https://rsshub.app/apnews/topics/apf-topnews',              category: 'News' },
  { id: 'nasa-breaking',  name: 'NASA Breaking News',       url: 'https://www.nasa.gov/news-release/feed/',                    category: 'Science' },
  { id: 'nature-latest',  name: 'Nature Latest Research',   url: 'https://www.nature.com/nature.rss',                          category: 'Science' },
];

function defaultSettings() {
  return {
    enabledFeeds: ['hn-front', 'krebs-sec', 'bbc-tech'],  // default enabled feeds
    refreshInterval: 600000,   // 10 minutes in ms
    maxAge: 1,                 // days — only show items newer than this
    maxItems: 25,              // max headlines in the ticker playlist
    speed: 50,
    fontColor: '#fafafa',
    fontFamily: "'SF Mono','Cascadia Code',monospace",
    fontSize: 13,
    // default ON since #45 — the switcher is the only way between boards;
    // non-INT users still never see it (isIntMember gate in applySettings)
    opsEnabled: true,
    linearEnabled: false,
    linearUrl: 'https://linear.app/phenom-earth/',
    linearTicker: false,
  };
}

function loadSettings() {
  try {
    const saved = localStorage.getItem(SETTINGS_KEY);
    const s = saved ? {...defaultSettings(), ...JSON.parse(saved)} : defaultSettings();
    // Migrate stale Linear URL defaults
    if (!s.linearUrl || s.linearUrl === 'https://linear.app/phenom' || s.linearUrl === '#') {
      s.linearUrl = 'https://linear.app/phenom-earth/';
    }
    return s;
  } catch(e) { return defaultSettings(); }
}

function saveSettings() {
  // Collect enabled feeds from catalog checkboxes
  settings.enabledFeeds = [];
  FEED_CATALOG.forEach(f => {
    const cb = document.getElementById('feed-' + f.id);
    if (cb && cb.checked) settings.enabledFeeds.push(f.id);
  });
  settings.refreshInterval = parseInt(document.getElementById('set-refresh').value);
  settings.maxAge = parseInt(document.getElementById('set-maxage').value);
  settings.maxItems = parseInt(document.getElementById('set-maxitems').value);
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
  Ticker.scheduleRefresh();
}

function resetSettings() {
  localStorage.removeItem(SETTINGS_KEY);
  settings = defaultSettings();
  applySettingsToUI();
  applySettings();
}

function applySettingsToUI() {
  // Feed catalog
  renderFeedCatalog();
  // Ticker behaviour
  document.getElementById('set-refresh').value = settings.refreshInterval;
  document.getElementById('set-maxage').value = settings.maxAge;
  document.getElementById('set-maxitems').value = settings.maxItems;
  document.getElementById('set-maxitems-val').textContent = settings.maxItems;
  // Ticker appearance
  document.getElementById('set-speed').value = settings.speed;
  document.getElementById('set-speed-val').textContent = settings.speed + 'px/s';
  document.getElementById('set-color').value = settings.fontColor;
  document.getElementById('set-color-val').textContent = settings.fontColor;
  document.getElementById('set-font').value = settings.fontFamily;
  document.getElementById('set-fontsize').value = settings.fontSize;
  document.getElementById('set-fontsize-val').textContent = settings.fontSize + 'px';
  // INT features
  document.getElementById('set-ops-enabled').checked = settings.opsEnabled;
  document.getElementById('set-linear-enabled').checked = settings.linearEnabled;
  document.getElementById('set-linear-url').value = settings.linearUrl;
  document.getElementById('set-linear-ticker').checked = settings.linearTicker;
}

function renderFeedCatalog() {
  const container = document.getElementById('feed-catalog');
  let currentCat = '';
  let html = '';
  FEED_CATALOG.forEach(f => {
    if (f.category !== currentCat) {
      currentCat = f.category;
      html += '<div style="font-size:10px;font-weight:600;color:var(--dim);text-transform:uppercase;letter-spacing:0.08em;padding:8px 8px 2px;">' + esc(currentCat) + '</div>';
    }
    const checked = settings.enabledFeeds.includes(f.id) ? 'checked' : '';
    html += '<label style="display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:4px;cursor:pointer;font-size:12px;" onmouseover="this.style.background=\'var(--border)\'" onmouseout="this.style.background=\'\'">' +
      '<input type="checkbox" id="feed-' + f.id + '" ' + checked + ' onchange="saveSettings()" style="accent-color:var(--accent);">' +
      '<span style="flex:1;">' + esc(f.name) + '</span>' +
      '<span style="font-size:10px;color:var(--dim);font-family:var(--mono);">' + esc(f.category) + '</span>' +
      '</label>';
  });
  container.innerHTML = html;
}

function applySettings() {
  // Board toggle visibility (replaces the old sidebar nav)
  const toggleWrap = document.getElementById('board-toggle-wrap');
  const canOps = isIntMember && settings.opsEnabled;
  toggleWrap.style.display = canOps ? '' : 'none';
  if (!canOps && currentView === 'ops') switchView('ghostmode');

  // Linear quick link in the profile dropdown
  const linearNav = document.getElementById('nav-linear');
  if (isIntMember && settings.linearEnabled) {
    linearNav.style.display = '';
    if (settings.linearUrl) linearNav.href = settings.linearUrl;
  } else {
    linearNav.style.display = 'none';
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
document.getElementById('set-maxitems').addEventListener('input', e => {
  document.getElementById('set-maxitems-val').textContent = e.target.value;
});

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

// ============================================================
// RSS Ticker Engine (catalog-based, play-count capped)
// ============================================================
const Ticker = {
  headlines: [],      // current playlist
  currentIndex: 0,
  timeout: null,
  refreshTimer: null,
  playCounts: {},     // title_hash -> count this hour
  playCountReset: 0,  // timestamp of last hourly reset
  MAX_PLAYS_PER_HOUR: 40,

  getEnabledFeedUrls() {
    return FEED_CATALOG
      .filter(f => settings.enabledFeeds.includes(f.id))
      .map(f => f.url);
  },

  async fetchAll() {
    const raw = [];
    const cutoff = Date.now() - (settings.maxAge * 86400000);

    // Fetch enabled RSS feeds
    for (const feedUrl of this.getEnabledFeedUrls()) {
      try {
        const resp = await fetch(apiUrl('api/rss?url=' + encodeURIComponent(feedUrl) + '&max=30'));
        const data = await resp.json();
        if (data.ok && data.items) {
          for (const item of data.items) {
            // Filter by age if published date is available
            if (item.published) {
              const pubTime = new Date(item.published).getTime();
              if (pubTime && pubTime < cutoff) continue;
            }
            raw.push({ title: item.title, link: item.link });
          }
        }
      } catch(e) { /* skip failed feeds */ }
    }

    // Linear issues (if INT member and enabled)
    if (isIntMember && settings.linearTicker) {
      try {
        const resp = await fetch(apiUrl('api/linear/issues?limit=10'));
        const data = await resp.json();
        if (data.ok && data.items) {
          for (const item of data.items) {
            raw.push({ title: item.title, link: item.link });
          }
        }
      } catch(e) { /* skip */ }
    }

    // Cap to maxItems, shuffle for variety
    if (raw.length > settings.maxItems) {
      for (let i = raw.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [raw[i], raw[j]] = [raw[j], raw[i]];
      }
      raw.length = settings.maxItems;
    }

    this.headlines = raw.length > 0 ? raw :
      [{ title: 'Enable feeds in Settings to populate the ticker', link: '' }];
    this.currentIndex = 0;
  },

  scheduleRefresh() {
    if (this.refreshTimer) clearInterval(this.refreshTimer);
    this.refreshTimer = setInterval(() => this.fetchAll(), settings.refreshInterval);
  },

  async start() {
    await this.fetchAll();
    this.scheduleRefresh();
    this.cycle();
  },

  canPlay(headline) {
    // Reset counts every hour
    const now = Date.now();
    if (now - this.playCountReset > 3600000) {
      this.playCounts = {};
      this.playCountReset = now;
    }
    const key = headline.title;
    const count = this.playCounts[key] || 0;
    return count < this.MAX_PLAYS_PER_HOUR;
  },

  recordPlay(headline) {
    const key = headline.title;
    this.playCounts[key] = (this.playCounts[key] || 0) + 1;
  },

  cycle() {
    if (this.headlines.length === 0) return;
    const el = document.getElementById('ticker-text');
    const container = el.parentElement;

    // Find next playable headline (skip those at 40 plays/hour cap)
    let attempts = 0;
    while (attempts < this.headlines.length) {
      const h = this.headlines[this.currentIndex];
      if (this.canPlay(h)) {
        this.recordPlay(h);
        this._showHeadline(el, container, h);
        return;
      }
      this.currentIndex = (this.currentIndex + 1) % this.headlines.length;
      attempts++;
    }
    // All items capped — show a placeholder
    el.textContent = 'All headlines played — waiting for refresh...';
  },

  _showHeadline(el, container, h) {

    // Set content (osint #24: only http(s) links — a hostile feed could
    // otherwise smuggle a javascript: URL into the ticker)
    if (h.link && /^https?:\/\//i.test(h.link)) {
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
// Animated Matrix avatar (dev-nest port, osint #43)
// ============================================================
function setAvatarImage(url) {
  for (const id of ['avatar-initial', 'avatar-initial-lg']) {
    const slot = document.getElementById(id);
    if (!slot) continue;
    const img = document.createElement('img');
    img.src = url; img.alt = ''; img.className = 'avatar-img';
    img.onerror = function() { img.remove(); };
    img.onload = function() { slot.textContent = ''; slot.appendChild(img); };
  }
}

const MATRIX_HS = 'https://chat.thephenom.app';
async function loadMatrixAvatar(sub) {
  try {
    // MXIDs on the phenom homeserver are @{cognito-sub}:chat.thephenom.app
    // (matrixUserIdFor in the dev-nest SPA — verified against the live
    // profile API, osint #50). The verified sub rides in /api/auth/permissions.
    if (!sub) return;
    const mxid = encodeURIComponent('@' + sub + ':chat.thephenom.app');
    const resp = await fetch(MATRIX_HS + '/_matrix/client/v3/profile/' + mxid + '/avatar_url');
    if (!resp.ok) return;                       // no profile -> keep initials
    const data = await resp.json();
    const mxc = data.avatar_url || '';
    if (!mxc.startsWith('mxc://')) return;
    const rest = mxc.slice(6);
    const slash = rest.indexOf('/');
    if (slash < 0) return;
    // /download (NOT /thumbnail): Synapse thumbnails are static frames, the
    // download URL preserves GIF / animated-WebP avatars — the dev-nest trick.
    const url = MATRIX_HS + '/_matrix/media/v3/download/' + rest.slice(0, slash) + '/' + rest.slice(slash + 1);
    for (const id of ['avatar-initial', 'avatar-initial-lg']) {
      const slot = document.getElementById(id);
      if (!slot) continue;
      const img = document.createElement('img');
      img.src = url;
      img.alt = '';
      img.className = 'avatar-img';
      img.onerror = function() { img.remove(); };  // fallback: initials stay
      img.onload = function() { slot.textContent = ''; slot.appendChild(img); };
    }
  } catch (e) { /* fallback: initials */ }
}

// ============================================================
// Auth & Permissions
// ============================================================
async function checkPermissions() {
  try {
    const resp = await fetch(apiUrl('api/auth/permissions'));
    const data = await resp.json();
    isIntMember = data.int_team_member === true;
    // Profile identity for the upper-right avatar (like dev-nest)
    const email = data.email || '';
    if (email) {
      const initial = email.charAt(0).toUpperCase();
      document.getElementById('avatar-initial').textContent = initial;
      document.getElementById('avatar-initial-lg').textContent = initial;
      document.getElementById('profile-email').textContent = email;
      if (data.avatar) { setAvatarImage(data.avatar); }
      else { loadMatrixAvatar(data.sub || ''); }
    }
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
<script>
// === Inlined Ghost Mode board logic (composed fragment, osint #45) ===
$ghostmode_js
</script>
</body>
</html>"""
