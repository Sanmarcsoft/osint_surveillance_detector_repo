# Tool Reference: ghostmode config validate

## Overview

The `ghostmode config validate` command checks that all required environment variables are set and that the `opencanary.conf` file exists and is valid JSON. Returns a list of issues found; an empty `issues` list means the configuration is clean.

## CLI Syntax

```bash
ghostmode config validate
ghostmode config validate --format json
ghostmode config validate --format text
```

## MCP Tool

**Tool name**: `ghostmode_config_validate`

| Parameter | Type   | Default | Description                    |
|-----------|--------|---------|--------------------------------|
| format    | string | json    | Output format: `json` or `text` |

## JSON Output Schema

```json
{
  "ok": true,
  "issues": [],
  "checks": {
    "env_vars": {
      "ok": true,
      "missing": [],
      "invalid": []
    },
    "opencanary_conf": {
      "ok": true,
      "path": "/etc/opencanary/opencanary.conf",
      "valid_json": true
    }
  }
}
```

### Issue Object

Each entry in the `issues` array is a string describing the problem:

```json
{
  "ok": false,
  "issues": [
    "Missing required env var: NTFY_SERVER",
    "opencanary.conf not found at /etc/opencanary/opencanary.conf"
  ]
}
```

## Checks Performed

| Check                  | Description                                              |
|------------------------|----------------------------------------------------------|
| NTFY_SERVER set        | Required env var present and non-empty                   |
| NTFY_TOPIC set         | Required env var present and non-empty                   |
| OPENCANARY_LOG set     | Required env var present and non-empty                   |
| OPENCANARY_LOG exists  | File at the configured path actually exists              |
| opencanary.conf exists | Config file present                                      |
| opencanary.conf valid  | Config file is parseable as JSON                         |
| MCP_PORT numeric       | If set, MCP_PORT is a valid port number (1-65535)        |
| CHROMADB_PORT numeric  | If set, CHROMADB_PORT is a valid port number             |

## Exit Codes

| Code | Meaning                         |
|------|---------------------------------|
| 0    | Configuration is valid          |
| 1    | One or more issues found        |

## Example: Clean Configuration

```bash
$ ghostmode config validate
{
  "ok": true,
  "issues": [],
  "checks": { ... }
}
```

## Example: Issues Found

```bash
$ ghostmode config validate
{
  "ok": false,
  "issues": [
    "Missing required env var: NTFY_TOPIC",
    "OPENCANARY_LOG path does not exist: /var/log/opencanary/opencanary.log"
  ]
}
```

## Notes

- Run this command before `ghostmode watch` or any monitoring workflow.
- Integrate into CI/CD to catch missing secrets early.
- Does not validate that services are actually reachable; use `ghostmode status` for that.
