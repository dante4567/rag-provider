# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

```bash
# Start the service
docker-compose up -d

# Health check
curl http://localhost:8001/health

# Upload document
curl -X POST -F "file=@doc.pdf" http://localhost:8001/ingest/file

# Search
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"text": "query", "top_k": 5}'
```

## Architecture Overview

**Service-Oriented Design** - The system uses a clean service layer architecture:

```
app.py (1,625 lines)           # FastAPI application, all endpoints
├── src/services/              # Business logic layer
│   ├── enrichment_service_v2.py      # V2: Controlled vocabulary enrichment
│   ├── obsidian_service_v3.py        # V3: RAG-first markdown export
│   ├── chunking_service.py           # Structure-aware semantic chunking
│   ├── vocabulary_service.py         # Controlled tag vocabularies
│   ├── document_service.py           # 13+ file format extraction
│   ├── llm_service.py                # Multi-provider LLM with fallbacks
│   ├── vector_service.py             # ChromaDB vector operations
│   └── ocr_service.py                # OCR for images/scanned docs
├── src/core/
│   ├── config.py              # Settings management
│   └── dependencies.py        # Dependency injection
└── src/models/                # Pydantic schemas
```

### Key Architectural Concepts

**Enrichment Pipeline V2** (active version):
- Uses controlled vocabulary from `vocabulary/*.yaml` (no invented tags)
- Separates entities (people, places) from topics
- Calculates recency scoring with exponential decay
- Better title extraction and project auto-matching

**Structure-Aware Chunking**:
- Chunks along semantic boundaries (headings, tables, code blocks)
- Keeps section context in chunk metadata
- Tables and code blocks = standalone chunks
- Rich metadata: `section_title`, `parent_sections`, `chunk_type`, `sequence`

**Obsidian Export V3** (RAG-first):
- Creates stub files in `refs/` for entities (people, places, projects)
- Main doc links to entity stubs via `[[Entity Name]]`
- Clean YAML frontmatter (no Python str representations)
- Compatible with Dataview queries

**LLM Fallback Chain**:
- Primary: Groq (ultra-cheap, fast)
- Fallback: Anthropic (balanced)
- Emergency: OpenAI (reliable)
- Configured via environment variables

## Development Commands

```bash
# Docker operations
docker-compose up --build -d     # Start/rebuild
docker-compose logs -f rag-service  # View logs
docker-compose down              # Stop
docker system prune -a -f        # Clean Docker space

# Testing
docker exec rag_service pytest tests/unit/ -v           # Unit tests
docker exec rag_service pytest tests/integration/ -v    # Integration tests
docker exec rag_service pytest tests/unit/test_vector_service.py -v  # Specific test

# Copy vocabulary into container (after updates)
docker cp vocabulary/ rag_service:/app/vocabulary/
docker-compose restart rag-service

# Verify V2 initialized
docker logs rag_service 2>&1 | grep -A 5 "Enrichment V2"
```

## Environment Setup

Copy `.env.example` to `.env` and configure:

```bash
# Required LLM API keys (at least one provider)
GROQ_API_KEY=gsk_...
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# ChromaDB connection (Docker auto-configures)
CHROMA_HOST=chromadb
CHROMA_PORT=8000

# LLM fallback priority
DEFAULT_LLM=groq
FALLBACK_LLM=anthropic
EMERGENCY_LLM=openai

# Feature flags
ENABLE_FILE_WATCH=true
CREATE_OBSIDIAN_LINKS=true
USE_OCR=true
```

## Frontend Interfaces

### Web UI (Gradio) - Recommended for testing
```bash
cd web-ui && pip install -r requirements.txt && python app.py
# Open: http://localhost:7860
```

### Telegram Bot - Mobile document upload
```bash
export TELEGRAM_BOT_TOKEN="your_token"
cd telegram-bot && pip install -r requirements.txt && python rag_bot.py
```

## Controlled Vocabulary System

The system uses curated vocabularies in `vocabulary/*.yaml`:

- **topics.yaml** - Hierarchical topics (e.g., `school/admin/enrollment`)
- **projects.yaml** - Time-bound focus areas (e.g., `school-2026`)
- **places.yaml** - Locations and institutions
- **people.yaml** - Privacy-safe role identifiers

LLM enrichment ONLY assigns tags from these vocabularies. Unknown tags go to `suggested_tags` for review.

## Testing Strategy

See `TESTING_NOW.md` for comprehensive guide. Quick validation:

```bash
# Upload test document with structure
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@test.md" \
  -F "generate_obsidian=true" | jq

# Verify:
# - enrichment_version: "2.0"
# - topics: from controlled vocabulary only
# - title: properly extracted (not "Untitled")
# - Obsidian file created in ./obsidian_vault/
```

## Current Version Status

**V2.0 Features** (October 2025):
- ✅ Controlled vocabulary enrichment
- ✅ Structure-aware semantic chunking
- ✅ Obsidian V3 RAG-first export with entity stubs
- ✅ Recency scoring, better titles, project auto-matching
- 🔄 Docker testing pending

**Cost Performance**:
- $0.010-0.013 per document
- 70-95% cost savings vs alternatives
- Average query: $0.000017

## Key Files to Know

**Start Here:**
- `START_HERE_TOMORROW.md` - Current status and next steps
- `TESTING_NOW.md` - Testing procedures

**Architecture:**
- `README.md` - Production deployment guide
- `ENRICHMENT_SYSTEM_OVERVIEW.md` - Enrichment pipeline details

**Recent Work:**
- Git log shows recent commits for context
- Check `git log --oneline -5` for latest changes
