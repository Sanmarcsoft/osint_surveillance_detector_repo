"""ChromaDB agent knowledge base — seeding and querying.

Collection: ghostmode_agent_docs on 10.0.0.12:18000
"""

import os
import glob
from datetime import datetime, timezone
from typing import Optional

import chromadb

from ghostmode import __version__

_COLLECTION_NAME = "ghostmode_agent_docs"
_KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "agent-knowledge")


def _detect_type(filename: str) -> str:
    for prefix in ("tool_reference", "workflow", "config_guide", "architecture", "troubleshooting"):
        if filename.startswith(prefix):
            return prefix
    return "reference"


def _detect_tool_name(filename: str) -> Optional[str]:
    if filename.startswith("tool_reference_"):
        return filename.replace("tool_reference_", "").replace(".md", "")
    return None


def load_knowledge_docs() -> list[dict]:
    docs = []
    knowledge_dir = os.path.normpath(_KNOWLEDGE_DIR)
    if not os.path.isdir(knowledge_dir):
        return docs

    for path in sorted(glob.glob(os.path.join(knowledge_dir, "*.md"))):
        filename = os.path.basename(path)
        doc_id = filename.replace(".md", "")
        with open(path, "r") as f:
            content = f.read()

        doc_type = _detect_type(filename)
        metadata = {
            "type": doc_type,
            "service": "all",
            "difficulty": "beginner",
            "version": __version__,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tool_name = _detect_tool_name(filename)
        if tool_name:
            metadata["tool_name"] = tool_name

        docs.append({"id": doc_id, "document": content, "metadata": metadata})
    return docs


def seed_docs(host: str = "10.0.0.12", port: int = 18000) -> dict:
    docs = load_knowledge_docs()
    if not docs:
        return {"ok": False, "error": "No knowledge docs found", "count": 0}

    client = chromadb.HttpClient(host=host, port=port)
    collection = client.get_or_create_collection(name=_COLLECTION_NAME)

    collection.upsert(
        ids=[d["id"] for d in docs],
        documents=[d["document"] for d in docs],
        metadatas=[d["metadata"] for d in docs],
    )
    return {"ok": True, "count": len(docs)}


def query_docs(
    query: str,
    n_results: int = 5,
    doc_type: Optional[str] = None,
    host: str = "10.0.0.12",
    port: int = 18000,
) -> dict:
    client = chromadb.HttpClient(host=host, port=port)
    collection = client.get_or_create_collection(name=_COLLECTION_NAME)

    where = {"type": doc_type} if doc_type else None
    raw = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where,
    )

    results = []
    for i in range(len(raw["ids"][0])):
        results.append({
            "id": raw["ids"][0][i],
            "document": raw["documents"][0][i],
            "metadata": raw["metadatas"][0][i],
            "distance": raw["distances"][0][i] if raw.get("distances") else None,
        })
    return {"query": query, "count": len(results), "results": results}
