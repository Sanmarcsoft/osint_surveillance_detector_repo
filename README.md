# Ghost Mode OSINT Stack

Honeypot + OSINT monitoring with a unified CLI, MCP server, and AI agent
knowledge base. Deployed as a Nix-built OCI image at crabkey.sanmarcsoft.com.

## Quick Start (Local Dev)

```bash
./setup.sh
ghostmode status
```

## Quick Start (Production)

```bash
nix build .#packages.x86_64-linux.oci-image
skopeo copy docker-archive:result docker://rg.fr-par.scw.cloud/sanmarcsoft/ghostmode:testing
```

## CLI

All commands return JSON by default.

```bash
ghostmode status                    # service health
ghostmode watch                     # tail honeypot logs
ghostmode alert test                # send test alert
ghostmode alerts list --limit 10    # recent events
ghostmode logs query --service http # structured log search
ghostmode config validate           # check configuration
ghostmode docs seed                 # seed ChromaDB knowledge base
ghostmode docs query "question"     # search knowledge base
ghostmode serve                     # start MCP server on :3200
```

## AI Agents

See [AGENTS.md](AGENTS.md) for the agent integration guide.

## Monitoring

Prometheus metrics at `:3200/metrics`, health check at `:3200/health`.
Scraped by ops.sanmarcsoft.com Grafana.

## Security

See [SECURITY.md](SECURITY.md) for threat model and safety guidelines.
