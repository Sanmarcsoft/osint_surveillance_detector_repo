# Tool Reference: ghostmode docs query

## Overview

The `ghostmode docs query` command searches the ChromaDB agent knowledge base (`ghostmode_agent_docs` collection) using semantic similarity. Returns the most relevant documentation chunks for a given query string.

## CLI Syntax

```bash
ghostmode docs query "how to check stack health"
ghostmode docs query "brute force investigation" --n-results 3
ghostmode docs query "env vars" --type config_guide
ghostmode docs query "FTP canary" --type tool_reference --n-results 5
```

## MCP Tool

**Tool name**: `ghostmode_docs_query`

| Parameter | Type    | Default | Description                                              |
|-----------|---------|---------|----------------------------------------------------------|
| query     | string  | —       | Required. Natural language search query                  |
| n_results | integer | 5       | Number of results to return (1-20)                       |
| doc_type  | string  | none    | Filter by document type (see valid values below)         |

### Valid `doc_type` Values

| Value           | Description                              |
|-----------------|------------------------------------------|
| tool_reference  | CLI tool and MCP tool reference docs     |
| workflow        | Multi-step operational workflow recipes  |
| config_guide    | Configuration and environment variable guides |
| architecture    | System architecture and topology docs    |
| troubleshooting | Error diagnosis and resolution guides    |

## JSON Output Schema

```json
{
  "query": "how to check stack health",
  "count": 3,
  "results": [
    {
      "id": "workflow_verify_stack_health",
      "document": "# Workflow: Verify Stack Health\n...",
      "metadata": {
        "type": "workflow",
        "service": "all",
        "version": "0.1.0"
      },
      "distance": 0.12
    }
  ]
}
```

### Result Fields

| Field    | Type   | Description                                         |
|----------|--------|-----------------------------------------------------|
| id       | string | Document ID (matches filename without `.md`)        |
| document | string | Full document content                               |
| metadata | object | Document metadata (type, version, tool_name, etc.)  |
| distance | float  | Semantic distance score — lower is more relevant    |

## Exit Codes

| Code | Meaning                              |
|------|--------------------------------------|
| 0    | Query completed successfully         |
| 1    | ChromaDB unreachable or query error  |

## Examples

Find workflow documentation for handling brute force attacks:
```bash
$ ghostmode docs query "brute force attack" --type workflow
```

Find all tool references for the alert command:
```bash
$ ghostmode docs query "send alert notification" --type tool_reference --n-results 3
```

## Notes

- The knowledge base must be seeded first: `ghostmode docs seed` (or call `seed_docs()` from Python).
- Semantic search uses the sentence-transformer model configured in ChromaDB.
- Distance scores below 0.3 indicate a strong semantic match.
- The ChromaDB host is configured via `CHROMADB_HOST` and `CHROMADB_PORT` env vars (default: `10.0.0.12:18000`).
