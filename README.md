# Enhanced RAG Service

A comprehensive, cross-platform RAG (Retrieval Augmented Generation) service that handles diverse document types, multiple LLM providers, OCR processing, and generates Obsidian-optimized markdown with rich metadata.

## 🚀 Features

### 📄 **Document Processing**
- **WhatsApp Chat Exports** - Parse and structure conversation data
- **Office Documents** - Word (.docx), Excel (.xlsx), PowerPoint (.pptx)
- **Scanned Documents** - PDF and TIFF with OCR processing
- **Images** - PNG, JPEG, TIFF with text extraction
- **Text Files** - Markdown, plain text, code files
- **Email Files** - .eml and .msg format support
- **Web Content** - HTML pages and archives

### 🤖 **Multi-LLM Support**
- **Primary**: Groq (Mixtral-8x7B) - Fast & cost-effective
- **Fallback**: Anthropic Claude - High quality analysis
- **Emergency**: OpenAI GPT - Reliable backup
- **Google Gemini** - Long context processing
- **Smart Routing** - Task-specific model selection
- **Cost Tracking** - Monitor usage per document

### 🔍 **OCR Capabilities**
- **Local Tesseract** - Multiple language support
- **Scanned PDFs** - Automatic text extraction
- **Multi-page TIFF** - Batch processing
- **Image Analysis** - Text detection and extraction

### 📝 **Obsidian Integration**
- **Rich Metadata** - Hierarchical keywords, entities, summaries
- **YAML Frontmatter** - Complete document metadata
- **Wiki Links** - Auto-generated cross-references
- **Tags** - Organized topic categorization
- **Vault Ready** - Direct import to Obsidian

### 🌐 **Cross-Platform**
- **Docker-first** - Identical behavior on Linux, macOS, Windows
- **Multi-architecture** - ARM64 and x86_64 support
- **Platform Detection** - Automatic path configuration
- **Resource Management** - Optimized for containers

