# Tool Reference: ghostmode status

## Overview

The `ghostmode status` command checks the health of all Ghost Mode stack services and returns a structured JSON report.

## CLI Syntax

```bash
ghostmode status
ghostmode status --format json
ghostmode status --format text
```

## MCP Tool

**Tool name**: `ghostmode_status`

No required parameters. Optional:

| Parameter | Type   | Default | Description                    |
|-----------|--------|---------|--------------------------------|
| format    | string | json    | Output format: `json` or `text` |

## JSON Output Schema

```json
{
  "ok": true,
  "timestamp": "2026-03-28T12:00:00+00:00",
  "services": {
    "opencanary": {
      "running": true,
      "port": 8081,
      "log_exists": true
    },
    "ntfy": {
      "running": true,
      "port": 80,
      "reachable": true
    },
    "spiderfoot": {
      "running": true,
      "port": 5001
    },
    "tailscale": {
      "running": true,
      "connected": true,
      "ip": "100.x.x.x"
    },
    "mcp": {
      "running": true,
      "port": 3200
    }
  },
  "issues": []
}
```

## Exit Codes

| Code | Meaning                          |
|------|----------------------------------|
| 0    | All services healthy             |
| 1    | One or more services degraded    |
| 2    | Fatal error (config missing, etc.) |

## Example

```bash
$ ghostmode status
{
  "ok": true,
  "timestamp": "2026-03-28T12:00:00+00:00",
  "services": { ... },
  "issues": []
}
```

## Notes

- Run after stack deployment to verify all containers are up.
- Combine with `ghostmode config validate` for a full pre-flight check.
- The `issues` array contains human-readable strings describing any problem found.
