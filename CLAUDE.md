# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

```bash
# Start the service
docker-compose up -d

# Check health
curl http://localhost:8001/health

# Upload a document
curl -X POST -F "file=@document.pdf" http://localhost:8001/ingest/file

# Search
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"text": "your query", "top_k": 5}'
```

## Architecture

**Clean Service-Oriented Design** (October 2025):
- `app.py` (1,625 lines) - FastAPI application with all endpoints
- `src/services/` - Modular service layer
  - `document_service.py` - Text extraction from 13+ file formats
  - `llm_service.py` - Multi-provider LLM with fallback chain
  - `vector_service.py` - ChromaDB vector operations
  - `ocr_service.py` - OCR processing for images
  - `advanced_enrichment_service.py` - 6-stage multi-LLM pipeline
  - `tag_taxonomy_service.py` - Evolving tag hierarchy
  - `smart_triage_service.py` - Duplicate detection & triage
  - `obsidian_service.py` - Markdown export
- `src/core/` - Configuration and dependency injection
- `src/models/` - Pydantic schemas for validation

## Frontend Interfaces ✅ READY

### 1. Telegram Bot (`telegram-bot/`)
```bash
export TELEGRAM_BOT_TOKEN="your_token_from_botfather"
cd telegram-bot && python rag_bot.py
```
Features: Document upload, search, chat, stats

### 2. Web GUI (`web-ui/`) - Gradio Interface
```bash
cd web-ui && python app.py
# Open: http://localhost:7860
```
Features: Upload, search, chat, statistics dashboard

### 3. OpenWebUI Function (Optional)
Create `openwebui/rag_function.py` - single file to drop into OpenWebUI

## Development Commands

```bash
# Docker operations
docker-compose up --build -d  # Start/rebuild
docker-compose logs -f        # View logs
docker-compose down           # Stop

# Testing
docker exec rag_service pytest tests/unit/test_vector_service.py -v  # 100% passing
docker exec rag_service pytest tests/ -v  # All 47 tests

# Add documents
curl -X POST -F "file=@doc.pdf" http://localhost:8001/ingest/file
```

## Environment Configuration

Required in `.env`:
```bash
GROQ_API_KEY=gsk_...
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PORT=8001
CHROMA_HOST=localhost
CHROMA_PORT=8000
```

## Current State: B+ (83/100)

### What Works ✅
- Multi-stage enrichment (6 stages, all working)
- 100% document processing success (validated with 6 diverse docs)
- Tag learning: 62.3% reuse on similar docs, 38.3% on diverse
- Duplicate detection: 100% accuracy
- Obsidian export: 100% success rate
- API enrichment: All metadata fields working
- Cost tracking: $0.010-0.013 per document (validated)
- Frontends: Telegram bot + Web UI ready

### Needs Scale Testing ⚠️
- Tag learning with 100+ documents across domains
- Performance with large PDFs (50+ pages)
- Memory stability after processing many files
- Concurrent upload handling
- SmartNotes compatibility (45/100)

## Using the Frontends

### Start Web UI (Recommended)
```bash
cd web-ui
pip install -r requirements.txt
python app.py
# Open: http://localhost:7860
```

### Start Telegram Bot
```bash
# Get token from @BotFather on Telegram first
export TELEGRAM_BOT_TOKEN="your_token"
cd telegram-bot
pip install -r requirements.txt
python rag_bot.py
```

### Testing Strategy
1. Upload 10 documents via Web UI
2. Check tag learning (aim for 60%+ reuse on similar docs)
3. Test duplicate detection (upload same file twice)
4. Monitor costs in Statistics tab
5. Test search and chat features

## Key Documentation

- **FRONTENDS_ADDED.md** - Latest status update and testing guide
- **REAL_WORLD_TEST_RESULTS.md** - Validation results with real documents
- **DEPLOYMENT_COMPLETE.md** - Initial deployment assessment
- **BRUTAL_HONEST_ASSESSMENT_V2.md** - Honest system evaluation
- **ENRICHMENT_SYSTEM_OVERVIEW.md** - Architecture details
- **ADD_FRONTENDS_GUIDE.md** - Frontend implementation guide

## Recent Changes (October 5, 2025)

### API Response Fix ✅
- Added 13 enrichment metadata fields to API response
- Now returns: domain, significance_score, quality_tier, entity_richness, content_depth, extraction_confidence
- Also: people_count, organizations_count, concepts_count, triage_category, triage_confidence, is_duplicate, is_actionable

### Frontends Added ✅
- Telegram bot for mobile document upload
- Gradio web UI for desktop testing
- Both ready for immediate use

### Real-World Testing ✅
- Validated with 6 diverse documents
- Confirmed tag learning works (38.3% reuse across diverse types)
- Confirmed duplicate detection (100% accuracy)
- Confirmed cost tracking ($0.010-0.013/doc)
