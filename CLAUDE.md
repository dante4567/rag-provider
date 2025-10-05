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
- `src/core/` - Configuration and dependency injection
- `src/models/` - Pydantic schemas for validation

## Frontend Interfaces (To Be Added)

### 1. Telegram Bot
Copy `telegram-bot/rag_bot.py` from ai-ecosystem-integrated repo or create new one that connects to http://localhost:8001

### 2. Simple Web GUI (Recommended: Gradio)
Create `web-ui/app.py` with Gradio interface for:
- Document upload
- Search
- Chat with documents
- Cost dashboard

### 3. OpenWebUI Function
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

## Current State: A- (88/100)

### What Works 
- Multi-stage enrichment (Groq + Claude)
- 92% document processing success
- Vector search with ChromaDB
- 4 LLM providers working
- 90% cost savings proven

### Needs Work  
- Triage service not integrated (6 hours)
- Tag learning needs 50+ doc validation
- Claude pricing broken ($0.00)
- Obsidian export disabled
- No frontends yet

## Adding Frontends

### Telegram Bot (1-2 hours)
1. Copy `ai-telegram-bots/rag_bot.py` from ecosystem repo
2. Update RAG_SERVICE_URL to http://localhost:8001
3. Install: `pip install python-telegram-bot aiohttp`
4. Run: `python telegram-bot/rag_bot.py`

### Web GUI (4-6 hours)
1. Create `web-ui/requirements.txt` with gradio
2. Create `web-ui/app.py` with Gradio interface
3. Run: `gradio web-ui/app.py`

### OpenWebUI (2-3 hours)
1. Create `openwebui/rag_function.py`
2. Copy search/chat logic from ai-ecosystem-integrated
3. Drop file into OpenWebUI functions directory
