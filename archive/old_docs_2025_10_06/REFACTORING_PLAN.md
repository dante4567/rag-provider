# Refactoring Plan: app.py → Clean Architecture

**Goal**: Transform 2305-line monolith into maintainable, testable, extensible architecture
**Timeline**: 1-2 weeks incremental work
**Strategy**: Pragmatic hybrid - keep working while refactoring

---

## Strategy: Parallel Development (Recommended)

**Keep `app.py` working while building new architecture**

```
Current:
app.py (2305 lines, monolithic) → Works but unmaintainable

Target:
app.py (<200 lines, routes only)
├── src/
│   ├── models/      - Pydantic schemas
│   ├── services/    - Business logic
│   ├── repositories/ - Data access
│   ├── utils/       - Helpers
│   └── core/        - Config, deps
```

---

## Phase 1: Foundation (Day 1-2)

### Step 1.1: Create Core Configuration Module

**File**: `src/core/config.py`

```python
"""
Centralized configuration management
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List
import os

class Settings(BaseSettings):
    """Application settings with validation"""

    # App
    app_name: str = "RAG Provider"
    version: str = "2.1.0"
    debug: bool = False

    # Security
    rag_api_key: str = ""
    require_auth: bool = True
    allowed_origins: List[str] = ["http://localhost:3000"]

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    collection_name: str = "documents"

    # Processing
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_file_size_mb: int = 50

    # LLM
    default_llm: str = "groq"
    fallback_llm: str = "anthropic"
    emergency_llm: str = "openai"
    llm_temperature: float = 0.7
    llm_max_retries: int = 3

    # API Keys
    groq_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    # OCR
    use_ocr: bool = True
    ocr_provider: str = "tesseract"
    ocr_languages: str = "eng,deu,fra,spa"

    # Paths
    input_path: str = "/data/input"
    output_path: str = "/data/output"
    processed_path: str = "/data/processed"
    obsidian_path: str = "/data/obsidian"

    # Features
    enable_file_watch: bool = True
    create_obsidian_links: bool = True
    enable_cost_tracking: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
```

### Step 1.2: Create Dependency Injection Module

**File**: `src/core/dependencies.py`

```python
"""
FastAPI dependency injection
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Generator
import chromadb
from chromadb.config import Settings as ChromaSettings
from src.core.config import Settings, get_settings

# Security
security = HTTPBearer(auto_error=False)

# Public endpoints
PUBLIC_ENDPOINTS = {"/health", "/docs", "/redoc", "/openapi.json"}


async def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings)
) -> bool:
    """Verify API token"""
    if not settings.require_auth:
        return True

    if request.url.path in PUBLIC_ENDPOINTS:
        return True

    token = None
    if credentials:
        token = credentials.credentials
    else:
        token = request.headers.get("X-API-Key") or request.query_params.get("api_key")

    if not settings.rag_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication required but no API key configured"
        )

    if not token or token != settings.rag_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True


def get_chroma_client(settings: Settings = Depends(get_settings)) -> chromadb.Client:
    """Get ChromaDB client"""
    return chromadb.HttpClient(
        host=settings.chroma_host,
        port=settings.chroma_port,
        settings=ChromaSettings(anonymized_telemetry=False)
    )


def get_collection(client: chromadb.Client = Depends(get_chroma_client), settings: Settings = Depends(get_settings)):
    """Get or create ChromaDB collection"""
    return client.get_or_create_collection(
        name=settings.collection_name,
        metadata={"description": "RAG document embeddings"}
    )
```

---

## Phase 2: Extract Models (Day 2-3)

### Step 2.1: Consolidate Pydantic Models

**File**: `src/models/schemas.py` (REPLACE existing)

**Extract from app.py lines 199-355**:
- All Enum classes
- All Pydantic BaseModel classes
- Move to single file
- Add proper docstrings

