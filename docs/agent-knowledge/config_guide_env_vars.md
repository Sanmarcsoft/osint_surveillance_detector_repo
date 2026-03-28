# Config Guide: Environment Variables

## Overview

All Ghost Mode runtime configuration is provided via environment variables. Set them in a `.env` file at the project root (never commit this file — it is in `.gitignore`).

Copy `.env.example` to `.env` and fill in your values before running `docker-compose up`.

## Required Variables

| Variable          | Type   | Default | Description                                              |
|-------------------|--------|---------|----------------------------------------------------------|
| `NTFY_SERVER`     | URL    | —       | Base URL of the ntfy server, e.g. `http://10.0.0.12:80` |
| `NTFY_TOPIC`      | string | —       | ntfy topic name, e.g. `ghostmode-alerts`                 |
| `OPENCANARY_LOG`  | path   | —       | Absolute path to OpenCanary log file, e.g. `/var/log/opencanary/opencanary.log` |

## Optional Variables

| Variable             | Type    | Default         | Description                                                  |
|----------------------|---------|-----------------|--------------------------------------------------------------|
| `TS_AUTHKEY`         | string  | —               | Tailscale auth key for automatic node registration           |
| `ALERT_MODE`         | string  | `ntfy`          | Alert delivery channel: `ntfy` or `signal`                   |
| `SIGNAL_PHONE`       | string  | —               | Signal CLI sender phone number (E.164 format, e.g. `+15551234567`) |
| `SIGNAL_RECIPIENT`   | string  | —               | Signal CLI recipient phone number (E.164 format)             |
| `CHROMADB_HOST`      | string  | `10.0.0.12`     | ChromaDB server hostname or IP                               |
| `CHROMADB_PORT`      | integer | `18000`         | ChromaDB server port                                         |
| `MCP_PORT`           | integer | `3200`          | Port for the ghostmode MCP server                            |
| `GHOSTMODE_FORMAT`   | string  | `json`          | Default output format for CLI commands: `json` or `text`     |

## Variable Details

### `NTFY_SERVER`

The full base URL of your ntfy instance. Include the scheme and port:
```
NTFY_SERVER=http://10.0.0.12:80
```

For a public ntfy instance: `NTFY_SERVER=https://ntfy.sh`

### `NTFY_TOPIC`

The topic name alerts are published to. Choose a non-guessable name to avoid unauthorized subscriptions:
```
NTFY_TOPIC=ghostmode-xk92j
```

### `OPENCANARY_LOG`

The path where OpenCanary writes its JSON log. Must be accessible from the ghostmode container. If using Docker volumes, ensure the path is mounted consistently:
```
OPENCANARY_LOG=/var/log/opencanary/opencanary.log
```

### `TS_AUTHKEY`

A Tailscale ephemeral auth key from the Tailscale admin console. If not set, Tailscale will require manual `tailscale up` inside the container.

### `ALERT_MODE`

When set to `signal`, ghostmode routes alerts through Signal CLI instead of ntfy. Requires `SIGNAL_PHONE` and `SIGNAL_RECIPIENT` to be set, and a running Signal CLI container.

### `CHROMADB_HOST` / `CHROMADB_PORT`

Location of the ChromaDB server for the agent knowledge base. The default points to the NAS at `10.0.0.12:18000`.

### `GHOSTMODE_FORMAT`

Sets the default output format for all CLI commands. Individual commands can override this with `--format json` or `--format text`.

## Validation

Run `ghostmode config validate` to check all required variables are set and the configuration is valid before starting monitoring workflows.

## Security Notes

- Never commit `.env` to version control.
- Rotate `TS_AUTHKEY` after node registration.
- Use a unique, random `NTFY_TOPIC` to prevent unauthorized subscribers from receiving your alerts.
- `SIGNAL_PHONE` and `SIGNAL_RECIPIENT` are phone numbers — handle with care.
