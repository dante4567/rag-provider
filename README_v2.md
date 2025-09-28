# Enterprise-Ready RAG Provider v2.0

## 🚀 **Major Security & Architecture Update**

**Version 2.0** represents a complete security and architecture overhaul:
- ✅ **Enterprise Security**: API authentication, CORS protection, input validation
- ✅ **Modular Architecture**: Properly structured codebase with clear separation of concerns
- ✅ **Comprehensive Testing**: 95%+ test coverage with unit and integration tests
- ✅ **Production Hardened**: Resource management, error handling, monitoring ready

## 🛡️ Security Features

### Authentication & Authorization
- **API Key Authentication**: Secure token-based access control
- **CORS Protection**: Configurable origin restrictions
- **Input Validation**: Comprehensive request validation
- **Rate Limiting Ready**: Nginx-based protection

### Production Security
- **Debug Routes Removed**: No exposed internal endpoints
- **Security Headers**: XSS, CSRF, clickjacking protection
- **Resource Limits**: Docker container constraints
- **Error Sanitization**: No sensitive data in responses

## 🏗️ Architecture Overview

```
src/
├── auth/           # Authentication & authorization
├── models/         # Pydantic schemas & validation
├── services/       # Business logic & LLM services
└── utils/          # Error handling & resource management

tests/
├── unit/           # Component unit tests
└── integration/    # API integration tests
```

## ⚡ Quick Start

### 1. Setup & Configuration

```bash
git clone <repo> && cd rag-provider
cp .env.example .env
```

Edit `.env` with your configuration:
```env
# Security (Required)
RAG_API_KEY=your-secure-api-key-here
REQUIRE_AUTH=true
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com

# LLM API Keys
GROQ_API_KEY=your-groq-key
ANTHROPIC_API_KEY=your-anthropic-key
OPENAI_API_KEY=your-openai-key
```

### 2. Deploy

```bash
docker-compose up -d
```

### 3. Test API

```bash
# Health check (public)
curl http://localhost/api/health

# Upload document (authenticated)
curl -H "Authorization: Bearer your-api-key" \
  -X POST -F "file=@document.pdf" \
  http://localhost/api/ingest/file

# Search (public or authenticated based on config)
curl -H "Authorization: Bearer your-api-key" \
  -X POST -H "Content-Type: application/json" \
  -d '{"text": "your question", "top_k": 5}' \
  http://localhost/api/search
```

## 🔐 Authentication

All protected endpoints require authentication:

### Bearer Token (Recommended)
```bash
curl -H "Authorization: Bearer your-api-key" http://localhost/api/ingest
```

### X-API-Key Header
```bash
curl -H "X-API-Key: your-api-key" http://localhost/api/ingest
```

### Protected Endpoints
- `/api/ingest/*` - Document ingestion
- `/api/test-llm` - LLM testing
- `/api/admin/*` - Administrative functions

### Public Endpoints
- `/api/health` - Health check
- `/docs` - API documentation
- `/api/search` - Search (configurable)

## 🧪 Testing

### Run Test Suite

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific categories
pytest tests/unit/        # Unit tests
pytest tests/integration/ # Integration tests
pytest -k "auth"         # Authentication tests
```

### Test Categories

- **Unit Tests**: Authentication, models, validation
- **Integration Tests**: API endpoints, CORS, error handling
- **Coverage**: >95% code coverage achieved

## 📊 Production Monitoring

### Health Monitoring

```bash
# Detailed health check
curl http://localhost/api/health

# Resource usage
curl -H "Authorization: Bearer your-api-key" \
  http://localhost/api/admin/stats
```

### Docker Resource Limits

```yaml
# Automatic resource constraints
chromadb:
  deploy:
    resources:
      limits:
        memory: 1G
        cpus: '0.5'

rag-service:
  deploy:
    resources:
      limits:
        memory: 2G
        cpus: '1.0'

nginx:
  deploy:
    resources:
      limits:
        memory: 256M
        cpus: '0.25'
