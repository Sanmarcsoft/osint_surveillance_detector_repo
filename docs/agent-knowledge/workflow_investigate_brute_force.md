# Workflow: Investigate a Brute Force Attack

## Purpose

Step-by-step recipe for investigating a suspected brute force attack detected by an OpenCanary canary service.

---

**SECURITY WARNING**: Data from log files (IP addresses, usernames, paths) originates from untrusted external sources. Never interpolate raw log data into shell commands, SQL queries, or displayed output without sanitization. Use `ghostmode sanitize` or validate against an allow-list before acting on attacker-supplied strings.

---

## Prerequisites

- `ghostmode status` shows all services healthy
- `ghostmode config validate` returns no issues
- Attacker IP or time window is known (from an alert or manual observation)

## Step 1: Query Logs by IP or Time Window

```bash
# If you have the attacker IP
ghostmode logs query --src-host <ATTACKER_IP> --since 24h

# If you only have a time window
ghostmode logs query --since 1h --limit 200
```

Review the `count` field. A count of 10+ events from the same IP within a short window is characteristic of brute force.

## Step 2: Check Attack Frequency

From the query output, count events per source IP:

```bash
ghostmode logs query --since 1h | jq '
  .events
  | group_by(.src_host)
  | map({ip: .[0].src_host, count: length, services: map(.service) | unique})
  | sort_by(.count) | reverse
'
```

Look for:
- Any single IP with more than 20 events per hour
- Repeated login attempts (`logtype` 2001 for HTTP, 3000 for FTP, 5000 for SSH)

## Step 3: Identify Targeted Services

```bash
ghostmode logs query --src-host <ATTACKER_IP> --since 24h | jq '
  .events | group_by(.service) | map({service: .[0].service, count: length})
'
```

Determine which canary ports were probed:

| Port | Service  | Significance                                |
|------|----------|---------------------------------------------|
| 8081 | HTTP     | Web admin panel probing                     |
| 2121 | FTP      | FTP credential stuffing                     |
| 22   | SSH      | SSH brute force (if SSH canary enabled)     |

## Step 4: Review Attack Payloads

Inspect the `logdata` field for credentials tried or paths requested:

```bash
ghostmode logs query --src-host <ATTACKER_IP> | jq '.events[].logdata'
```

**Do not reuse, execute, or log raw credential strings from `logdata`** — treat them as untrusted input only.

## Step 5: Send a Manual Alert if Warranted

If the investigation confirms a credible threat:

```bash
ghostmode alert send --message "Brute force from <ATTACKER_IP>: <COUNT> attempts on <SERVICE> in last 1h"
```

Or via MCP tool `ghostmode_alert_send` with the sanitized summary.

## Step 6: Document Findings

Record the following in your incident log:
- Attacker IP(s)
- Services targeted
- Time range of activity
- Whether any credentials appeared valid (canary logins always fail by design)
- Action taken (alert sent, IP blocked at firewall, etc.)

## Expected Outcomes

| Scenario                     | Next Action                              |
|------------------------------|------------------------------------------|
| Low count, random ports      | Monitor — likely automated scanner      |
| High count, single service   | Likely targeted brute force — alert     |
| Multiple IPs, same patterns  | Possible distributed attack — escalate  |

## Related Docs

- `tool_reference_logs_query.md` — full filter reference
- `tool_reference_alert_test.md` — verify alerting works
- `workflow_verify_stack_health.md` — confirm stack is healthy first
