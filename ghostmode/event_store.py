"""Persistent event store for security events beyond Cloudflare's 24h window.

Uses ChromaDB on the NAS (10.0.0.12:18000) for permanent storage and
future AI-powered threat analysis. Events are stored with metadata
for filtering and embeddings for semantic search over attack patterns.

A background collector fetches from Cloudflare hourly and appends new events.
Queries for >24h serve from the store; <=24h serve from Cloudflare directly.
"""
from __future__ import annotations

import os
import logging
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

COLLECTION_NAME = "security_events"
CHROMA_HOST = os.getenv("CHROMADB_HOST", "10.0.0.12")
CHROMA_PORT = int(os.getenv("CHROMADB_PORT", "18000"))


_chroma_available: Optional[bool] = None  # cached after first check


def _get_client():
    """Get a ChromaDB client connected to the NAS. Fast-fails if unreachable."""
    global _chroma_available

    # If we already know it's unreachable, don't retry for 5 minutes
    if _chroma_available is False:
        return None

    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        logger.warning("chromadb not installed — event store disabled")
        _chroma_available = False
        return None

    try:
        client = chromadb.HttpClient(
            host=CHROMA_HOST,
            port=CHROMA_PORT,
            settings=Settings(
                chroma_client_auth_provider=None,
                anonymized_telemetry=False,
            ),
        )
        # Fast connectivity check — 2 second timeout via socket
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            sock.connect((CHROMA_HOST, CHROMA_PORT))
            sock.close()
        except (socket.timeout, ConnectionRefusedError, OSError):
            _chroma_available = False
            logger.warning("ChromaDB unreachable at %s:%d — event store disabled", CHROMA_HOST, CHROMA_PORT)
            return None

        client.heartbeat()
        _chroma_available = True
        return client
    except Exception as e:
        _chroma_available = False
        logger.error("ChromaDB connection failed (%s:%d): %s", CHROMA_HOST, CHROMA_PORT, e)
        return None


def _get_collection():
    """Get or create the security_events collection."""
    client = _get_client()
    if not client:
        return None
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Cloudflare firewall events for AI threat analysis"},
    )


def _event_id(evt: dict) -> str:
    """Deterministic ID for deduplication."""
    key = f"{evt.get('timestamp','')}-{evt.get('client_ip','')}-{evt.get('domain','')}-{evt.get('path','')}"
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def _event_to_document(evt: dict) -> str:
    """Create a searchable text document from an event for semantic analysis."""
    parts = [
        f"{evt.get('action', '')} from {evt.get('client_ip', '')}",
        f"country={evt.get('country', '')} asn={evt.get('asn', '')}",
        f"domain={evt.get('domain', '')} host={evt.get('host', '')}",
        f"path={evt.get('path', '')} method={evt.get('method', '')}",
        f"threat={evt.get('threat_level', '')} source={evt.get('source', '')}",
    ]
    if evt.get("is_recon"):
        parts.append("RECON_ATTEMPT")
    if evt.get("user_agent"):
        parts.append(f"ua={evt.get('user_agent', '')[:100]}")
    return " | ".join(parts)


def store_events(events: list[dict]) -> int:
    """Store events in ChromaDB on the NAS. Returns count of new events stored."""
    collection = _get_collection()
    if not collection:
        return 0

    ids = []
    documents = []
    metadatas = []
    for evt in events:
        if evt.get("error"):
            continue
        eid = _event_id(evt)
        ids.append(eid)
        documents.append(_event_to_document(evt))
        metadatas.append({
            "timestamp": str(evt.get("timestamp", "")),
            "domain": evt.get("domain", ""),
            "host": evt.get("host", ""),
            "path": evt.get("path", ""),
            "method": evt.get("method", ""),
            "action": evt.get("action", ""),
            "source": evt.get("source", ""),
            "client_ip": evt.get("client_ip", ""),
            "country": evt.get("country", ""),
            "asn": evt.get("asn", ""),
            "is_recon": evt.get("is_recon", False),
            "threat_level": evt.get("threat_level", "info"),
        })

    if not ids:
        return 0

    try:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        logger.info("Stored %d events in ChromaDB", len(ids))
        return len(ids)
    except Exception as e:
        logger.error("ChromaDB upsert failed: %s", e)
        return 0


def query_events(
    hours_back: float = 168,
    domain: Optional[str] = None,
    limit: int = 500,
) -> list[dict]:
    """Query events from ChromaDB on the NAS."""
    collection = _get_collection()
    if not collection:
        return []

    since = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()

    where_filter: dict = {"timestamp": {"$gte": since}}
    if domain:
        where_filter = {"$and": [
            {"timestamp": {"$gte": since}},
            {"domain": {"$eq": domain}},
        ]}

    try:
        results = collection.get(
            where=where_filter,
            limit=limit,
            include=["metadatas"],
        )
        events = []
        for meta in results.get("metadatas", []):
            events.append({
                "timestamp": meta.get("timestamp", ""),
                "domain": meta.get("domain", ""),
                "host": meta.get("host", ""),
                "path": meta.get("path", ""),
                "method": meta.get("method", ""),
                "action": meta.get("action", ""),
                "source": meta.get("source", ""),
                "client_ip": meta.get("client_ip", ""),
                "country": meta.get("country", ""),
                "asn": meta.get("asn", ""),
                "is_recon": meta.get("is_recon", False),
                "threat_level": meta.get("threat_level", "info"),
            })
        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return events
    except Exception as e:
        logger.error("ChromaDB query failed: %s", e)
        return []


def search_threats(query: str, n_results: int = 20) -> list[dict]:
    """Semantic search over stored security events for AI analysis.

    Use natural language queries like:
    - "recon scanning from China"
    - "blocked requests targeting admin paths"
    - "bot activity on thephenom.app"
    """
    collection = _get_collection()
    if not collection:
        return []

    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["metadatas", "documents", "distances"],
        )
        events = []
        for i, meta in enumerate(results.get("metadatas", [[]])[0]):
            evt = dict(meta)
            evt["relevance"] = 1 - results["distances"][0][i] if results.get("distances") else 0
            events.append(evt)
        return events
    except Exception as e:
        logger.error("ChromaDB search failed: %s", e)
        return []


def get_event_count() -> int:
    """Get total event count in the store."""
    collection = _get_collection()
    if not collection:
        return 0
    try:
        return collection.count()
    except Exception:
        return 0