**Then in app.py**:
```python
# REPLACE lines 199-355 with:
from src.models.schemas import (
    DocumentType, LLMProvider, LLMModel, ComplexityLevel,
    Keywords, Entities, ObsidianMetadata, Document,
    IngestResponse, SearchResult, SearchResponse,
    DocumentInfo, Stats, Query, ChatRequest, ChatResponse,
    CostInfo, CostStats, EnrichmentSettings
)
```

---

## Phase 3: Extract Services (Day 3-7)

### Step 3.1: Create Document Service

**File**: `src/services/document_service.py`

**Responsibilities**:
- File upload handling
- Document extraction (PDF, Office, etc.)
- Text splitting/chunking
- OCR processing
- Obsidian markdown generation

**Extract from app.py**:
- All document processing logic (lines ~600-1200)
- OCR functions
- File validation
- Format detection

**Interface**:
```python
class DocumentService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.text_splitter = SimpleTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap
        )

    async def process_file(self, file: UploadFile) -> Dict[str, Any]:
        """Process uploaded file and extract content"""
        pass

    async def extract_text(self, file_path: Path, file_type: str) -> str:
        """Extract text from various file formats"""
        pass

    async def chunk_text(self, text: str) -> List[str]:
        """Split text into chunks"""
        pass

    def generate_obsidian_markdown(self, metadata: Dict) -> str:
        """Generate Obsidian-formatted markdown"""
        pass
```

### Step 3.2: Create LLM Service

**File**: `src/services/llm_service.py`

**Responsibilities**:
- LLM provider selection & fallback
- API calls to Groq/Anthropic/OpenAI/Google
- Cost tracking
- Error handling & retries

**Extract from app.py**:
- LLM call logic (lines ~1300-1500)
- Cost tracking class
- Model pricing data
- Retry logic

**Interface**:
```python
class LLMService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cost_tracker = CostTracker()

    async def call_llm(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """Call LLM with fallback logic"""
        pass

    async def enrich_document(self, text: str) -> Dict[str, Any]:
        """Generate metadata using LLM"""
        pass

    def estimate_cost(self, model: str, tokens: int) -> float:
        """Estimate cost for LLM call"""
        pass
```

### Step 3.3: Create Vector Service

**File**: `src/services/vector_service.py`

**Responsibilities**:
- ChromaDB operations
- Embedding generation
- Vector search
- Document storage/retrieval

**Extract from app.py**:
- ChromaDB interaction logic
- Embedding logic
- Search logic

**Interface**:
```python
class VectorService:
    def __init__(self, collection, settings: Settings):
        self.collection = collection
        self.settings = settings

    async def add_document(
        self,
        doc_id: str,
        chunks: List[str],
        metadata: Dict[str, Any]
    ) -> None:
        """Add document chunks to vector store"""
        pass

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter: Optional[Dict] = None
    ) -> List[Dict]:
        """Search vector store"""
        pass

    async def delete_document(self, doc_id: str) -> bool:
        """Delete document from vector store"""
        pass

    async def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        pass
```

### Step 3.4: Create Enrichment Service

**File**: `src/services/enrichment_service.py`

**Responsibilities**:
- Extract entities (people, orgs, places)
- Generate summaries
- Extract keywords
- Classify documents

**Extract from app.py**:
- Enrichment logic (if exists)
- Entity extraction
- Classification

---

## Phase 4: Extract Repositories (Day 7-8)

### Step 4.1: File Repository

**File**: `src/repositories/file_repository.py`

**Responsibilities**:
- File system operations
- File watching
- Path management

### Step 4.2: Vector Repository

**File**: `src/repositories/vector_repository.py`

**Responsibilities**:
- Direct ChromaDB access
- Query building
- Result parsing

---

## Phase 5: Refactor app.py (Day 8-10)

### Target Structure

**New `app.py`** (~150-200 lines):

