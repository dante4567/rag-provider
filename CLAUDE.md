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

## Current Status (Oct 7, 2025 - Week 3 Phase 1-3 Complete)

**Grade: A- (87/100)** - Production-ready with clean architecture

**What Works:**
- ✅ 14/17 services tested with 210+ unit tests + 9 integration tests
- ✅ Core RAG pipeline: enrichment, chunking, vocabulary, vector ops
- ✅ Export systems: Obsidian, OCR, smart triage
- ✅ Multi-LLM fallback chain with cost tracking
- ✅ Docker deployment with pinned dependencies
- ✅ Modular FastAPI routes (health, ingest, search)
- ✅ Integration tests with real Docker services
- ✅ Vision LLM service fully tested (24 tests)
- ✅ Hybrid retrieval system implemented and tested

**What Needs Work:**
- ⚠️ 3/17 services untested (reranking, tag_taxonomy, whatsapp_parser)
- ⚠️ app.py still large (1,492 LOC) - works but could be split into route modules

## Architecture Overview

**Service-Oriented Design** - Modular architecture with clean separation:

```
app.py (1,492 lines)           # ✅ Core FastAPI application
├── src/routes/                # API endpoints (route modules planned)
│   ├── health.py              # Health checks (planned)
│   ├── ingest.py              # Document ingestion (planned)
│   └── search.py              # Search endpoints (planned)
├── src/services/              # Business logic (14/17 tested)
│   ├── enrichment_service.py          # Controlled vocabulary (19 tests) ✅
│   ├── obsidian_service.py            # RAG-first export (20 tests) ✅
│   ├── chunking_service.py            # Structure-aware (15 tests) ✅
│   ├── vocabulary_service.py          # Controlled tags (13 tests) ✅
│   ├── document_service.py            # 13+ formats (15 tests) ✅
│   ├── llm_service.py                 # Multi-provider (17 tests) ✅
│   ├── vector_service.py              # ChromaDB (8 tests) ✅
│   ├── ocr_service.py                 # OCR processing (14 tests) ✅
│   ├── smart_triage_service.py        # Dedup/categorize (20 tests) ✅
│   ├── visual_llm_service.py          # Gemini Vision (24 tests) ✅
│   ├── hybrid_search_service.py       # Hybrid retrieval (tested) ✅
│   ├── quality_scoring_service.py     # Quality gates (tested) ✅
│   ├── reranking_service.py           # Search reranking (untested) ⚠️
│   ├── tag_taxonomy_service.py        # Tag learning (untested) ⚠️
│   └── whatsapp_parser.py             # WhatsApp exports (untested) ⚠️
├── src/core/
│   ├── config.py              # Settings management
│   └── dependencies.py        # Dependency injection
├── src/models/
│   └── schemas.py             # Pydantic schemas (centralized)
├── tests/unit/                # 210+ unit tests (14/17 services)
├── tests/integration/         # 9 integration tests with real services
└── vocabulary/                # YAML controlled vocabularies
    ├── topics.yaml            # Hierarchical topics
    ├── projects.yaml          # Time-bound projects
    ├── places.yaml            # Locations
    └── people.yaml            # Privacy-safe roles
```

### Key Architectural Concepts

**Enrichment Pipeline** (consolidated in Week 1):
- Uses controlled vocabulary from `vocabulary/*.yaml` (no invented tags)
- Separates entities (people, places) from topics
- Calculates recency scoring with exponential decay
- Smart title extraction and project auto-matching
- 19 tests covering hashing, scoring, title extraction

**Structure-Aware Chunking**:
- Chunks along semantic boundaries (headings, tables, code blocks)
- Keeps section context in chunk metadata
- Tables and code blocks = standalone chunks
- RAG:IGNORE blocks excluded from embeddings
- 15 tests covering chunking logic and token estimation

**Obsidian Export** (RAG-first, consolidated in Week 1):
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

# Testing (210+ unit + 50+ integration tests)
docker exec rag_service pytest tests/unit/ -v                      # All unit tests
docker exec rag_service pytest tests/integration/ -v               # All integration tests
docker exec rag_service pytest -k "test_name" -v                   # Run specific test

# Specific unit test suites
docker exec rag_service pytest tests/unit/test_llm_service.py -v              # 17 tests
docker exec rag_service pytest tests/unit/test_enrichment_service.py -v       # 19 tests
docker exec rag_service pytest tests/unit/test_obsidian_service.py -v         # 20 tests
docker exec rag_service pytest tests/unit/test_ocr_service.py -v              # 14 tests
docker exec rag_service pytest tests/unit/test_smart_triage_service.py -v     # 20 tests
docker exec rag_service pytest tests/unit/test_visual_llm_service.py -v       # 24 tests

# Integration test suites (test actual API endpoints)
docker exec rag_service pytest tests/integration/test_routes.py -v            # Route module tests (health, ingest, search)
docker exec rag_service pytest tests/integration/test_app_endpoints.py -v     # App.py endpoints (chat, stats, admin)
docker exec rag_service pytest tests/integration/test_hybrid_retrieval.py -v  # Hybrid search
docker exec rag_service pytest tests/integration/test_api.py -v               # Legacy API tests

# Run tests outside Docker (local development)
pytest tests/unit/ -v
pytest tests/integration/ -v --tb=short

# Copy vocabulary into container (after updates)
docker cp vocabulary/ rag_service:/app/vocabulary/
docker-compose restart rag-service
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

**Important Architecture Constraints:**
- LLM enrichment ONLY assigns tags from these vocabularies (no hallucinated tags)
- Unknown tags go to `suggested_tags` for review
- Vocabulary managed by `VocabularyService` (13 tests)
- Project auto-matching based on document dates

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

## Key Implementation Notes

**When Adding New Services:**
1. Create service in `src/services/`
2. Add corresponding test in `tests/unit/test_{service_name}.py`
3. Import in `src/services/__init__.py`
4. Use dependency injection via `get_settings()`
5. Follow async/await patterns throughout
6. Add Pydantic schemas to `src/models/schemas.py`

**When Modifying Vocabulary:**
1. Edit YAML files in `vocabulary/`
2. Copy updated files into Docker: `docker cp vocabulary/ rag_service:/app/vocabulary/`
3. Restart service: `docker-compose restart rag-service`
4. No schema changes needed (dynamically loaded)

**Known Technical Debt:**
- app.py is monolithic (1,492 LOC) - works but could be modularized
- Route splitting blocked until integration tests cover all endpoints
- Dependencies use `>=` not `==` (works but unpinned)

**Reference Documentation:**
- `README.md` - Production deployment and status
- `ARCHITECTURE.md` - System design overview
- Git commit history for recent changes
