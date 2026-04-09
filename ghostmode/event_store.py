"""Persistent event store for security events on AWS RDS PostgreSQL.

Stores Cloudflare firewall events for long-term analysis (days, weeks, months).
Runs on the same RDS instance as Synapse (phenom-dev-postgres), reachable from ECS.
Background collector fetches hourly; API serves historical data for >24h ranges.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

_initialized = False


def _get_conn():
    """Get a PostgreSQL connection to the RDS instance."""
    import psycopg2

    host = os.getenv("DB_HOST", "phenom-dev-postgres.c8toq6uq223c.us-east-1.rds.amazonaws.com")
    port = int(os.getenv("DB_PORT", "5432"))
    user = os.getenv("DB_USER", "nestops")
    password = os.getenv("DB_PASSWORD", "")
    dbname = os.getenv("DB_NAME", "nestops")

    return psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname,
                            connect_timeout=5, sslmode="require")


def _ensure_schema():
    """Create the security_events table if it doesn't exist."""
    global _initialized
    if _initialized:
        return

    try:
        conn = _get_conn()
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS security_events (
                    id BIGSERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL,
                    domain TEXT NOT NULL,
                    host TEXT,
                    path TEXT,
                    method TEXT,
                    action TEXT,
                    source TEXT,
                    client_ip TEXT,
                    country TEXT,
                    asn TEXT,
                    user_agent TEXT,
                    is_recon BOOLEAN DEFAULT FALSE,
                    threat_level TEXT,
                    ingested_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_events_dedup
                ON security_events(timestamp, client_ip, domain, path)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_ts ON security_events(timestamp DESC)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_domain ON security_events(domain)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_threat ON security_events(threat_level)
            """)
        conn.close()
        _initialized = True
        logger.info("Event store schema ready")
    except Exception as e:
        logger.error("Schema init failed: %s", e)


def store_events(events: list[dict]) -> int:
    """Store events in PostgreSQL. Deduplicates on (timestamp, client_ip, domain, path)."""
    _ensure_schema()

    try:
        conn = _get_conn()
        conn.autocommit = True
    except Exception as e:
        logger.error("DB connection failed: %s", e)
        return 0

    inserted = 0
    try:
        with conn.cursor() as cur:
            for evt in events:
                if evt.get("error"):
                    continue
                try:
                    cur.execute("""
                        INSERT INTO security_events
                            (timestamp, domain, host, path, method, action, source,
                             client_ip, country, asn, user_agent, is_recon, threat_level)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (timestamp, client_ip, domain, path) DO NOTHING
                    """, (
                        evt.get("timestamp"),
                        evt.get("domain", ""),
                        evt.get("host", ""),
                        evt.get("path", ""),
                        evt.get("method", ""),
                        evt.get("action", ""),
                        evt.get("source", ""),
                        evt.get("client_ip", ""),
                        evt.get("country", ""),
                        evt.get("asn", ""),
                        evt.get("user_agent", ""),
                        evt.get("is_recon", False),
                        evt.get("threat_level", "info"),
                    ))
                    if cur.rowcount > 0:
                        inserted += 1
                except Exception as e:
                    logger.debug("Event insert skipped: %s", e)
    finally:
        conn.close()

    logger.info("Stored %d new events (of %d)", inserted, len(events))
    return inserted


def query_events(
    hours_back: float = 168,
    domain: Optional[str] = None,
    limit: int = 500,
) -> list[dict]:
    """Query historical events from PostgreSQL."""
    _ensure_schema()

    since = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            sql = """
                SELECT timestamp, domain, host, path, method, action, source,
                       client_ip, country, asn, user_agent, is_recon, threat_level
                FROM security_events
                WHERE timestamp > %s
            """
            params: list = [since]
            if domain:
                sql += " AND domain = %s"
                params.append(domain)
            sql += " ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)

            cur.execute(sql, params)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
        conn.close()

        events = []
        for row in rows:
            evt = dict(zip(columns, row))
            # Convert datetime to ISO string for JSON serialization
            if hasattr(evt.get("timestamp"), "isoformat"):
                evt["timestamp"] = evt["timestamp"].isoformat()
            events.append(evt)
        return events
    except Exception as e:
        logger.error("Event query failed: %s", e)
        return []


def get_event_count(hours_back: float = 720) -> int:
    """Total events in the store for the given window."""
    _ensure_schema()
    since = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM security_events WHERE timestamp > %s", (since,))
            count = cur.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def get_stats() -> dict:
    """Store statistics for the /api/store-stats endpoint."""
    _ensure_schema()
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM security_events")
            total = cur.fetchone()[0]
            cur.execute("SELECT MIN(timestamp), MAX(timestamp) FROM security_events")
            row = cur.fetchone()
            oldest = row[0].isoformat() if row[0] else None
            newest = row[1].isoformat() if row[1] else None
            cur.execute("""
                SELECT domain, COUNT(*) as cnt
                FROM security_events
                GROUP BY domain ORDER BY cnt DESC
            """)
            by_domain = {r[0]: r[1] for r in cur.fetchall()}
        conn.close()
        return {
            "backend": "postgresql",
            "host": os.getenv("DB_HOST", "phenom-dev-postgres"),
            "total_events": total,
            "oldest_event": oldest,
            "newest_event": newest,
            "by_domain": by_domain,
        }
    except Exception as e:
        return {"backend": "postgresql", "error": str(e), "total_events": 0}
