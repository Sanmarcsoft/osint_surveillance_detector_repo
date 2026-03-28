from unittest.mock import patch, MagicMock
from ghostmode.alert import send_ntfy, send_signal


def test_send_ntfy_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    with patch("ghostmode.alert.requests.post", return_value=mock_resp) as mock_post:
        result = send_ntfy("test message", server="http://localhost", topic="test")
    assert result.success is True
    assert result.channel == "ntfy"
    assert result.status_code == 200
    mock_post.assert_called_once()


def test_send_ntfy_failure():
    import requests as req
    with patch("ghostmode.alert.requests.post", side_effect=req.ConnectionError("refused")):
        result = send_ntfy("test", server="http://localhost", topic="test")
    assert result.success is False
    assert result.channel == "ntfy"
    assert "refused" in result.error


def test_send_ntfy_rejects_bad_url():
    result = send_ntfy("test", server="ftp://evil", topic="test")
    assert result.success is False
    assert "invalid" in result.error.lower()


def test_send_signal_rejects_bad_phone():
    result = send_signal("test", phone="not-a-phone", recipient="+14155551234")
    assert result.success is False
    assert "invalid" in result.error.lower()


def test_send_signal_success():
    with patch("ghostmode.alert.shutil.which", return_value="/usr/bin/signal-cli"):
        with patch("ghostmode.alert.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = send_signal("test", phone="+14155551234", recipient="+14155559999")
    assert result.success is True
    assert result.channel == "signal"
