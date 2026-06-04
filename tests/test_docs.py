from unittest.mock import patch, MagicMock
from ghostmode.docs import seed_docs, query_docs, load_knowledge_docs


def test_load_knowledge_docs_returns_list():
    docs = load_knowledge_docs()
    assert isinstance(docs, list)
    assert len(docs) > 0
    for doc in docs:
        assert "id" in doc
        assert "document" in doc
        assert "metadata" in doc
        assert "type" in doc["metadata"]


def test_seed_docs_upserts_to_chromadb():
    mock_collection = MagicMock()
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    with patch("ghostmode.docs.chromadb.HttpClient", return_value=mock_client):
        result = seed_docs(host="10.0.0.12", port=18000)
    assert result["ok"] is True
    assert result["count"] > 0
    mock_collection.upsert.assert_called_once()


def test_query_docs_returns_results():
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [["tool_reference_status"]],
        "documents": [["# ghostmode status\nCheck service health."]],
        "metadatas": [[{"type": "tool_reference", "tool_name": "status"}]],
        "distances": [[0.1]],
    }
    mock_client = MagicMock()
    mock_client.get_or_create_collection.return_value = mock_collection
    with patch("ghostmode.docs.chromadb.HttpClient", return_value=mock_client):
        result = query_docs("how to check health", n_results=3)
    assert len(result["results"]) == 1
    assert result["results"][0]["id"] == "tool_reference_status"
