"""Click CLI router — all commands default to JSON output."""

import sys
import json

import click

from ghostmode import __version__
from ghostmode.models import Envelope
from ghostmode.config import load_config, validate_config
from ghostmode.status import get_status
from ghostmode.alert import send_ntfy, send_signal
from ghostmode.logs import query_logs
from ghostmode.watch import watch_loop


class OutputFormatter:
    def __init__(self, fmt: str):
        self.fmt = fmt

    def output(self, envelope: Envelope):
        if self.fmt == "json":
            click.echo(envelope.to_json())
        else:
            d = envelope.to_dict()
            if d["ok"]:
                click.echo(f"[OK] {d['command']}")
                click.echo(json.dumps(d.get("data", {}), indent=2, default=str))
            else:
                click.echo(f"[ERROR] {d['command']}: {d['error']['message']}")


pass_formatter = click.make_pass_decorator(OutputFormatter)


@click.group()
@click.option("--format", "fmt", type=click.Choice(["json", "text"]), default="json", envvar="GHOSTMODE_FORMAT")
@click.version_option(__version__)
@click.pass_context
def cli(ctx, fmt):
    """Ghost Mode OSINT Stack — CLI for agents and humans."""
    ctx.obj = OutputFormatter(fmt)


@cli.command()
@pass_formatter
def status(formatter):
    """Check health of all Ghost Mode services."""
    cfg = load_config()
    data = get_status(
        ntfy_server=cfg["ntfy_server"],
        ntfy_topic=cfg["ntfy_topic"],
        canary_log=cfg["opencanary_log"],
    )
    formatter.output(Envelope.success("status", data))


@cli.group()
def config():
    """Configuration commands."""
    pass


@config.command("validate")
@pass_formatter
def config_validate(formatter):
    """Validate all configuration."""
    result = validate_config()
    if result["ok"]:
        formatter.output(Envelope.success("config.validate", result))
    else:
        formatter.output(Envelope.error("config.validate", "INVALID_CONFIG", json.dumps(result["issues"])))
        sys.exit(2)


@cli.group()
def alert():
    """Alert commands."""
    pass


@alert.command("test")
@pass_formatter
def alert_test(formatter):
    """Send a test alert."""
    cfg = load_config()
    result = send_ntfy(
        "Ghost Mode test alert",
        server=cfg["ntfy_server"],
        topic=cfg["ntfy_topic"],
        user=cfg["ntfy_user"],
        password=cfg["ntfy_pass"],
    )
    if result.success:
        formatter.output(Envelope.success("alert.test", result.to_dict()))
    else:
        formatter.output(Envelope.error("alert.test", "ALERT_FAILED", result.error))
        sys.exit(1)


@cli.group()
def alerts():
    """Query alerts."""
    pass


@alerts.command("list")
@click.option("--since", default=None, help="ISO timestamp filter")
@click.option("--limit", default=100, type=int)
@click.option("--service", default=None)
@pass_formatter
def alerts_list(formatter, since, limit, service):
    """List recent honeypot events from logs."""
    cfg = load_config()
    events = query_logs(cfg["opencanary_log"], service=service, since=since, limit=limit)
    formatter.output(Envelope.success("alerts.list", {"count": len(events), "events": events}))


@cli.group()
def logs():
    """Log query commands."""
    pass


@logs.command("query")
@click.option("--since", default=None)
@click.option("--service", default=None)
@click.option("--src-host", default=None)
@click.option("--limit", default=100, type=int)
@pass_formatter
def logs_query(formatter, since, service, src_host, limit):
    """Query structured OpenCanary logs."""
    cfg = load_config()
    events = query_logs(cfg["opencanary_log"], service=service, src_host=src_host, since=since, limit=limit)
    formatter.output(Envelope.success("logs.query", {"count": len(events), "events": events}))


@cli.command()
@click.option("--log", default=None, help="Path to OpenCanary log")
@pass_formatter
def watch(formatter, log):
    """Tail OpenCanary log and emit structured events."""
    cfg = load_config()
    log_path = log or cfg["opencanary_log"]
    click.echo(json.dumps({"event": "watch_started", "log": log_path}), err=True)

    def on_event(evt):
        click.echo(evt.to_json())
        if cfg["alert_mode"] in ("ntfy", "both"):
            send_ntfy(evt.to_json(), server=cfg["ntfy_server"], topic=cfg["ntfy_topic"],
                      user=cfg["ntfy_user"], password=cfg["ntfy_pass"])
        if cfg["alert_mode"] in ("signal", "both"):
            send_signal(evt.to_json(), phone=cfg.get("signal_phone", ""),
                        recipient=cfg.get("signal_recipient", ""))

    watch_loop(log_path, on_event)


@cli.group()
def docs():
    """Agent knowledge base commands."""
    pass


@docs.command("seed")
@pass_formatter
def docs_seed(formatter):
    """Seed the ChromaDB agent knowledge base."""
    cfg = load_config()
    from ghostmode.docs import seed_docs
    result = seed_docs(host=cfg["chromadb_host"], port=cfg["chromadb_port"])
    if result["ok"]:
        formatter.output(Envelope.success("docs.seed", result))
    else:
        formatter.output(Envelope.error("docs.seed", "SEED_FAILED", result.get("error", "unknown")))
        sys.exit(1)


@docs.command("query")
@click.argument("query_text")
@click.option("--n-results", default=5, type=int)
@click.option("--type", "doc_type", default=None)
@pass_formatter
def docs_query(formatter, query_text, n_results, doc_type):
    """Search the agent knowledge base."""
    cfg = load_config()
    from ghostmode.docs import query_docs
    result = query_docs(query_text, n_results=n_results, doc_type=doc_type,
                        host=cfg["chromadb_host"], port=cfg["chromadb_port"])
    formatter.output(Envelope.success("docs.query", result))


@cli.command()
@click.option("--port", default=3200, type=int, envvar="MCP_PORT")
def serve(port):
    """Start the MCP server."""
    from ghostmode.mcp_server import create_server
    server = create_server(port)
    server.run(transport="http", port=port)
