from unittest.mock import patch, MagicMock
from ghostmode.status import get_status, check_ntfy, check_opencanary_log


def test_check_ntfy_reachable():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("ghostmode.status.requests.get", return_value=mock_resp):
        result = check_ntfy("http://localhost", "test")
    assert result.status == "reachable"


def test_check_ntfy_unreachable():
    import requests
    with patch("ghostmode.status.requests.get", side_effect=requests.ConnectionError):
        result = check_ntfy("http://localhost", "test")
    assert result.status == "unreachable"


def test_check_opencanary_log_exists(tmp_path, monkeypatch):
    log = tmp_path / "opencanary.log"
    log.write_text("line1\nline2\nline3\n")
    monkeypatch.setenv("OPENCANARY_LOG", str(log))
    result = check_opencanary_log(str(log))
    assert result.status == "running"
    assert result.detail["log_lines"] == 3
    assert result.detail["last_activity_age_s"] >= 0


def test_check_opencanary_log_missing(monkeypatch):
    monkeypatch.setenv("OPENCANARY_LOG", "/nonexistent/path.log")
    result = check_opencanary_log("/nonexistent/path.log")
    assert result.status == "log_missing"


def test_check_opencanary_log_not_configured(monkeypatch):
    # No OPENCANARY_LOG in the environment (e.g. ECS nest-ops): the check is
    # informational, never a false alarm (osint #58).
    monkeypatch.delenv("OPENCANARY_LOG", raising=False)
    result = check_opencanary_log("/var/log/opencanary/opencanary.log")
    assert result.status == "not_configured"


def test_check_opencanary_log_stale(tmp_path, monkeypatch):
    # A file untouched longer than CANARY_LOG_MAX_AGE_H means no sensor
    # (local or remote-ingest) has produced an event — flag it.
    import os
    log = tmp_path / "opencanary.log"
    log.write_text("old event\n")
    two_days_ago = __import__("time").time() - 72 * 3600
    os.utime(log, (two_days_ago, two_days_ago))
    monkeypatch.setenv("OPENCANARY_LOG", str(log))
    monkeypatch.setenv("CANARY_LOG_MAX_AGE_H", "48")
    result = check_opencanary_log(str(log))
    assert result.status == "stale"
    assert result.detail["last_activity_age_s"] > 48 * 3600


def test_check_opencanary_log_fresh_within_threshold(tmp_path, monkeypatch):
    log = tmp_path / "opencanary.log"
    log.write_text("recent event\n")
    monkeypatch.setenv("OPENCANARY_LOG", str(log))
    monkeypatch.setenv("CANARY_LOG_MAX_AGE_H", "48")
    result = check_opencanary_log(str(log))
    assert result.status == "running"


def test_get_status_returns_envelope():
    with patch("ghostmode.status.check_ntfy") as m_ntfy, \
         patch("ghostmode.status.check_opencanary_log") as m_canary:
        from ghostmode.models import ServiceHealth
        m_ntfy.return_value = ServiceHealth(name="ntfy", status="reachable")
        m_canary.return_value = ServiceHealth(name="opencanary", status="running")
        result = get_status(ntfy_server="http://localhost", ntfy_topic="t", canary_log="/tmp/c.log")
    assert "services" in result
    assert "ntfy" in result["services"]