## 🏗️ **Architecture**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI App   │────│   ChromaDB       │    │   File System   │
│   (Port 8001)   │    │   (Port 8000)    │    │   (/data/*)     │
│                 │    │                  │    │                 │
│ • REST API      │    │ • Vector Storage │    │ • Input Files   │
│ • File Watcher  │    │ • Embeddings     │    │ • Obsidian MD   │
│ • LLM Router    │    │ • Search         │    │ • Processed     │
│ • OCR Engine    │    │ • Metadata       │    │ • Temp Files    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            │                    │                    │
   ┌─────────────┐    ┌─────────────────┐    ┌─────────────┐
   │    Groq     │    │   Anthropic     │    │   OpenAI    │
   │  (Primary)  │    │  (Fallback)     │    │ (Emergency) │
   └─────────────┘    └─────────────────┘    └─────────────┘
```

## 🚦 **Quick Start**

### 1. **Prerequisites**
- Docker and Docker Compose
- At least one LLM API key (Groq recommended)

### 2. **Installation**
```bash
# Clone repository
git clone <repository-url>
cd rag-provider

# Copy environment template
cp .env.example .env

# Edit with your API keys
nano .env
```

### 3. **Configuration**
Add your API keys to `.env`:
```bash
# Primary LLM (recommended)
GROQ_API_KEY=gsk_your_groq_api_key_here

# Fallback LLMs
ANTHROPIC_API_KEY=sk-ant-your_anthropic_key_here
OPENAI_API_KEY=sk-your_openai_key_here
```

### 4. **Launch Services**
```bash
# Start all services
docker-compose up -d

# Check service health
curl http://localhost:8001/health

# View logs
docker-compose logs -f rag-service
```

### 5. **Test Installation**
```bash
# Run comprehensive test suite
python test_rag_enhanced.py

# Or quick health check
curl -X GET "http://localhost:8001/health"
```

## 📊 **API Reference**

### **Health & Status**
```http
GET /health
# Returns platform info, LLM status, OCR availability

GET /stats
# Returns usage statistics and provider status
```

### **Document Ingestion**
```http
POST /ingest
Content-Type: application/json
{
  "content": "Document text...",
  "filename": "document.txt",
  "document_type": "text|pdf|whatsapp|office|scanned",
  "process_ocr": true,
  "generate_obsidian": true
}

POST /ingest/file
Content-Type: multipart/form-data
# Single file upload with OCR options

POST /ingest/batch
Content-Type: multipart/form-data
# Multiple file upload processing
```

### **Search & Retrieval**
```http
POST /search
Content-Type: application/json
{
  "text": "search query",
  "top_k": 5,
  "filter": {
    "document_type": "whatsapp",
    "tags": ["#ai", "#machine-learning"]
  }
}
```

### **Document Management**
```http
GET /documents
# List all documents with metadata

DELETE /documents/{doc_id}
# Delete document and associated files
```

### **LLM Testing**
```http
POST /test-llm
{
  "provider": "groq|anthropic|openai",
  "prompt": "Test prompt"
}
```

## 🔧 **Configuration Options**

### **LLM Providers**
```bash
# Provider priority (fallback chain)
DEFAULT_LLM=groq           # Primary choice
FALLBACK_LLM=anthropic     # Secondary
EMERGENCY_LLM=openai       # Final fallback

# Model parameters
LLM_TEMPERATURE=0.7        # Creativity level
LLM_MAX_RETRIES=3         # Retry attempts
```

### **Document Processing**
```bash
# File handling
MAX_FILE_SIZE_MB=50       # Maximum upload size
CHUNK_SIZE=1000           # Text chunk size
CHUNK_OVERLAP=200         # Chunk overlap

# File monitoring
ENABLE_FILE_WATCH=true    # Auto-process new files
WATCH_FOLDER=/data/input  # Watch directory
```

### **OCR Configuration**
```bash
# OCR settings
USE_OCR=true                    # Enable OCR processing
OCR_PROVIDER=tesseract          # OCR engine
OCR_LANGUAGES=eng,deu,fra,spa   # Language support
```

### **Obsidian Integration**
```bash
# Output settings
OBSIDIAN_VAULT_PATH=/data/obsidian  # Vault location
CREATE_OBSIDIAN_LINKS=true          # Generate [[links]]
HIERARCHY_DEPTH=3                   # Keyword levels
```

## 📁 **File Structure**

```
rag-provider/
├── app.py                    # Main FastAPI application
├── requirements.txt          # Python dependencies
├── Dockerfile               # Multi-platform container
├── docker-compose.yml       # Service orchestration
├── .env.example             # Environment template
├── setup.sh                 # Quick setup script
├── test_rag_enhanced.py     # Comprehensive test suite
├── openwebui_function.py    # OpenWebUI integration
├── README.md                # This documentation
├── data/                    # Data directories
│   ├── input/              # Auto-processed files
│   ├── output/             # Standard markdown
│   ├── obsidian/           # Obsidian vault files
│   └── processed/          # Completed files
└── volumes/                 # Docker volumes
    └── chroma_data/        # ChromaDB persistence
```

## 🎯 **Usage Examples**

### **WhatsApp Chat Processing**
```bash
# Upload WhatsApp export
curl -X POST "http://localhost:8001/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "1/20/24, 10:30 - John: How is the ML project?\n1/20/24, 10:31 - Jane: Going well!",
    "filename": "team_chat.txt",
    "document_type": "whatsapp",
    "generate_obsidian": true
  }'
```

### **OCR Document Processing**
```bash
# Process scanned document with OCR
curl -X POST "http://localhost:8001/ingest/file" \
  -F "file=@scanned_document.pdf" \
  -F "process_ocr=true" \
  -F "generate_obsidian=true"
```

### **Batch Processing**
```bash
# Upload multiple files
curl -X POST "http://localhost:8001/ingest/batch" \
  -F "files=@document1.pdf" \
  -F "files=@document2.docx" \
  -F "files=@chat_export.txt" \
  -F "generate_obsidian=true"
```

### **Advanced Search**
```bash
# Search with metadata filtering
curl -X POST "http://localhost:8001/search" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "machine learning algorithms",
    "top_k": 10,
    "filter": {
      "document_type": "text",
      "complexity": "advanced"
    }
  }'
```

## 📋 **Obsidian Markdown Format**

Generated markdown files include comprehensive metadata:

```yaml
---
title: "Document Title"
id: "unique-document-id"
created: "2024-01-20T10:30:00"
tags: ["#ai", "#machine-learning", "#research"]
type: "research_paper"
source: "uploaded_file.pdf"
summary: "Brief document summary..."
abstract: "Detailed abstract paragraph..."
keywords:
  primary: ["Machine Learning", "Neural Networks"]
  secondary: ["Deep Learning", "Optimization"]
  related: ["AI", "Data Science"]
entities:
  people: ["John Smith", "Jane Doe"]
  organizations: ["OpenAI", "Google"]
  locations: ["San Francisco", "New York"]
  technologies: ["Python", "TensorFlow"]
complexity: "advanced"
reading_time: "15 minutes"
links: ["[[Related Document]]", "[[Another Topic]]"]
---

# Document Title

## Summary
Brief executive summary...

## Key Insights
- Important point 1
- Important point 2

## Entities
**People:** [[John Smith]], [[Jane Doe]]
**Organizations:** [[OpenAI]], [[Google]]

## Content
[Original document content...]

## Related Notes
- [[Related Document]]
- [[Another Topic]]

## Tags
#ai #machine-learning #research
```

## 🔗 **OpenWebUI Integration**

Add this function to OpenWebUI for knowledge base search:

```python
def search_knowledge_base(query: str, top_k: int = 5) -> str:
    """Search RAG knowledge base for relevant information"""
    import requests

    try:
        response = requests.post(
            "http://localhost:8001/search",
            json={"text": query, "top_k": top_k},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()

            context = f"📚 Found {len(data['results'])} results:\\n\\n"

            for i, result in enumerate(data['results'], 1):
                relevance = result['relevance_score']
                content = result['content'][:500] + "..."
                filename = result['metadata'].get('filename', 'Unknown')

                context += f"**Result {i}** (Relevance: {relevance:.2f})\\n"
                context += f"{content}\\n"
                context += f"*Source: {filename}*\\n\\n"

            return context
        else:
            return f"Search failed: HTTP {response.status_code}"

    except Exception as e:
        return f"Error: {str(e)}"
```

## 🧪 **Testing**

### **Basic Tests**
```bash
# Health check
curl http://localhost:8001/health

# Simple document ingestion
curl -X POST "http://localhost:8001/ingest" \
  -H "Content-Type: application/json" \
  -d '{"content": "Test document", "filename": "test.txt"}'
```

### **Comprehensive Test Suite**
```bash
# Run all enhanced tests
python test_rag_enhanced.py

# Test specific features
python -c "
from test_rag_enhanced import EnhancedRAGTester
tester = EnhancedRAGTester()
tester.test_whatsapp_processing()
tester.test_ocr_processing()
"
```

### **Performance Testing**
```bash
# Batch processing test
python -c "
import requests
import time

start = time.time()
# Upload multiple files...
end = time.time()
print(f'Processing time: {end - start:.2f}s')
"
```

## 🛠️ **Development**

### **Local Development**
```bash
# Install dependencies
pip install -r requirements.txt

# Start ChromaDB separately
docker run -p 8000:8000 chromadb/chroma:latest

# Set environment variables
export GROQ_API_KEY=your_key
export CHROMA_HOST=localhost

# Run development server
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

### **Adding New Document Types**
Extend the `DocumentProcessor.extract_text_from_file` method:

```python
async def extract_text_from_file(self, file_path: str) -> tuple[str, DocumentType]:
    # Add new format detection
    if file_extension == ".your_format":
        text = await self._process_your_format(file_path)
        return text, DocumentType.your_type
```

### **Custom LLM Integration**
Add providers to the `LLM_PROVIDERS` configuration:

```python
LLM_PROVIDERS["your_provider"] = {
    "api_key": YOUR_API_KEY,
    "model": "your-model-name",
    "max_tokens": 4000,
    "client_class": YourLLMClient
}
```

## 📊 **Monitoring**

### **Service Health**
```bash
# Health status
curl http://localhost:8001/health

# System statistics
curl http://localhost:8001/stats

# ChromaDB status
curl http://localhost:8000/api/v1/heartbeat
```

### **Logs**
```bash
# Service logs
docker-compose logs -f rag-service

# ChromaDB logs
docker-compose logs -f chromadb

# All services
docker-compose logs -f
```

### **Resource Usage**
```bash
# Container stats
docker stats rag_service rag_chromadb

# Disk usage
docker system df

# Volume inspection
docker volume inspect rag-provider_chroma_data
```

## 🚨 **Troubleshooting**

### **Common Issues**

**Service won't start:**
```bash
# Check API keys
grep -E "GROQ_API_KEY|ANTHROPIC_API_KEY" .env

# Verify ChromaDB
curl http://localhost:8000/api/v1/heartbeat

# Check logs
docker-compose logs rag-service
```

**OCR not working:**
```bash
# Check OCR dependencies in container
docker exec rag_service tesseract --version

# Test OCR manually
docker exec rag_service python -c "import pytesseract; print('OCR available')"
```

**No search results:**
```bash
# Verify documents were ingested
curl http://localhost:8001/documents

# Check ChromaDB connection
curl http://localhost:8000/api/v1/collections
```

**LLM failures:**
```bash
# Test each provider
curl -X POST "http://localhost:8001/test-llm" \
  -H "Content-Type: application/json" \
  -d '{"provider": "groq", "prompt": "test"}'
```

### **Reset Everything**
```bash
# Stop and remove all data
docker-compose down -v

# Clean up
rm -rf data/obsidian/* data/processed/* volumes/

# Restart fresh
docker-compose up -d --build
```

## 📈 **Performance Optimization**

### **Resource Allocation**
```yaml
# docker-compose.yml - Resource limits
deploy:
  resources:
    limits:
      memory: 4G
      cpus: '2.0'
    reservations:
      memory: 2G
      cpus: '1.0'
```

### **Concurrent Processing**
```bash
# Increase worker processes
uvicorn app:app --workers 4 --host 0.0.0.0 --port 8001
```

### **Caching**
```python
# Enable LLM response caching
CACHE_LLM_RESPONSES=true
CACHE_TTL_SECONDS=3600
```

## 📜 **License**

MIT License - see LICENSE file for details.

## 🤝 **Contributing**

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📞 **Support**

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Documentation**: This README and inline code comments
- **Examples**: See `test_rag_enhanced.py` for usage examples

---

**Built with ❤️ for the AI community**