# Ghost Mode OSINT Stack (with OpenCanary)

This package deploys:
- SpiderFoot (OSINT engine)
- ntfy (push notifications)
- Tailscale (private global access)
- OpenCanary (honeypot) + real-time watcher wired to ntfy

## Quick Start
```bash
./setup.sh          # creates venv, installs deps, sets up pre-commit hooks
# edit .env with your values (TS_AUTHKEY, NTFY_*, etc.)
docker compose up -d --build
```

## Services
- ntfy -> http://localhost (bound to 127.0.0.1; use Tailscale for remote)
- OpenCanary ports (Tailscale-only recommended):
  - HTTP 8081
  - FTP 2121

## Alerts
- `alerts` service: sends a startup test message to your ntfy topic
- `canary_watcher`: tails `/logs/opencanary/opencanary.log` and pushes every hit to ntfy

## Security

See [SECURITY.md](SECURITY.md) for the full threat model.

- All dependencies pinned to exact versions
- Docker images pinned to SHA256 digests
- Containers run with `no-new-privileges`, `cap_drop: ALL`, `read_only`
- Pre-commit hooks block secrets and large files
- CI runs secret scanning, dependency audit, SAST, and Dockerfile linting
- Honeypot log data is sanitized before forwarding (control chars stripped, length capped)
