# Workflow: Verify Stack Health (Post-Deploy)

## Purpose

A quick post-deployment verification recipe to confirm that the Ghost Mode stack is fully operational before relying on it for real-time intrusion detection.

## When to Run

- After initial deployment
- After `docker-compose up -d` or container restarts
- After any configuration change (env vars, opencanary.conf)
- As a periodic health check (e.g., cron every 5 minutes)

## Prerequisites

- Docker Compose stack is running
- Environment variables are set in `.env`

## Step 1: Check Service Status

```bash
ghostmode status
```

Expected output: `"ok": true` with all services showing `"running": true`.

If any service is not running, restart it:
```bash
docker-compose restart <service-name>
```

Wait 5 seconds and re-run `ghostmode status`.

## Step 2: Validate Configuration

```bash
ghostmode config validate
```

Expected output: `"ok": true` with `"issues": []`.

If issues are found, fix the reported env var or config file before proceeding.

## Step 3: Test the Alert Pipeline

```bash
ghostmode alert test
```

Expected output: `"delivered": true` with `"status_code": 200`.

Check the ntfy notification arrived on your subscribed device/client.

If delivery fails:
- Check `NTFY_SERVER` and `NTFY_TOPIC` are correct.
- Verify the ntfy container is running: `ghostmode status | jq '.services.ntfy'`
- Check ntfy is reachable: `curl http://<NTFY_SERVER>/<NTFY_TOPIC>/json`

## Step 4: Watch for Live Events (30 seconds)

```bash
timeout 30 ghostmode watch || true
```

If no events appear in 30 seconds, that is expected in a quiet environment.
To generate a test event, probe a canary port from another host:
```bash
curl http://<CANARY_HOST>:8081/
```

The watch stream should emit a JSON event line immediately.

## Step 5: Confirm Log File is Being Written

```bash
ghostmode logs query --since 5m --limit 5
```

If this returns events corresponding to the test probe in Step 4, the full pipeline (canary event -> log file -> ghostmode) is confirmed working.

## Checklist Summary

```
[ ] ghostmode status -> ok: true, all services running
[ ] ghostmode config validate -> ok: true, issues: []
[ ] ghostmode alert test -> delivered: true
[ ] ghostmode watch shows events when canary port is probed
[ ] ghostmode logs query returns recent events
```

## Expected Total Time

Under 2 minutes for a healthy stack.

## Related Docs

- `tool_reference_status.md` — status output schema
- `tool_reference_alert_test.md` — alert test details
- `tool_reference_config_validate.md` — what is validated
- `troubleshooting.md` — error resolution guide
