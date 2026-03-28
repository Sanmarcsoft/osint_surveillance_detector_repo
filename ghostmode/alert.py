"""Alert delivery via ntfy and Signal with Prometheus instrumentation."""

import time
import shutil
import subprocess
from typing import Optional

import requests

from ghostmode.models import AlertResult
from ghostmode.sanitize import validate_phone, validate_url
from ghostmode import metrics


def send_ntfy(
    message: str,
    server: str,
    topic: str,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> AlertResult:
    """Send alert via ntfy. Returns structured result."""
    url = f"{server.rstrip('/')}/{topic}"
    if not validate_url(url):
        return AlertResult(channel="ntfy", success=False, error="Invalid ntfy URL")

    start = time.monotonic()
    try:
        auth = (user, password) if user and password else None
        resp = requests.post(url, data=message.encode("utf-8"), auth=auth, timeout=10)
        resp.raise_for_status()
        metrics.alerts_sent.labels(channel="ntfy").inc()
        metrics.alert_latency.labels(channel="ntfy").observe(time.monotonic() - start)
        return AlertResult(channel="ntfy", success=True, status_code=resp.status_code)
    except requests.RequestException as e:
        metrics.alerts_failed.labels(channel="ntfy", error=type(e).__name__).inc()
        return AlertResult(channel="ntfy", success=False, error=str(e))


def send_signal(message: str, phone: str, recipient: str) -> AlertResult:
    """Send alert via signal-cli. Returns structured result."""
    if not validate_phone(phone) or not validate_phone(recipient):
        return AlertResult(channel="signal", success=False, error="Invalid phone number format")
    if not shutil.which("signal-cli"):
        return AlertResult(channel="signal", success=False, error="signal-cli not on PATH")

    start = time.monotonic()
    try:
        result = subprocess.run(
            ["signal-cli", "-u", phone, "send", recipient, "-m", message],
            check=True,
            timeout=30,
            capture_output=True,
        )
        metrics.alerts_sent.labels(channel="signal").inc()
        metrics.alert_latency.labels(channel="signal").observe(time.monotonic() - start)
        return AlertResult(channel="signal", success=True)
    except subprocess.TimeoutExpired:
        metrics.alerts_failed.labels(channel="signal", error="timeout").inc()
        return AlertResult(channel="signal", success=False, error="signal-cli timed out")
    except subprocess.CalledProcessError as e:
        metrics.alerts_failed.labels(channel="signal", error="exit_code").inc()
        return AlertResult(channel="signal", success=False, error=f"exit {e.returncode}")
