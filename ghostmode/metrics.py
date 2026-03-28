"""Prometheus metrics for external monitoring by ops.sanmarcsoft.com.

All metrics are prefixed with `ghostmode_`. The MCP server exposes these
at :3200/metrics for Prometheus to scrape over Tailscale.
"""

from prometheus_client import Counter, Histogram, Gauge

# Counters
honeypot_hits = Counter(
    "ghostmode_honeypot_hits_total",
    "Total honeypot events detected",
    ["service", "port"],
)

alerts_sent = Counter(
    "ghostmode_alerts_sent_total",
    "Total alerts successfully delivered",
    ["channel"],
)

alerts_failed = Counter(
    "ghostmode_alerts_failed_total",
    "Total alert delivery failures",
    ["channel", "error"],
)

mcp_calls = Counter(
    "ghostmode_mcp_calls_total",
    "Total MCP tool invocations",
    ["tool"],
)

# Histograms
alert_latency = Histogram(
    "ghostmode_alert_latency_seconds",
    "Time from honeypot hit to alert delivery",
    ["channel"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

mcp_latency = Histogram(
    "ghostmode_mcp_latency_seconds",
    "MCP tool call duration",
    ["tool"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0),
)

# Gauges
services_up = Gauge(
    "ghostmode_services_up",
    "Whether a service is up (1) or down (0)",
    ["service"],
)

uptime_seconds = Gauge(
    "ghostmode_uptime_seconds",
    "Process uptime in seconds",
)

log_lines_total = Gauge(
    "ghostmode_log_lines_total",
    "Total canary log lines processed",
)
