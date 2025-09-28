# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run local development (requires ChromaDB running separately)
uvicorn app:app --host 0.0.0.0 --port 8001 --reload

# Start ChromaDB locally
docker run -p 8000:8000 chromadb/chroma:latest
```

### Docker Development
```bash
# Start all services
docker-compose up -d

# Build and start with rebuild
docker-compose up -d --build

# View logs
docker-compose logs -f rag-service
docker-compose logs -f chromadb
```

### Testing
```bash
# Run comprehensive test suite
python test_rag_enhanced.py

# Run automated test script
./test_comprehensive_suite.sh

# Run production tests
python production_test.py

# Run Docker integration tests
python docker_integration_test.py

# Health check
curl http://localhost:8001/health
```

### Service Management
```bash
# Check service status
curl http://localhost:8001/health
curl http://localhost:8001/stats

# Reset everything (removes all data)
docker-compose down -v
rm -rf data/obsidian/* data/processed/* volumes/
docker-compose up -d --build
```

## Architecture

This is a production-ready RAG (Retrieval-Augmented Generation) service with the following core architecture:

### Multi-Service Architecture
- **FastAPI App** (port 8001): Main REST API, file processing, LLM routing
- **ChromaDB** (port 8000): Vector storage and similarity search
- **File System**: `/data/*` directories for input, output, and processed files

### Core Components
- **DocumentProcessor** (`app.py:2253 lines`): Handles 8+ document types including WhatsApp, Office docs, PDFs, images, emails
- **LLMService**: Multi-provider LLM management with cost tracking and fallback chains
- **Enhanced Retrieval**: Hybrid dense/sparse search with cross-encoder reranking
- **Document Quality Triage**: Automatic content assessment and OCR quality evaluation

### Multi-LLM Provider System
**Fallback Chain**: Groq (primary) → Anthropic (fallback) → OpenAI (emergency) → Google (long context)

**Supported Providers**:
- **Groq**: llama-3.1-8b-instant, llama3-70b-8192 (fast & cheap)
- **Anthropic**: claude-3-haiku, claude-3-5-sonnet, claude-3-opus (quality)
- **OpenAI**: gpt-4o-mini, gpt-4o (reliable)
- **Google**: gemini-1.5-pro (2M context window)

### Document Processing Pipeline
1. **File Ingestion**: Auto-detection of document types via python-magic
2. **Text Extraction**: Format-specific processors for each document type
3. **OCR Processing**: Tesseract with multi-language support + cloud fallbacks
4. **Chunking & Embedding**: Vector storage in ChromaDB with metadata
5. **Obsidian Generation**: Rich markdown with YAML frontmatter, entities, cross-links

### Data Flow
```
Input Files → Document Processor → Text Extraction → OCR (if needed) →
Chunking → Vector Embedding → ChromaDB Storage → Obsidian Markdown
```

### Directory Structure
- `/data/input/`: Auto-processed files (file watcher monitors this)
- `/data/output/`: Standard markdown output
- `/data/obsidian/`: Obsidian vault files with rich metadata
- `/data/processed/`: Completed/moved files
- `/volumes/chroma_data/`: ChromaDB persistence

## Key Implementation Details

### Document Types Supported
- **WhatsApp**: Chat export parsing with conversation structure
- **Office**: Word (.docx), Excel (.xlsx), PowerPoint (.pptx)
- **PDF**: Text extraction + OCR for scanned documents
- **Images**: PNG, JPEG, TIFF with Tesseract OCR
- **Email**: .eml and .msg files
- **Web**: HTML content processing
- **Text**: Markdown, plain text, code files

### OCR Pipeline
- **Local**: Tesseract with languages: eng, deu, fra, spa
- **Cloud Fallbacks**: Google Vision, Azure Computer Vision, AWS Textract
- **Quality Assessment**: Automatic cloud fallback for poor local OCR results

### API Endpoints
- `/health`: Platform info and service status
- `/ingest`: Text content ingestion
- `/ingest/file`: Single file upload
- `/ingest/batch`: Multiple file processing
- `/search`: Vector search with metadata filtering
- `/chat`: RAG-enhanced chat with context
- `/test-llm`: Model testing and validation
- `/cost-stats`: Usage and budget monitoring

### Cost Management
- **Token Estimation**: Real-time cost calculation per request
- **Budget Enforcement**: Daily limits with automatic cutoffs
- **Usage Tracking**: Per-provider and per-document cost tracking
- **Model Selection**: Task-specific model recommendations

### Environment Configuration
Key environment variables in `.env`:
- **LLM API Keys**: GROQ_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY
- **Processing**: MAX_FILE_SIZE_MB, CHUNK_SIZE, CHUNK_OVERLAP
- **Features**: USE_OCR, ENABLE_FILE_WATCH, CREATE_OBSIDIAN_LINKS
- **Cost Control**: ENABLE_COST_TRACKING, DAILY_BUDGET_USD

### Production Features
- **Cross-platform Docker**: ARM64 + x86_64 support
- **Resource Management**: Memory/CPU limits and optimization
- **Health Monitoring**: Comprehensive status endpoints
- **File Watching**: Automatic processing of new files
- **Non-root Security**: Container runs as unprivileged user

## Important Files
- `app.py`: Main FastAPI application (2,253 lines)
- `enhanced_retrieval.py`: Advanced search and reranking
- `document_quality_triage.py`: Content quality assessment
- `test_rag_enhanced.py`: Comprehensive test suite
- `docker-compose.yml`: Multi-service orchestration
- `requirements.txt`: Python dependencies
- `Dockerfile`: Multi-platform container definition

## Development Notes
- The system is designed for production use with comprehensive error handling
- All document processing is async for performance
- Vector embeddings use ChromaDB's default model (can be configured)
- Obsidian output includes rich metadata: tags, entities, summaries, cross-links
- Cost tracking is built-in with detailed per-request monitoring
- The service handles file watching and auto-processing of new documents