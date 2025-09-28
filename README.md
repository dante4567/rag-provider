# RAG Service

Modern, production-ready RAG service using Unstructured.io + LiteLLM for document processing and multi-LLM support.

## Features

- **Document Processing**: Text, PDF, Office files, WhatsApp exports via Unstructured.io
- **Multi-LLM Support**: Groq, Anthropic, OpenAI, Google via LiteLLM unified interface
- **Vector Search**: ChromaDB for fast similarity search
- **OCR Support**: Tesseract for scanned documents
- **Obsidian Integration**: Rich markdown with metadata generation
- **Docker Ready**: Full containerization with compose

## Quick Start

```bash
# Clone and setup
git clone <repo-url> && cd rag-provider
cp .env.example .env
# Add your API keys to .env

# Start services
docker-compose up -d

# Test
curl http://localhost:8001/health
```

## API Endpoints

```bash
# Upload document
POST /ingest/file

# Search documents
POST /search
{"text": "query", "top_k": 5}

# Chat with RAG
POST /chat
{"question": "What is X?", "llm_model": "groq/llama-3.1-8b-instant"}

# Test LLM providers
POST /test-llm
{"provider": "groq", "prompt": "test"}
```

## Configuration

Add to `.env`:
```bash
GROQ_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

## Architecture

- **FastAPI**: REST API server (port 8001)
- **ChromaDB**: Vector database (port 8000)
- **Unstructured.io**: Document processing
- **LiteLLM**: Unified LLM interface
- **Docker Compose**: Service orchestration

## Supported Models

- **Fast & Cheap**: `groq/llama-3.1-8b-instant`
- **High Quality**: `anthropic/claude-3-haiku-20240307`
- **Reliable**: `openai/gpt-4o-mini`
- **Long Context**: `google/gemini-1.5-pro`

## Testing

```bash
# Run comprehensive tests
docker exec rag_service python comprehensive_validation_suite.py

# Test specific LLM
curl -X POST "http://localhost:8001/test-llm" \
  -H "Content-Type: application/json" \
  -d '{"provider": "groq", "prompt": "Hello"}'
```

## File Structure

```
data/
├── input/     # Drop files here for auto-processing
├── output/    # Processed markdown files
└── obsidian/  # Obsidian vault files

volumes/
└── chroma_data/  # Vector database storage
```

## Production Status

✅ **Working**: Document processing, search, chat, multi-LLM
⚠️ **Needs work**: Image OCR, cost tracking precision
❌ **TODO**: Advanced reranking, monitoring

See `FINAL_NO_BS_ASSESSMENT.md` for detailed production readiness analysis.

## License

MIT