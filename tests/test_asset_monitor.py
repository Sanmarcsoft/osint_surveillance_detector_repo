"""Tests for the asset-down → ntfy monitor (transition logic + down-definition)."""
import ghostmode.asset_monitor as am


def setup_function(_):
    am._state.clear()


def test_down_definition_per_asset():
    # /healthz-style: only 200 is healthy
    assert am._is_healthy({"code": 200}, {200}) is True
    assert am._is_healthy({"code": 500}, {200}) is False
    # a dead host probes to code None — must read as DOWN (the bug we fixed:
    # the board's code<500 check treated None… here None is not in the set)
    assert am._is_healthy({"code": None}, {200}) is False
    # token-gated / access-gated routes: 401 is the healthy state
    assert am._is_healthy({"code": 401}, {401}) is True
    assert am._is_healthy({"code": 200}, {401}) is False
    # AWS control-plane statuses
    assert am._is_healthy({"code": "AVAILABLE"}, {"AVAILABLE"}) is True
    assert am._is_healthy({"code": "STOPPED"}, {"AVAILABLE"}) is False
    # self row is always up
    assert am._is_healthy({"is_self": True}, None) is True


def test_debounce_then_down_then_recovery(monkeypatch):
    sent = []
    monkeypatch.setattr(am, "_publish",
                        lambda topic, title, body, priority, tags, click_url=None: sent.append((topic, title)) or True)
    down = {"label": "X", "host": "x.test", "code": None}
    up = {"label": "X", "host": "x.test", "code": 200}

    # one transient failure must NOT page (debounce)
    assert am.evaluate_transition("X", "phenom-x", False, down, now=1000) is None
    assert sent == []
    # second consecutive failure pages — asset topic + BOTH mirrors
    # (ghostmode-alerts = Phenom client view, universal-exports = operator
    # all-assets view; multi-tenant routing, M directive 2026-06-08)
    assert am.evaluate_transition("X", "phenom-x", False, down, now=1060) == "down"
    assert ("phenom-x", "X: DOWN") in sent and ("ghostmode-alerts", "X: DOWN") in sent
    assert ("universal-exports", "X: DOWN") in sent
    assert len(sent) == 3
    # title must BEGIN with the asset name (admin scans the mirror topic)
    assert all(title.startswith("X") for _topic, title in sent)
    # still down inside the cooldown: no repeat page
    assert am.evaluate_transition("X", "phenom-x", False, down, now=1120) is None
    assert len(sent) == 3
    # recovery pages once, to all three topics
    assert am.evaluate_transition("X", "phenom-x", True, up, now=1180) == "recovered"
    assert ("phenom-x", "X: RECOVERED") in sent and ("ghostmode-alerts", "X: RECOVERED") in sent
    assert ("universal-exports", "X: RECOVERED") in sent
    assert len(sent) == 6


def test_realert_only_after_cooldown(monkeypatch):
    sent = []
    monkeypatch.setattr(am, "_publish", lambda *a, **k: sent.append(a) or True)
    down = {"label": "Y", "host": "y.test", "code": 500}
    am.evaluate_transition("Y", "phenom-y", False, down, now=0)      # streak 1: debounced
    am.evaluate_transition("Y", "phenom-y", False, down, now=60)     # streak 2: page (asset topic + 2 mirrors)
    assert len(sent) == 3
    am.evaluate_transition("Y", "phenom-y", False, down, now=120)    # within cooldown: no
    assert len(sent) == 3
    am.evaluate_transition("Y", "phenom-y", False, down, now=60 + am._REALERT_SECONDS)  # re-page
    assert len(sent) == 6


def test_recovery_without_prior_alert_is_silent(monkeypatch):
    sent = []
    monkeypatch.setattr(am, "_publish", lambda *a, **k: sent.append(a) or True)
    up = {"label": "Z", "host": "z.test", "code": 200}
    # a single healthy probe (never alerted) emits nothing
    assert am.evaluate_transition("Z", "phenom-z", True, up, now=0) is None
    assert sent == []


def test_topics_cover_all_board_assets():
    # every monitored topic is a phenom-* topic; 15 assets mapped
    assert len(am.ASSET_MONITOR) == 15
    for topic, _expected, url in am.ASSET_MONITOR.values():
        assert topic.startswith("phenom-")
        assert url.startswith("https://")


def test_click_url_threads_to_publish(monkeypatch):
    captured = {}
    monkeypatch.setattr(am, "_publish",
                        lambda topic, title, body, priority, tags, click_url=None: captured.setdefault(topic, click_url) or True)
    down = {"label": "W", "host": "w.test", "code": None}
    am.evaluate_transition("W", "phenom-w", False, down, now=0)
    am.evaluate_transition("W", "phenom-w", False, down, now=60, click_url="https://www.thephenom.app")
    assert captured["phenom-w"] == "https://www.thephenom.app"
    assert captured["ghostmode-alerts"] == "https://www.thephenom.app"


def test_rds_benign_states_not_down():
    db = am.ASSET_MONITOR["DB · dev (RDS Postgres)"][1]
    for ok in ("AVAILABLE", "BACKING-UP", "MAINTENANCE", "MODIFYING",
               "STORAGE-OPTIMIZATION", "UPGRADING", "CONFIGURING-ENHANCED-MONITORING"):
        assert am._is_healthy({"code": ok}, db) is True, ok
    for bad in ("STOPPED", "FAILED", "STORAGE-FULL", "DELETING"):
        assert am._is_healthy({"code": bad}, db) is False, bad


def test_title_ascii_sanitized(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200
        text = "ok"

    monkeypatch.setattr(am.requests, "post",
                        lambda url, data=None, headers=None, auth=None, timeout=None:
                        captured.update(headers) or FakeResp())
    monkeypatch.setattr(am, "load_config",
                        lambda: {"ntfy_server": "https://x", "ntfy_user": "u", "ntfy_pass": "p"})
    am._publish("phenom-db-dev", "DB · dev (RDS Postgres): DOWN", "b", 5, "rotating_light",
                click_url="https://console.aws")
    assert "·" not in captured["Title"] and captured["Title"].startswith("DB - dev")
    assert captured["Click"] == "https://console.aws"


class _FakeThread:
    """Records whether the daemon thread was actually started."""
    def __init__(self, *args, **kwargs):
        self.name = kwargs.get("name")

    def start(self):
        _FakeThread.started.append(self.name)


def test_start_gated_off_when_flag_unset(monkeypatch):
    # asset-monitor must NOT start unless RUN_ASSET_MONITOR is truthy. crabkey
    # (outside the AWS VPC) would false-page RDS/SES and double-page HTTP assets;
    # only the designated pager (ECS nest-ops) sets the flag true.
    monkeypatch.delenv("RUN_ASSET_MONITOR", raising=False)
    _FakeThread.started = []
    monkeypatch.setattr(am.threading, "Thread", _FakeThread)
    am.start_asset_monitor()
    assert _FakeThread.started == []


def test_start_gated_off_when_flag_falsey(monkeypatch):
    monkeypatch.setenv("RUN_ASSET_MONITOR", "false")
    _FakeThread.started = []
    monkeypatch.setattr(am.threading, "Thread", _FakeThread)
    am.start_asset_monitor()
    assert _FakeThread.started == []


def test_start_runs_when_flag_true(monkeypatch):
    monkeypatch.setenv("RUN_ASSET_MONITOR", "true")
    _FakeThread.started = []
    monkeypatch.setattr(am.threading, "Thread", _FakeThread)
    am.start_asset_monitor()
    assert _FakeThread.started == ["asset-monitor"]
