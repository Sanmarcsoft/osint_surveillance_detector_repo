# Tool Reference: ghostmode logs query

## Overview

The `ghostmode logs query` command queries historical OpenCanary log events with flexible filters. Returns a JSON array of matching events, most recent first.

## CLI Syntax

```bash
ghostmode logs query
ghostmode logs query --since 1h
ghostmode logs query --since 24h --service ftp
ghostmode logs query --src-host 192.168.1.100
ghostmode logs query --since 1h --limit 50
```

## MCP Tool

**Tool name**: `ghostmode_logs_query`

| Parameter | Type   | Default | Description                                          |
|-----------|--------|---------|------------------------------------------------------|
| since     | string | 1h      | Time window: `15m`, `1h`, `6h`, `24h`, `7d`         |
| service   | string | all     | Filter by service: `http`, `ftp`, `ssh`, `telnet`, `all` |
| src_host  | string | none    | Filter by exact source IP address                    |
| limit     | integer | 100    | Maximum number of results to return (1-1000)         |

## JSON Output Schema

```json
{
  "ok": true,
  "query": {
    "since": "1h",
    "service": "all",
    "src_host": null,
    "limit": 100
  },
  "count": 3,
  "events": [
    {
      "ts": "2026-03-28T12:05:00+00:00",
      "src_host": "10.0.1.5",
      "src_port": 54321,
      "dst_port": 8081,
      "service": "http",
      "logtype": 2000,
      "logdata": {"METHOD": "GET", "PATH": "/admin"}
    }
  ]
}
```

### Event Fields

| Field    | Type    | Description                          |
|----------|---------|--------------------------------------|
| ts       | string  | ISO-8601 event timestamp             |
| src_host | string  | Source IP address                    |
| src_port | integer | Source port                          |
| dst_port | integer | Destination canary port              |
| service  | string  | Canary service name                  |
| logtype  | integer | OpenCanary numeric log type          |
| logdata  | object  | Service-specific event payload       |

## Exit Codes

| Code | Meaning                          |
|------|----------------------------------|
| 0    | Query successful (may return 0 results) |
| 1    | Query error (log file missing, parse error) |

## Examples

Query all events from the last hour:
```bash
$ ghostmode logs query --since 1h
```

Query FTP events from a specific attacker IP:
```bash
$ ghostmode logs query --service ftp --src-host 203.0.113.5
```

Get the 10 most recent events:
```bash
$ ghostmode logs query --limit 10
```

## Notes

- Time windows are relative to the current clock on the host running ghostmode.
- For real-time monitoring use `ghostmode watch` instead.
- The `--src-host` filter performs an exact string match; CIDR ranges are not supported.
- Combine with `jq` for aggregation: `ghostmode logs query --since 24h | jq '.events | group_by(.src_host) | map({ip: .[0].src_host, count: length})'`
