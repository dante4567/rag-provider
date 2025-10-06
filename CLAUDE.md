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

## Current Status (Oct 6, 2025 - Week 2 Complete)

**Grade: C+ (74/100)** - Production-ready for small-medium teams

**What Works (79% test coverage):**
- ✅ 11/14 services tested with 179 test functions
- ✅ Core RAG pipeline: enrichment, chunking, vocabulary, vector ops
- ✅ Export systems: Obsidian, OCR, smart triage
- ✅ Multi-LLM fallback chain with cost tracking
- ✅ Docker deployment

**What Needs Work:**
- ⚠️ Dependencies NOT pinned (uses >= not ==) - See DEPENDENCY_STATUS.md
- ⚠️ app.py too large (1,904 lines) - See APP_PY_REFACTORING_NEEDED.md
- ⚠️ 3/14 services untested (reranking, tag_taxonomy, visual_llm)

## Architecture Overview

**Service-Oriented Design** - Clean service layer (Week 1 consolidation):

```
app.py (1,904 lines)           # ⚠️ Monolithic but functional
├── src/services/              # Business logic (11/14 tested)
│   ├── enrichment_service.py          # Controlled vocabulary (19 tests) ✅
│   ├── obsidian_service.py            # RAG-first export (20 tests) ✅
│   ├── chunking_service.py            # Structure-aware (15 tests) ✅
│   ├── vocabulary_service.py          # Controlled tags (13 tests) ✅
│   ├── document_service.py            # 13+ formats (15 tests) ✅
│   ├── llm_service.py                 # Multi-provider (17 tests) ✅
│   ├── vector_service.py              # ChromaDB (8 tests) ✅
│   ├── ocr_service.py                 # OCR processing (14 tests) ✅
│   ├── smart_triage_service.py        # Dedup/categorize (20 tests) ✅
│   ├── reranking_service.py           # Search quality (untested) ⚠️
│   ├── tag_taxonomy_service.py        # Tag learning (untested) ⚠️
│   └── visual_llm_service.py          # Visual analysis (untested) ⚠️
├── src/core/
│   ├── config.py              # Settings management
│   └── dependencies.py        # Dependency injection
├── src/models/
│   └── schemas.py             # Pydantic schemas (duplicated in app.py)
└── tests/unit/                # 179 test functions (79% coverage)
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

# Testing (Week 2: 179 tests, 79% coverage)
docker exec rag_service pytest tests/unit/ -v                      # All 179 unit tests
docker exec rag_service pytest tests/unit/test_llm_service.py -v   # 17 tests
docker exec rag_service pytest tests/unit/test_enrichment_service.py -v  # 19 tests
docker exec rag_service pytest tests/unit/test_obsidian_service.py -v    # 20 tests
docker exec rag_service pytest tests/unit/test_ocr_service.py -v         # 14 tests
docker exec rag_service pytest tests/unit/test_smart_triage_service.py -v  # 20 tests

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
