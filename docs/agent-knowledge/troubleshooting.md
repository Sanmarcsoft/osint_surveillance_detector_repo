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

## 6. Asset Monitor Fires False DOWN Pages (issue #55)

**Symptom**: Repeated p5 `<Asset>: DOWN` pages on `ghostmode-alerts` (and `universal-exports`) for a host that is actually serving traffic. The alert body reads `Probe code: 200 (expected healthy)` yet pages DOWN, and re-fires every ~30 min. Most common victim: SSO/Cognito-gated hosts (Dev NEST, Analytics, Webmail).

**Root cause class**: The uptime pager (`ghostmode/asset_monitor.py`) used to page DOWN whenever a host's live HTTP status fell outside a hard-coded expected-code set. SSO/Cognito gates change their redirect behaviour over time (302 ↔ 200 ↔ 301), so the expected code drifts out of date and every healthy probe is read as DOWN. This recurred three times before the durable fix.

**Current behaviour (durable, since commit `aa598df`)**: HTTP assets page DOWN **only on genuine unreachability** — no response, or a 5xx. Any live response below 500 (200, a gate's 301/302, an auth wall's 401/403) is treated as UP. A reachable host answering an unexpected-but-live code is a dashboard **warn** (`ops_dashboard.status_class`), not a page. Expected-code sets are now a dashboard concern only — they no longer trigger pages. RDS/SES assets keep matching their broad expected-state set (so `BACKING-UP`/`MAINTENANCE` never page).

**Where the pager runs**: a single instance — the ECS service `phenom-dev-nest-ops` (cluster `phenom-dev-cluster`) with env `RUN_ASSET_MONITOR=true` + `ALERT_MODE=ntfy`. The `crabkey` container runs the same code with `RUN_ASSET_MONITOR` unset, so it does NOT page (avoids the duplicate-pager zombie of June 2026).

**Diagnosis**:
```bash
# 1. Is the "DOWN" host actually serving? (the alert lies if this is < 500)
curl -s -o /dev/null -w '%{http_code}\n' https://<host>/

# 2. Which task-def / image is the pager running?
AWS_PROFILE=phenom aws ecs describe-services --cluster phenom-dev-cluster \
  --services phenom-dev-nest-ops --query 'services[0].taskDefinition' --output text

# 3. Confirm the running image carries the reachability fix
AWS_PROFILE=phenom aws ecs describe-task-definition --task-definition <taskdef> \
  --query 'taskDefinition.containerDefinitions[0].image' --output text
```

**Resolution** — never edit expected codes to chase a drift (that is the bug). Confirm the reachability-based pager is deployed. To rebuild + deploy the nest-ops pager image:
```bash
# build on the x86_64 build host (ai), push to ECR via skopeo (token over stdin),
# register a new task-def revision pointing at the new tag, roll the service:
#   docker buildx build --builder multiarch --platform linux/amd64 --load \
#     -f Dockerfile.nest -t nest-ops:<tag> .
#   aws ecr get-login-password | skopeo login --username AWS --password-stdin <ECR>
#   skopeo copy docker-daemon:nest-ops:<tag> docker://<ECR>/phenom-dev/nest-ops:<tag>
#   aws ecs register-task-definition --cli-input-json file://<td.json>   # image swapped
#   aws ecs update-service --cluster phenom-dev-cluster --service phenom-dev-nest-ops \
#     --task-definition phenom-dev-nest-ops:<rev>
#   aws ecs wait services-stable --cluster phenom-dev-cluster --services phenom-dev-nest-ops
```
Verify the running task's `imageDigest` equals the ECR digest you pushed, then confirm no new `<Asset>: DOWN` fires on `ghostmode-alerts` after the new task passes its warmup + debounce (~3 min).

---

## Quick Reference: Run All Diagnostics

```bash
ghostmode config validate && ghostmode status && ghostmode alert test
```

All three commands should return `ok: true`. If any fails, follow the relevant section above.
