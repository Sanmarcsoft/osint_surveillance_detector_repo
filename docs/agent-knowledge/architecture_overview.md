# Architecture Overview: Ghost Mode Stack

## System Purpose

Ghost Mode is a self-hosted OSINT surveillance detection system. It runs a set of honeypot (canary) services that log any probe or connection attempt, then routes alerts through ntfy for real-time notification. A CLI and MCP server expose the entire system to human operators and AI agents.

## Public FQDN

```
crabkey.sanmarcsoft.com
```

Tailscale provides zero-trust mesh networking between the stack and authorized clients.

## Service Topology

| Service       | Role                        | Internal Port | External Access         | Container Name        |
|---------------|-----------------------------|---------------|-------------------------|-----------------------|
| OpenCanary    | Honeypot canary services     | 8081 (HTTP), 2121 (FTP) | Via Tailscale | opencanary      |
| ntfy          | Push notification server    | 80            | Via Tailscale           | ntfy                  |
| SpiderFoot    | OSINT recon engine          | 5001          | Via Tailscale           | spiderfoot            |
| Tailscale     | Mesh VPN / zero trust        | —             | crabkey.sanmarcsoft.com | tailscale             |
| ghostmode MCP | MCP + CLI interface         | 3200          | Via Tailscale           | ghostmode-mcp         |
| ChromaDB      | Vector database (external)  | 18000         | 10.0.0.12:18000 (NAS)  | (NAS-hosted)          |

## Data Flow

```
External Attacker
      |
      v
OpenCanary (ports 8081, 2121)
      |  writes JSON events
      v
/var/log/opencanary/opencanary.log
      |
      +---> ghostmode watch (real-time tail)
      |           |
      |           v
      |        Alert trigger
      |           |
      |           v
      |         ntfy server --> push notification --> operator device
      |
      +---> ghostmode logs query (historical queries)
      |
      +---> ghostmode status / config validate (health checks)

ghostmode MCP server (port 3200)
      |
      +--> AI agents / Claude Code call MCP tools
      |
      +--> ChromaDB 10.0.0.12:18000 (knowledge base queries)
```

## Network Boundaries

| Boundary                         | Protection              |
|----------------------------------|-------------------------|
| Internet -> canary ports         | Intentionally open (honeypot design) |
| Internet -> ntfy / SpiderFoot / MCP | Blocked; Tailscale only |
| Operator -> stack                | Tailscale mesh VPN      |
| ghostmode -> ChromaDB            | Private LAN (10.0.0.x)  |

## Key Design Principles

1. **Canary services are intentionally accessible** — they are designed to attract and log probes.
2. **No canary service accepts real logins** — all credentials entered are logged, none are valid.
3. **Alerting is push-based** — operators receive ntfy notifications without polling.
4. **AI-native** — MCP server on port 3200 exposes all tools to Claude and other AI agents.
5. **Sovereign storage** — knowledge base and event data remain on the local NAS (10.0.0.x) or Scaleway EU infrastructure.

## File Locations

| File                            | Description                             |
|---------------------------------|-----------------------------------------|
| `docker-compose.yml`            | Stack definition                        |
| `.env`                          | Runtime configuration (never committed) |
| `opencanary/opencanary.conf`    | OpenCanary service configuration        |
| `/var/log/opencanary/opencanary.log` | Live event log                     |
| `ghostmode/`                    | Python package (CLI + MCP server)       |
| `docs/agent-knowledge/`        | ChromaDB agent knowledge base docs      |
