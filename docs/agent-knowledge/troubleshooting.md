# Troubleshooting: Common Ghost Mode Errors

## 1. ntfy Unreachable

**Symptom**: `ghostmode alert test` returns `"delivered": false` or exits with code 1.

**Error messages**:
- `Connection refused`
- `Failed to connect to <NTFY_SERVER>`
- `status_code: 503`

**Diagnosis**:
```bash
# Check ntfy container is running
ghostmode status | jq '.services.ntfy'

# Test direct HTTP connectivity
curl -v http://<NTFY_SERVER>/<NTFY_TOPIC>
```

**Resolution**:
1. If ntfy container is not running: `docker-compose restart ntfy`
2. If `NTFY_SERVER` is wrong, correct it in `.env` and re-export.
3. If behind a firewall, verify the ntfy port (default 80) is open on the host.
4. Check ntfy container logs: `docker-compose logs ntfy`

---

## 2. OpenCanary Log File Missing

**Symptom**: `ghostmode watch` exits immediately with an error, or `ghostmode logs query` returns 0 events even after probing the canary.

**Error messages**:
- `Log file not found: /var/log/opencanary/opencanary.log`
- `OPENCANARY_LOG does not exist`

**Diagnosis**:
```bash
ghostmode config validate
ls -la $OPENCANARY_LOG
docker-compose logs opencanary
```

**Resolution**:
1. If OpenCanary is not running: `docker-compose restart opencanary`
2. If the log path is wrong, correct `OPENCANARY_LOG` in `.env`.
3. If the volume mount is missing, check `docker-compose.yml` to ensure the log directory is mounted into the ghostmode container.
4. OpenCanary only creates the log on first event — probe a canary port to trigger the first write: `curl http://<CANARY_HOST>:8081/`

---

## 3. Alerts Not Delivered

**Symptom**: OpenCanary is logging events, watch shows events, but no ntfy notification arrives on your device.

**Diagnosis**:
```bash
# Confirm the topic matches on sender and receiver
echo $NTFY_TOPIC

# Check the alert mode
echo $ALERT_MODE

# Manually send a test
ghostmode alert test
```

**Resolution**:
1. Verify your ntfy client is subscribed to the exact same topic as `NTFY_TOPIC`.
2. Check `ALERT_MODE` — if set to `signal`, ntfy is bypassed.
3. Check ntfy server logs for delivery errors: `docker-compose logs ntfy`
4. If using Signal (`ALERT_MODE=signal`), verify Signal CLI container is running and registered.
5. Check device notification settings — ntfy notifications may be muted.

---

## 4. MCP Server Not Responding

**Symptom**: AI agent tool calls to `ghostmode_*` tools fail with connection errors. Claude Code reports the MCP server is unavailable.

**Error messages**:
- `Connection refused on port 3200`
- `MCP tool ghostmode_status not found`

**Diagnosis**:
```bash
ghostmode status | jq '.services.mcp'
curl http://localhost:3200/health
docker-compose logs ghostmode-mcp
```

**Resolution**:
1. Restart the MCP container: `docker-compose restart ghostmode-mcp`
2. Verify `MCP_PORT` env var matches the port in `docker-compose.yml`.
3. Check for port conflicts: `ss -tlnp | grep 3200`
4. Review MCP server startup logs for Python import errors.

---

## 5. ghostmode watch Shows No Events

**Symptom**: `ghostmode watch` runs but no JSON lines appear even when you expect canary activity.

**Diagnosis**:
```bash
# Verify the log file is growing
stat $OPENCANARY_LOG
tail -f $OPENCANARY_LOG

# Generate a test event
curl http://<CANARY_HOST>:8081/

# Check OpenCanary is listening
ghostmode status | jq '.services.opencanary'
```

**Resolution**:
1. Confirm OpenCanary is running and the canary port is accessible.
2. Verify the `OPENCANARY_LOG` path in `.env` matches where OpenCanary is writing.
3. Check file permissions — ghostmode must have read access to the log file.
4. If OpenCanary is running but not writing: check `opencanary.conf` for the correct `"log": {"file": {...}}` setting.
5. Ensure probes are reaching the canary host and not being blocked by a local firewall.

---

## Quick Reference: Run All Diagnostics

```bash
ghostmode config validate && ghostmode status && ghostmode alert test
```

All three commands should return `ok: true`. If any fails, follow the relevant section above.
