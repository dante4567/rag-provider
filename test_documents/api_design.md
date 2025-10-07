# RAG Provider API Design

## Overview

The RAG Provider exposes a REST API for document ingestion, search, and management.

## Core Endpoints

### Health Check

```http
GET /health
```

Returns service health status including:
- ChromaDB connection
- LLM provider availability
- OCR capabilities

### Document Ingestion

```http
POST /ingest/file
Content-Type: multipart/form-data

Parameters:
- file: Document file (PDF, DOCX, MD, etc.)
- generate_obsidian: boolean (optional)
- do_index: boolean (optional, default: true)
```

**Example:**
```bash
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@document.pdf" \
  -F "generate_obsidian=true"
```

### Search

```http
POST /search
Content-Type: application/json

{
  "text": "search query",
  "top_k": 5,
  "use_reranking": true
}
```

**Example:**
```bash
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"text": "Q3 revenue", "top_k": 3}'
```

## Advanced Features

### HyDE Query Expansion

The system uses Hypothetical Document Embeddings (HyDE) to improve search quality:

1. Generate hypothetical answer to query
2. Embed hypothetical answer
3. Search with both original query and hypothetical embedding
4. Merge and deduplicate results

### Confidence Gates

Multi-dimensional confidence scoring prevents hallucinations:

- **Relevance** (50% weight): Search score distribution
- **Coverage** (30% weight): Query term presence
- **Quality** (20% weight): Source document quality

Responses are rejected if confidence < 0.6.

## Rate Limiting

| Tier | Rate Limit | Burst |
|------|-----------|-------|
| Free | 10/min | 20 |
| Pro | 100/min | 200 |
| Enterprise | 1000/min | 2000 |

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Invalid request format |
| 401 | Authentication required |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

---
*Version: 2.1*
*Last updated: October 7, 2025*