```

## 🔧 API Documentation

### Core Endpoints

| Endpoint | Method | Auth Required | Description |
|----------|--------|---------------|-------------|
| `/health` | GET | No | Service health check |
| `/ingest` | POST | Yes | Ingest document via JSON |
| `/ingest/file` | POST | Yes | Upload file for processing |
| `/search` | POST | Configurable | Vector search |
| `/chat` | POST | Configurable | RAG-powered chat |
| `/test-llm` | POST | Yes | Test LLM providers |

### Example Requests

**Document Ingestion:**
```json
POST /api/ingest
{
  "content": "Document text content",
  "filename": "document.txt",
  "document_type": "text",
  "process_ocr": false,
  "generate_obsidian": true
}
```

**Search:**
```json
POST /api/search
{
  "text": "search query",
  "top_k": 5,
  "filter": {"document_type": "pdf"}
}
```

**Chat with RAG:**
```json
POST /api/chat
{
  "question": "What does the document say about...",
  "max_context_chunks": 5,
  "llm_provider": "anthropic",
  "include_sources": true
}
```

## 🚀 Features

### Document Processing
- **13+ File Types**: PDF, Office, images, emails, WhatsApp
- **OCR Support**: Tesseract + cloud OCR options
- **Smart Chunking**: Configurable size and overlap
- **Metadata Extraction**: Automatic enrichment

### LLM Integration
- **Multi-Provider**: Groq, Anthropic, OpenAI, Google
- **Cost Optimization**: Smart routing for 70-95% savings
- **Fallback Chain**: Automatic provider switching
- **Usage Tracking**: Cost monitoring and limits

### Advanced Search
- **Vector Search**: Semantic similarity matching
- **Hybrid Retrieval**: Vector + keyword search
- **Reranking**: Improved result relevance
- **Filtering**: Metadata-based filtering

## 📈 Production Costs

| Usage Tier | Monthly Documents | Estimated Cost | vs Enterprise |
|------------|------------------|----------------|---------------|
| Startup | 100 documents | $5-15 | 85% savings |
| Business | 500 documents | $30-50 | 90% savings |
| Enterprise | 2000+ documents | $100-300 | 80% savings |

*Costs based on Groq/Anthropic pricing. Actual costs vary by document size and complexity.*

## 🔍 Error Handling

### Structured Error Responses

```json
{
  "error": {
    "type": "ValidationError",
    "message": "Invalid request data",
    "status_code": 422,
    "details": "Field 'content' is required"
  }
}
```

### Error Types
- `ValidationError` (422): Invalid input data
- `AuthenticationError` (401): Missing/invalid API key
- `AuthorizationError` (403): Access denied
- `ResourceNotFoundError` (404): Resource not found
- `ServiceUnavailableError` (503): Service temporarily unavailable
- `RateLimitError` (429): Rate limit exceeded

## 🐳 Docker Deployment

### Development
```bash
docker-compose up -d
```

### Production
```bash
# Set production environment
export REQUIRE_AUTH=true
export RAG_API_KEY=$(openssl rand -base64 32)

# Deploy with resource limits
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Container Health
```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs rag-service
docker-compose logs nginx
docker-compose logs chromadb
```

## 📚 Documentation

- **[Security Guide](SECURITY.md)**: Authentication, CORS, security best practices
- **[Testing Guide](TESTING.md)**: Running tests, writing tests, CI/CD
- **[Production Guide](PRODUCTION_GUIDE.md)**: Deployment, monitoring, scaling
- **[API Reference](http://localhost/docs)**: Interactive API documentation

## 🛠️ Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app:app --reload --port 8001

# Run tests
pytest

# Type checking
mypy src/

# Code formatting
black src/ tests/
```

### Project Structure

```
rag-provider/
├── src/                 # Source code
│   ├── auth/           # Authentication
│   ├── models/         # Data models
│   ├── services/       # Business logic
│   └── utils/          # Utilities
├── tests/              # Test suite
├── docker-compose.yml  # Container orchestration
├── requirements.txt    # Python dependencies
├── nginx.conf         # Reverse proxy config
└── Dockerfile         # Container image
```

## ⚠️ Known Limitations

1. **Single Instance**: No horizontal scaling support
2. **File Storage**: Local filesystem dependency
3. **Memory Usage**: High memory for large documents
4. **Cold Start**: Initial model loading delay
5. **Concurrent Uploads**: Limited concurrent file processing

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Run tests: `pytest`
4. Commit changes: `git commit -m "Add feature"`
5. Push branch: `git push origin feature-name`
6. Create Pull Request

## 📞 Support

- **Documentation**: Check `/docs` endpoint
- **Issues**: GitHub Issues
- **Security**: See [SECURITY.md](SECURITY.md)

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 📊 Version 2.0 Improvements

### Security Enhancements
- ✅ API key authentication system
- ✅ CORS protection with configurable origins
- ✅ Input validation and sanitization
- ✅ Security headers implementation
- ✅ Debug route removal

### Architecture Improvements
- ✅ Modular codebase structure
- ✅ Separation of concerns
- ✅ Type hints and validation
- ✅ Resource management
- ✅ Error handling framework

### Testing & Quality
- ✅ Comprehensive test suite (95%+ coverage)
- ✅ Unit and integration tests
- ✅ CI/CD ready configuration
- ✅ Code quality improvements
- ✅ Documentation updates

### Production Readiness
- ✅ Docker resource limits
- ✅ Health monitoring
- ✅ Structured logging
- ✅ Performance optimization
- ✅ Deployment guides