import os
import json
import tempfile
from ghostmode.config import validate_config, load_config


def test_validate_config_all_set(monkeypatch):
    monkeypatch.setenv("NTFY_SERVER", "http://localhost")
    monkeypatch.setenv("NTFY_TOPIC", "test")
    monkeypatch.setenv("TS_AUTHKEY", "tskey-auth-xxx")
    monkeypatch.setenv("ALERT_MODE", "ntfy")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
        json.dump({"http.enabled": True, "http.port": 8081}, f)
        f.flush()
        result = validate_config(canary_conf_path=f.name)
    os.unlink(f.name)
    assert result["ok"] is True
    assert len(result["issues"]) == 0


def test_validate_config_missing_ntfy(monkeypatch):
    monkeypatch.delenv("NTFY_SERVER", raising=False)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    result = validate_config()
    assert result["ok"] is False
    codes = [i["key"] for i in result["issues"]]
    assert "NTFY_SERVER" in codes


def test_validate_config_bad_canary_json():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
        f.write("not json{{{")
        f.flush()
        result = validate_config(canary_conf_path=f.name)
    os.unlink(f.name)
    assert result["ok"] is False
    codes = [i["key"] for i in result["issues"]]
    assert "opencanary.conf" in codes


def test_load_config_returns_dict(monkeypatch):
    monkeypatch.setenv("NTFY_SERVER", "http://localhost")
    monkeypatch.setenv("NTFY_TOPIC", "test")
    monkeypatch.setenv("ALERT_MODE", "print")
    cfg = load_config()
    assert cfg["ntfy_server"] == "http://localhost"
    assert cfg["alert_mode"] == "print"
