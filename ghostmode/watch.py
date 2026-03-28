"""OpenCanary log tailer with structured event emission."""

import os
import time
import json
from typing import Optional, Generator

from ghostmode.models import HoneypotEvent
from ghostmode.sanitize import sanitize
from ghostmode import metrics


def parse_event(line: str) -> Optional[HoneypotEvent]:
    """Parse a single OpenCanary JSON log line into a HoneypotEvent."""
    try:
        raw = json.loads(line.strip())
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None

    # Filter out OpenCanary internal/startup messages (no service or src_host)
    if not raw.get("src_host") and not raw.get("dst_port"):
        return None

    return HoneypotEvent(
        timestamp=str(raw.get("local_time") or raw.get("timestamp") or "unknown"),
        node=str(raw.get("node_id", "unknown")),
        service=str(raw.get("service", "unknown")),
        port=int(raw.get("dst_port") or 0),
        src_host=str(raw.get("src_host", "unknown")),
        logdata=raw.get("logdata", {}),
    )


def tail_file(path: str) -> Generator[str, None, None]:
    """Tail -F style reader with log rotation detection."""
    while not os.path.exists(path):
        time.sleep(2)

    with open(path, "r") as f:
        f.seek(0, os.SEEK_END)
        inode = os.fstat(f.fileno()).st_ino

        while True:
            line = f.readline()
            if line:
                yield line
            else:
                time.sleep(0.5)
                try:
                    if os.stat(path).st_ino != inode:
                        with open(path, "r") as nf:
                            f.close()
                            f = nf
                            inode = os.fstat(f.fileno()).st_ino
                            f.seek(0, os.SEEK_END)
                except FileNotFoundError:
                    time.sleep(1)


def watch_loop(log_path: str, callback):
    """Tail the canary log, parse events, and call callback(HoneypotEvent) for each."""
    for line in tail_file(log_path):
        evt = parse_event(line)
        if evt:
            metrics.honeypot_hits.labels(service=sanitize(evt.service), port=str(evt.port)).inc()
            metrics.log_lines_total.inc()
            callback(evt)
