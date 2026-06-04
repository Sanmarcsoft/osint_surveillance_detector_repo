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
                        lambda topic, title, body, priority, tags: sent.append((topic, title)) or True)
    down = {"label": "X", "host": "x.test", "code": None}
    up = {"label": "X", "host": "x.test", "code": 200}

    # one transient failure must NOT page (debounce)
    assert am.evaluate_transition("X", "phenom-x", False, down, now=1000) is None
    assert sent == []
    # second consecutive failure pages exactly once
    assert am.evaluate_transition("X", "phenom-x", False, down, now=1060) == "down"
    assert len(sent) == 1 and sent[0] == ("phenom-x", "DOWN: X")
    # still down inside the cooldown: no repeat page
    assert am.evaluate_transition("X", "phenom-x", False, down, now=1120) is None
    assert len(sent) == 1
    # recovery pages once
    assert am.evaluate_transition("X", "phenom-x", True, up, now=1180) == "recovered"
    assert len(sent) == 2 and sent[1] == ("phenom-x", "RECOVERED: X")


def test_realert_only_after_cooldown(monkeypatch):
    sent = []
    monkeypatch.setattr(am, "_publish", lambda *a, **k: sent.append(a) or True)
    down = {"label": "Y", "host": "y.test", "code": 500}
    am.evaluate_transition("Y", "phenom-y", False, down, now=0)      # streak 1: debounced
    am.evaluate_transition("Y", "phenom-y", False, down, now=60)     # streak 2: page
    assert len(sent) == 1
    am.evaluate_transition("Y", "phenom-y", False, down, now=120)    # within cooldown: no
    assert len(sent) == 1
    am.evaluate_transition("Y", "phenom-y", False, down, now=60 + am._REALERT_SECONDS)  # re-page
    assert len(sent) == 2


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
    for topic, _expected in am.ASSET_MONITOR.values():
        assert topic.startswith("phenom-")
