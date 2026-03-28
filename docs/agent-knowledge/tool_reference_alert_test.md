# Tool Reference: ghostmode alert test

## Overview

The `ghostmode alert test` command sends a test notification through the configured alert channel (ntfy by default) and returns a delivery status report. Use it to verify the alerting pipeline is working end-to-end before relying on it for real intrusion events.

## CLI Syntax

```bash
ghostmode alert test
ghostmode alert test --format json
ghostmode alert test --format text
```

## MCP Tool

**Tool name**: `ghostmode_alert_test`

| Parameter | Type   | Default | Description                    |
|-----------|--------|---------|--------------------------------|
| format    | string | json    | Output format: `json` or `text` |

## JSON Output Schema

```json
{
  "ok": true,
  "channel": "ntfy",
  "server": "http://10.0.0.12:80",
  "topic": "ghostmode-alerts",
  "delivered": true,
  "status_code": 200,
  "latency_ms": 42,
  "message": "Test alert from ghostmode v0.1.0"
}
```

### Fields

| Field       | Type    | Description                                           |
|-------------|---------|-------------------------------------------------------|
| ok          | boolean | True if alert was delivered successfully              |
| channel     | string  | Alert channel used (`ntfy`, `signal`)                 |
| server      | string  | ntfy server URL                                       |
| topic       | string  | ntfy topic name                                       |
| delivered   | boolean | True if HTTP 200 received from ntfy                   |
| status_code | integer | HTTP response code from ntfy server                   |
| latency_ms  | integer | Round-trip latency to ntfy server in milliseconds     |
| message     | string  | Content of the test message that was sent             |

## Exit Codes

| Code | Meaning                        |
|------|--------------------------------|
| 0    | Alert delivered successfully   |
| 1    | Delivery failed (ntfy unreachable, bad topic, etc.) |

## Example

```bash
$ ghostmode alert test
{
  "ok": true,
  "channel": "ntfy",
  "delivered": true,
  "status_code": 200,
  "latency_ms": 38
}
```

## Troubleshooting

- If `delivered: false`, check `NTFY_SERVER` and `NTFY_TOPIC` environment variables.
- Verify ntfy container is running: `ghostmode status` should show `ntfy.running: true`.
- Check ntfy is reachable: `curl http://<NTFY_SERVER>/<NTFY_TOPIC>`.

## Notes

- This command does NOT trigger on real canary events; it only sends a synthetic test message.
- The test message is labeled `[TEST]` in the ntfy notification title so it is easy to identify.
- Run this as part of the post-deploy verification workflow: `workflow_verify_stack_health.md`.