```python
"""
RAG Provider API - Main Application
"""
from fastapi import FastAPI, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.core.config import get_settings
from src.core.dependencies import verify_token, get_collection
from src.models.schemas import *
from src.services.document_service import DocumentService
from src.services.llm_service import LLMService
from src.services.vector_service import VectorService
from src.utils.error_handlers import setup_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    print("🚀 RAG Provider starting...")
    yield
    # Shutdown
    print("👋 RAG Provider shutting down...")


app = FastAPI(
    title="RAG Provider",
    version="2.1.0",
    description="Clean architecture RAG service",
    lifespan=lifespan
)

# Setup
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)
setup_error_handlers(app)


# Routes
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": settings.version}


@app.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    collection = Depends(get_collection),
    _: bool = Depends(verify_token)
):
    """Ingest document from file upload"""
    # Initialize services
    doc_service = DocumentService(settings)
    vector_service = VectorService(collection, settings)
    llm_service = LLMService(settings)

    # Process file
    result = await doc_service.process_file(file)

    # Add to vector store
    await vector_service.add_document(
        doc_id=result['id'],
        chunks=result['chunks'],
        metadata=result['metadata']
    )

    # Enrich with LLM
    enrichment = await llm_service.enrich_document(result['text'])

    return IngestResponse(**result)


@app.post("/search", response_model=SearchResponse)
async def search_documents(
    query: Query,
    collection = Depends(get_collection),
    settings: Settings = Depends(get_settings)
):
    """Search documents"""
    vector_service = VectorService(collection, settings)
    results = await vector_service.search(query.text, top_k=query.top_k)

    return SearchResponse(
        results=results,
        query=query.text,
        total_results=len(results)
    )


# ... more routes (each 5-15 lines max)
```

---

## Phase 6: Testing (Day 10-12)

### Create Real Tests

**File**: `tests/services/test_document_service.py`
**File**: `tests/services/test_llm_service.py`
**File**: `tests/services/test_vector_service.py`
**File**: `tests/integration/test_full_workflow.py`

**Test actual code paths**, not fake modules!

---

## Phase 7: Migration (Day 12-14)

### Migration Checklist

- [ ] All services created and tested
- [ ] All repositories created and tested
- [ ] All models moved to src/models
- [ ] app.py refactored to <250 lines
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Docker still works
- [ ] All endpoints functional
- [ ] No functionality lost

### Rollback Plan

Keep `app_legacy.py` as backup:
```bash
cp app.py app_legacy.py
# Refactor app.py
# If issues: cp app_legacy.py app.py
```

---

## Success Criteria

### Code Quality
- [ ] app.py < 250 lines
- [ ] No code duplication
- [ ] Clear separation of concerns
- [ ] Proper dependency injection
- [ ] Type hints everywhere

### Testing
- [ ] 70%+ test coverage on services
- [ ] All business logic tested
- [ ] Integration tests pass
- [ ] E2E workflow tested

### Documentation
- [ ] Architecture diagram
- [ ] API documentation
- [ ] Service documentation
- [ ] Migration guide

### Functionality
- [ ] All 16 endpoints work
- [ ] Docker compose works
- [ ] File processing works
- [ ] LLM integration works
- [ ] Vector search works
- [ ] No regressions

---

## Implementation Order

**Week 1**:
1. ✅ Day 1: Foundation (config, dependencies)
2. ✅ Day 2: Models extraction
3. ✅ Day 3-4: Document service
4. ✅ Day 5-6: LLM service
5. ✅ Day 7: Vector service

**Week 2**:
6. ✅ Day 8-9: Repositories
7. ✅ Day 10: Refactor app.py
8. ✅ Day 11-12: Testing
9. ✅ Day 13: Documentation
10. ✅ Day 14: Final validation & deployment

---

## Next Step

**Start with Phase 1: Foundation**

Create:
1. `src/core/config.py`
2. `src/core/dependencies.py`

These are the building blocks everything else depends on.

Ready to proceed?
