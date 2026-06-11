# thephenom.app external honeypot sensor (AWS Lightsail)

Source of truth for the **phenom-aws-honeypot** OpenCanary sensor — the
internet-exposed honeypot on Phenom's own AWS, monitoring thephenom.app's
external attack surface and reporting to crabkey + the nest-ops ops board.

> This directory is the canonical copy. The instance is provisioned by hand
> today; if it is rebuilt, re-apply these files. (Pulumi/cloud-init backfill
> is tracked — see osint #54 / #58.)

## Instance

| | |
|---|---|
| Name | `phenom-honeypot` (account 657033058608, us-east-1a, `micro_3_0`) |
| Static IP | **3.230.47.213** (`phenom-honeypot-ip`) |
| SSH | user `ubuntu`, key `pass sanmarcsoft/aws/phenom-honeypot-ssh-key` |
| Firewall | 21/22/23/80/3306/6379 open |

## Files

| Repo file | Deploys to | Purpose |
|-----------|-----------|---------|
| `opencanary.conf` | `/etc/opencanaryd/opencanary.conf` | Honeypot services (ftp/http/telnet/mysql/redis; **not** ssh — 22 is admin) |
| `opencanary.service` | `/etc/systemd/system/opencanary.service` | Runs `opencanaryd` |
| `canary-push.sh` | `/opt/canary-push.sh` (chmod 755) | Tails the log, dual-pushes each event |
| `canary-push.service` | `/etc/systemd/system/canary-push.service` | Runs the pusher |

**Secret (not in git):** `/etc/canary-push.env` (chmod 600) holds
`TOKEN=<ingest bearer>`. Same value as `pass sanmarcsoft/ghostmode/ingest-token`,
the nest-ops Secrets Manager key `ghostmode_ingest_token`, and crabkey.

## Gotchas (hard-won 2026-06-08 / 2026-06-11)

- **Egress IP family.** The crabkey push MUST use `curl -4`: the CF allow rule
  for 3.230.47.213 is IPv4-only, and this dual-stack host egresses IPv6 first,
  drawing a managed challenge. (osint canary-ingest setup, 2026-06-08.)
- **nest-ops leg bypasses Cloudflare** via `--connect-to <ALB DNS>`. The
  `/api/canary-ingest` path is Cognito-exempt at the ALB (`nest_canary_ingest`
  rule, priority `listener_rule_priority - 1`) and bearer-gated in the app.
- **OpenCanary config search path** is `/etc/opencanaryd/opencanary.conf`,
  `~/.opencanary.conf`, or `./opencanary.conf` — NOT `/etc/opencanaryd.conf`.
- **OpenCanary FTP needs CRLF** to log a login: `printf 'USER x\r\nPASS y\r\nQUIT\r\n' | nc <ip> 21`. Bare LF logs nothing.

## Verify end-to-end

```bash
printf 'USER probe-test\r\nPASS x\r\nQUIT\r\n' | nc 3.230.47.213 21
# then, within ~10s:
#  crabkey:  ghostmode_watch_events shows node phenom-aws-honeypot, USERNAME probe-test
#  nest-ops: CloudWatch /ecs/phenom-dev-nest-ops shows POST /api/canary-ingest 200
#  board:    nest-ops.thephenom.app opencanary tile = running, fresh last_activity_age_s
```
