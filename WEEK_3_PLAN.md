# Week 3 Plan: Pin Deps + Integration Tests + Refactoring

**Goal:** C+ (74/100) → A- (85/100)
**Timeline:** 1-2 weeks
**Status:** STARTING

## Phase 1: Pin Dependencies (2 hours) ✅ NEXT

**Target Grade:** C+ → B (76/100)

**Steps:**
1. Stop OpenWebUI containers (port 8000/8001 conflicts)
2. Start RAG service containers
3. Run `pip freeze` inside Docker
4. Create `requirements-pinned.txt`
5. Test with pinned versions
6. Update Dockerfile to use pinned requirements

**Blockers:** Disk space at 100%
**Workaround:** Minimal file writes, small commits

## Phase 2: Real Integration Tests (3-5 days)

**Target Grade:** B → B+ (80/100)

**Minimum Tests Needed:**
1. `/health` - Real service health check
2. `/ingest/file` - Full document processing pipeline
3. `/search` - Real vector search (not mocked)
4. `/chat` - LLM interaction end-to-end
5. Cost tracking validation

**Files to Create:**
- `tests/integration/test_real_ingestion.py`
- `tests/integration/test_real_search.py`
- `tests/conftest.py` updates (real ChromaDB fixture)

## Phase 3: Refactor app.py (3 days)

**Target Grade:** B+ → A- (85/100)

**Phase 3a: Remove Duplicate Schemas (LOW RISK)**
- Import from `src/models/schemas.py`
- Delete duplicate definitions from app.py
- Reduces ~400 lines
- Run all tests after

**Phase 3b: Split Routes (MEDIUM RISK - after integration tests pass)**
- Create `src/routes/` directory
- Move routes to modules:
  - `health.py` - /health, /stats
  - `ingest.py` - /ingest, /ingest/file, /ingest/batch
  - `search.py` - /search, /documents
  - `chat.py` - /chat
  - `admin.py` - /admin/*
- Update app.py to include routers
- Run integration tests after each module

**Phase 3c: Extract Service Init (MEDIUM RISK)**
- Create `src/core/app_factory.py`
- Move service initialization
- Keep app.py focused on routing

## Success Criteria

**After Phase 1 (Pin Deps):**
- ✅ requirements-pinned.txt exists
- ✅ All tests still pass
- ✅ Docker build works
- ✅ Reproducible builds guaranteed

**After Phase 2 (Integration Tests):**
- ✅ At least 5 real integration tests
- ✅ Test actual ChromaDB storage/retrieval
- ✅ Test real document processing end-to-end
- ✅ Can safely refactor knowing tests will catch breaks

**After Phase 3 (Refactor):**
- ✅ app.py under 500 lines
- ✅ No duplicate schemas
- ✅ Routes in separate modules
- ✅ All tests still passing

## Estimated Timeline

- **Phase 1:** 2 hours (today)
- **Phase 2:** 3-5 days (this week)
- **Phase 3:** 3 days (next week)
- **Total:** 1-2 weeks to A- grade

## Risk Mitigation

1. **Commit after each small change**
2. **Run tests after every modification**
3. **Keep old files until new ones validated**
4. **Document any issues found honestly**

Let's go! Starting with Phase 1: Pin Dependencies.
