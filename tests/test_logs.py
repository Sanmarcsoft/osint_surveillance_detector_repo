import json
import os
import tempfile
from ghostmode.logs import query_logs


def _write_log(lines: list[str]) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False)
    for line in lines:
        f.write(line + "\n")
    f.close()
    return f.name


def test_query_logs_returns_matching_events():
    path = _write_log([
        json.dumps({"local_time": "2026-03-28T10:00:00", "service": "http", "dst_port": 8081, "src_host": "1.2.3.4", "logdata": {}}),
        json.dumps({"local_time": "2026-03-28T11:00:00", "service": "ftp", "dst_port": 2121, "src_host": "5.6.7.8", "logdata": {}}),
    ])
    results = query_logs(path, service="http")
    os.unlink(path)
    assert len(results) == 1
    assert results[0]["service"] == "http"


def test_query_logs_filters_by_src_host():
    path = _write_log([
        json.dumps({"local_time": "2026-03-28T10:00:00", "service": "http", "dst_port": 8081, "src_host": "1.2.3.4", "logdata": {}}),
        json.dumps({"local_time": "2026-03-28T11:00:00", "service": "http", "dst_port": 8081, "src_host": "9.9.9.9", "logdata": {}}),
    ])
    results = query_logs(path, src_host="1.2.3.4")
    os.unlink(path)
    assert len(results) == 1


def test_query_logs_respects_limit():
    path = _write_log([
        json.dumps({"local_time": f"2026-03-28T{i:02d}:00:00", "service": "http", "dst_port": 8081, "src_host": "1.2.3.4", "logdata": {}})
        for i in range(10)
    ])
    results = query_logs(path, limit=3)
    os.unlink(path)
    assert len(results) == 3


def test_query_logs_handles_empty_file():
    path = _write_log([])
    results = query_logs(path)
    os.unlink(path)
    assert results == []


def test_query_logs_skips_bad_json():
    path = _write_log(["not json", '{"service": "http", "dst_port": 8081, "src_host": "1.1.1.1", "logdata": {}}'])
    results = query_logs(path)
    os.unlink(path)
    assert len(results) == 1
