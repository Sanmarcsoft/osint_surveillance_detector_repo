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


def test_check_opencanary_log_exists(tmp_path):
    log = tmp_path / "opencanary.log"
    log.write_text("line1\nline2\nline3\n")
    result = check_opencanary_log(str(log))
    assert result.status == "running"
    assert result.detail["log_lines"] == 3


def test_check_opencanary_log_missing():
    result = check_opencanary_log("/nonexistent/path.log")
    assert result.status == "log_missing"


def test_get_status_returns_envelope():
    with patch("ghostmode.status.check_ntfy") as m_ntfy, \
         patch("ghostmode.status.check_opencanary_log") as m_canary:
        from ghostmode.models import ServiceHealth
        m_ntfy.return_value = ServiceHealth(name="ntfy", status="reachable")
        m_canary.return_value = ServiceHealth(name="opencanary", status="running")
        result = get_status(ntfy_server="http://localhost", ntfy_topic="t", canary_log="/tmp/c.log")
    assert "services" in result
    assert "ntfy" in result["services"]
