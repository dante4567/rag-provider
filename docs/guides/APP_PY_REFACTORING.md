# app.py Refactoring Guide

## Current Status

**app.py:** 1,535 lines (too large, contains business logic)

**Structure:**
- Lines 1-572: Imports, utilities, helper classes
- Lines 573-1234: RAGService class (661 lines) ← Extract this
- Lines 1235+: FastAPI app initialization

**Goal:** Reduce app.py to ~400 lines (FastAPI setup only)

## Why Refactor?

**Current Issues:**
- ❌ app.py has business logic (should only have routing)
- ❌ Circular import: dependencies.py imports from app.py
- ❌ Hard to test RAGService in isolation
- ❌ 1,535 lines is too large for maintainability

**After Refactoring:**
- ✅ Clean separation: app.py = routing, services = logic
- ✅ No circular imports
- ✅ RAGService testable in isolation
- ✅ app.py < 400 lines

## Refactoring Plan

### Step 1: Create src/services/rag_service.py

Extract these classes from app.py:
```python
# Move to src/services/rag_service.py
- SimpleTextSplitter (lines 114-154)
- CostTracker (lines 472-555)
- FileWatchHandler (lines 557-570)
- RAGService (lines 573-1234)
```

### Step 2: Update Dependencies

**File: `src/core/dependencies.py`**

Change line 211:
```python
# OLD:
from app import RAGService

# NEW:
from src.services.rag_service import RAGService
```

### Step 3: Update app.py

**File: `app.py`**

Replace RAGService definition with import:
```python
# Add to imports section
from src.services.rag_service import RAGService, FileWatchHandler

# Remove lines 114-154 (SimpleTextSplitter) - move to rag_service.py
# Remove lines 472-555 (CostTracker) - move to rag_service.py
# Remove lines 557-570 (FileWatchHandler) - move to rag_service.py
# Remove lines 573-1234 (RAGService) - move to rag_service.py

# Keep line 1236 (initialization)
rag_service = RAGService()
```

### Step 4: Handle Global Variables

RAGService needs access to:
- `collection` (ChromaDB collection)
- `chroma_client` (ChromaDB client)

**Solution:** Pass as constructor parameters:
```python
# In rag_service.py
class RAGService:
    def __init__(self, chroma_host=None, chroma_port=None):
        self.chroma_host = chroma_host or os.getenv("CHROMA_HOST", "localhost")
        self.chroma_port = int(chroma_port or os.getenv("CHROMA_PORT", "8000"))
        self.setup_chromadb()
        # ... rest of initialization
```

## Implementation Steps

### 1. Create the New File

```bash
touch src/services/rag_service.py
```

### 2. Copy Required Imports

**To src/services/rag_service.py:**
```python
"""
RAG Service - Document processing orchestration

This service coordinates all document processing operations including:
- LLM enrichment and metadata extraction
- Structure-aware chunking
- Vector embedding and storage
- Obsidian export
- Quality scoring and triage
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid
import hashlib
import logging
import os
from datetime import datetime

from watchdog.events import FileSystemEventHandler
import chromadb

from src.core.config import get_settings
from src.models.schemas import IngestResponse, SearchResult, DocumentType

# All the service imports that RAGService uses
from src.services import (
    DocumentService,
    LLMService,
    VectorService,
    OCRService
)
from src.services.enrichment_service import EnrichmentService
from src.services.vocabulary_service import VocabularyService
from src.services.chunking_service import ChunkingService
from src.services.obsidian_service import ObsidianService
# ... etc
```

### 3. Copy Classes to New File

Copy from app.py to rag_service.py:
1. SimpleTextSplitter class
2. CostTracker class
3. FileWatchHandler class
4. RAGService class

### 4. Update Imports in app.py

```python
from src.services.rag_service import RAGService, FileWatchHandler

# Remove old class definitions
# Keep only initialization:
rag_service = RAGService()
```

### 5. Test

```bash
# Test imports work
python -c "from src.services.rag_service import RAGService; print('✅ Imports work')"

# Run unit tests
pytest tests/unit/ -v

# Start the service
docker-compose up -d

# Test an endpoint
curl http://localhost:8001/health
```

## Expected Results

### Before:
```
app.py (1,535 lines)
├── Imports (112 lines)
├── SimpleTextSplitter (40 lines)
├── Logging setup (50 lines)
├── Config (100 lines)
├── CostTracker (83 lines)
├── FileWatchHandler (13 lines)
├── RAGService (661 lines) ← 43% of the file!
└── FastAPI setup (476 lines)
```

### After:
```
app.py (~400 lines)
├── Imports (120 lines)
├── Logging setup (50 lines)
├── Config (100 lines)
└── FastAPI setup (130 lines)

src/services/rag_service.py (~800 lines)
├── Imports (50 lines)
├── SimpleTextSplitter (40 lines)
├── CostTracker (83 lines)
├── FileWatchHandler (13 lines)
└── RAGService (661 lines)
```

## Testing Checklist

After refactoring, verify:

```bash
# 1. Imports work
python -c "from src.services.rag_service import RAGService"

# 2. Service starts
docker-compose up -d

# 3. Health check
curl http://localhost:8001/health

# 4. Document ingestion
curl -X POST http://localhost:8001/ingest \
  -H "Content-Type: application/json" \
  -d '{"content": "test", "filename": "test.txt"}'

# 5. Unit tests pass
pytest tests/unit/ -v

# 6. Integration tests pass
pytest tests/integration/test_smoke.py -v
```

## Common Issues & Solutions

### Issue 1: Circular Import

**Error:** `ImportError: cannot import name 'RAGService' from partially initialized module 'app'`

**Solution:** Import RAGService from `src.services.rag_service` instead of `app`

### Issue 2: Global Variables

**Error:** `NameError: name 'collection' is not defined`

**Solution:** Pass globals as constructor parameters or use dependency injection

### Issue 3: Missing Imports

**Error:** `ImportError: No module named 'X'`

**Solution:** Ensure all imports from app.py are copied to rag_service.py

## Benefits After Refactoring

✅ **Cleaner Architecture**
- app.py focuses on FastAPI setup
- Services contain business logic
- Clear separation of concerns

✅ **Better Testability**
- Test RAGService without starting FastAPI
- Mock dependencies easily
- Isolated unit tests

✅ **Improved Maintainability**
- Smaller files (app.py: 1,535 → 400 lines)
- Easier to navigate codebase
- Clear module boundaries

✅ **No Circular Imports**
- dependencies.py imports from services
- app.py imports from services
- Clean dependency graph

## Timeline

**Estimated Time:** 1-2 hours

- Step 1-2: Create file and copy classes (30 min)
- Step 3-4: Update imports and app.py (30 min)
- Step 5: Testing and debugging (30-60 min)

## Alternative: Keep Current Structure

If you prefer NOT to refactor now:

**Pros of keeping current structure:**
- ✅ Everything works as-is
- ✅ No risk of breaking changes
- ✅ Zero time investment

**Cons:**
- ❌ app.py remains large (1,535 lines)
- ❌ Circular import pattern continues
- ❌ Harder to test in isolation

**Recommendation:** Current structure is production-ready. Refactoring is a nice-to-have for long-term maintainability, not a requirement.
