# Tool Reference: ghostmode watch

## Overview

The `ghostmode watch` command tails the OpenCanary log file in real time, emitting structured JSON lines for each canary event. Use this to monitor live intrusion attempts or to stream events into downstream processors.

## CLI Syntax

```bash
ghostmode watch
ghostmode watch --log /path/to/opencanary.log
ghostmode watch --log /var/log/opencanary/opencanary.log
```

## MCP Tool

**Tool name**: `ghostmode_watch`

| Parameter | Type   | Default                              | Description                   |
|-----------|--------|--------------------------------------|-------------------------------|
| log       | string | value of `OPENCANARY_LOG` env var    | Path to the OpenCanary log file |

## Streaming Output Format

Each event is emitted as a single JSON line to stdout:

```json
{"ts": "2026-03-28T12:01:05+00:00", "src_host": "192.168.1.100", "src_port": 54321, "dst_port": 8081, "logtype": 2000, "logdata": {"msg": "HTTP GET /"}, "node_id": "opencanary-1"}
```

### Key Fields

| Field     | Type    | Description                                    |
|-----------|---------|------------------------------------------------|
| ts        | string  | ISO-8601 event timestamp                       |
| src_host  | string  | Attacker source IP address                     |
| src_port  | integer | Attacker source port                           |
| dst_port  | integer | Canary service port that was probed            |
| logtype   | integer | OpenCanary log type code (see table below)     |
| logdata   | object  | Service-specific event detail                  |
| node_id   | string  | OpenCanary node identifier                     |

### OpenCanary Log Types

| logtype | Service         |
|---------|-----------------|
| 2000    | HTTP            |
| 2001    | HTTP login attempt |
| 3000    | FTP login       |
| 5000    | SSH login attempt |
| 6000    | Telnet login    |

## Behavior

- Blocks indefinitely; use `Ctrl+C` to stop.
- If the log file does not exist at startup, watch exits with code 1 and an error message.
- New lines appended to the log file are picked up in near real time (polling interval: 0.5 s).

## Example

```bash
$ ghostmode watch --log /var/log/opencanary/opencanary.log
{"ts": "2026-03-28T12:01:05+00:00", "src_host": "10.0.1.5", ...}
{"ts": "2026-03-28T12:01:12+00:00", "src_host": "10.0.1.5", ...}
^C
```

## Notes

- Pipe the output to `jq` for filtering: `ghostmode watch | jq 'select(.dst_port == 22)'`
- For historical log queries use `ghostmode logs query` instead.
