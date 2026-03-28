import json
from click.testing import CliRunner
from ghostmode.cli import cli


def test_cli_status_returns_json(monkeypatch):
    monkeypatch.setenv("NTFY_SERVER", "http://localhost")
    monkeypatch.setenv("NTFY_TOPIC", "test")
    from unittest.mock import patch
    from ghostmode.models import ServiceHealth
    with patch("ghostmode.cli.get_status", return_value={
        "services": {"ntfy": ServiceHealth("ntfy", "reachable").to_dict()},
        "uptime_seconds": 100,
    }):
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True
    assert data["command"] == "status"


def test_cli_config_validate_json(monkeypatch):
    monkeypatch.setenv("NTFY_SERVER", "http://localhost")
    monkeypatch.setenv("NTFY_TOPIC", "test")
    runner = CliRunner()
    result = runner.invoke(cli, ["config", "validate"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "ok" in data


def test_cli_alert_test_json(monkeypatch):
    monkeypatch.setenv("NTFY_SERVER", "http://localhost")
    monkeypatch.setenv("NTFY_TOPIC", "test")
    from unittest.mock import patch
    from ghostmode.models import AlertResult
    with patch("ghostmode.cli.send_ntfy", return_value=AlertResult("ntfy", True, 200)):
        runner = CliRunner()
        result = runner.invoke(cli, ["alert", "test"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True


def test_cli_format_text(monkeypatch):
    monkeypatch.setenv("NTFY_SERVER", "http://localhost")
    monkeypatch.setenv("NTFY_TOPIC", "test")
    from unittest.mock import patch
    from ghostmode.models import ServiceHealth
    with patch("ghostmode.cli.get_status", return_value={
        "services": {"ntfy": ServiceHealth("ntfy", "reachable").to_dict()},
        "uptime_seconds": 100,
    }):
        runner = CliRunner()
        result = runner.invoke(cli, ["--format", "text", "status"])
    assert result.exit_code == 0
    try:
        json.loads(result.output)
        assert False, "text format should not be JSON"
    except json.JSONDecodeError:
        pass
