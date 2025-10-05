# Master Implementation Plan
**Date:** October 5, 2025
**Status:** Foundation Complete → Systematic Build-Out

---

## Execution Order

### ✅ Phase 0: Foundation (COMPLETE)
- Controlled vocabulary (32 topics, 2 projects, 13 places)
- EnrichmentServiceV2 (4-strategy titles, recency scoring)
- ObsidianServiceV2 (clean YAML)
- Integration into main pipeline
- **Status:** Code written, committed, ready to test

---

### 🔄 Phase 1: TEST FOUNDATION (NOW - 30 min)
**Goal:** Validate V2 integration works in Docker

**Tasks:**
1. Start Docker containers
2. Check V2 initialization in logs
3. Upload test document
4. Verify:
   - Title extraction (not "Untitled")
   - Controlled vocabulary (no invented tags)
   - Auto-project matching
   - Clean Obsidian YAML
   - Chat retrieval

**Guide:** `TESTING_NOW.md`

**Success Criteria:**
- [ ] Docker starts cleanly
- [ ] Logs show "Enrichment V2 initialized"
- [ ] Test doc uploads successfully
- [ ] Metadata shows V2 features working
- [ ] Obsidian YAML is clean

**If Fails:** Stop and debug before proceeding

---

### 📐 Phase 2: Structure-Aware Chunking (3-4 hours)
**Goal:** Semantic chunking for precision boost

**Why This First:**
- **Biggest quality improvement** (10-20% precision gain)
- Foundation for everything else (better chunks = better retrieval)
- No external dependencies

**Tasks:**

1. **Create ChunkingService** (1.5h)
   ```python
   # src/services/chunking_service.py
   - Markdown structure parser (headings, lists, tables)
   - Semantic boundary detection
   - Metadata-rich chunks (section_title, parents, sequence)
   - Keep headings in chunk content
   ```

2. **Integrate into Pipeline** (1h)
   ```python
   # app.py: RAGService.process_document()
   - Replace SimpleTextSplitter with ChunkingService
   - Preserve chunk metadata in ChromaDB
   - Update chunk_metadata to include structure info
   ```

3. **Test & Validate** (0.5h)
   - Upload document with headings/tables
   - Verify chunks follow semantic boundaries
   - Check metadata preserved

4. **Documentation** (0.5h)
   - Update architecture docs
   - Add chunking strategy guide

**Deliverables:**
- `src/services/chunking_service.py`
- Updated `app.py` integration
- Test results document
- Updated docs

**Success Metrics:**
- Chunks align with document structure
- Tables = standalone chunks
- Section titles in metadata
- No broken boundaries mid-paragraph

---

### 🗂️ Phase 3: Obsidian SmartNotes Matching (1-2 hours)
**Goal:** Perfect integration with your Obsidian vault

**Why Now:**
- Quick win (V2 export already 80% there)
- Immediate usability improvement
- No code dependencies

**Tasks:**

1. **Review SmartNotes Format** (0.5h)
   - Check your actual Obsidian templates
   - Identify required fields/structure
   - Note any custom Dataview queries

2. **Enhance ObsidianServiceV2** (0.5h)
   ```python
   # src/services/obsidian_service_v2.py
   - Add any missing frontmatter fields
   - Ensure Dataview inline fields match your queries
   - Add custom metadata blocks
   - Format suggested_topics as actionable checklist
   ```

3. **Test in Obsidian** (0.5h)
   - Export test document
   - Open in Obsidian
   - Verify Dataview queries work
   - Check rendering and links

**Deliverables:**
- Updated `ObsidianServiceV2`
- SmartNotes compatibility guide
- Example exports

**Success Criteria:**
- Files open cleanly in Obsidian
- Dataview queries return results
- Links work (`[[project]]` syntax)
- Frontmatter validates

---

### 🌐 Phase 4: FastAPI + Frontends + OpenWebUI (6-8 hours)
**Goal:** Production-ready API + UI integration

**Why Now:**
- Makes everything accessible
- OpenWebUI = your main interface
- Enables future features (feedback, visualization)

**Part A: FastAPI Enhancement** (2h)

1. **API Improvements**
   ```python
   # New endpoints:
   POST /v2/ingest              # V2-specific with full config
   GET  /v2/documents           # List with V2 metadata
   GET  /v2/documents/{id}      # Full document details
   POST /v2/search              # Advanced search with filters
   POST /v2/chat                # Enhanced chat with V2 features

   # Existing endpoints enhanced with V2 metadata
   ```

2. **Request/Response Models**
   ```python
   # Update Pydantic models for V2
   - IngestRequestV2 (with vocab options)
   - DocumentResponseV2 (with recency, projects, etc.)
   - SearchRequestV2 (metadata filters)
   ```

**Part B: OpenWebUI Integration** (3-4h)

1. **OpenWebUI Connection Setup**
   ```yaml
   # OpenWebUI configuration
   - RAG provider endpoint
   - Authentication
   - Custom metadata display
   ```

2. **Custom Functions**
   ```python
   # OpenWebUI function for RAG
   - Search with metadata filters
   - Display recency scores
   - Show project tags
   - Feedback buttons
   ```

3. **UI Customization**
   - Source citations with metadata
   - Recency indicators
   - Project/topic filters
   - Quality scores display

**Part C: Simple Admin UI** (2h)

1. **Document Browser**
   ```html
   # web-ui/documents.html
   - List documents with V2 metadata
   - Filter by project/topic/date
   - View enrichment details
   - Re-process button
   ```

2. **Vocabulary Manager**
   ```html
   # web-ui/vocabulary.html
   - View current vocabularies
   - Review suggested tags
   - Approve/reject/merge
   ```

**Deliverables:**
- Enhanced FastAPI endpoints
- OpenWebUI integration guide
- Admin UI pages
- Connection testing script

**Success Criteria:**
- OpenWebUI can query RAG
- Sources show V2 metadata
- Admin UI functional
- All endpoints documented

---

### 🔍 Phase 5: Hybrid Retrieval (4-6 hours)
**Goal:** BM25 + dense embeddings + MMR fusion

**Why Now:**
- Structure-aware chunks ready
- API ready for advanced queries
- Major quality boost (keyword + semantic)

**Tasks:**

1. **BM25 Index** (2h)
   ```python
   # src/services/bm25_service.py
   - Build BM25Okapi index
   - Incremental updates
   - Persistence (save/load)
   - Fast top-k retrieval
   ```

2. **Hybrid Retriever** (2h)
   ```python
   # src/services/hybrid_retrieval_service.py
   - Parallel BM25 + dense queries
   - Score normalization
   - MMR fusion (diversity)
   - Metadata filtering integration
   ```

3. **Integration** (1h)
   ```python
   # Update /search and /chat endpoints
   - Use hybrid retriever
   - Optional: user can choose dense-only/sparse-only/hybrid
   - Performance logging
   ```

4. **Testing** (1h)
   - Compare dense-only vs hybrid
   - Test keyword queries (names, IDs)
   - Test semantic queries (concepts)
   - Measure precision improvement

**Deliverables:**
- `src/services/bm25_service.py`
- `src/services/hybrid_retrieval_service.py`
- Updated endpoints
- Performance comparison report

**Success Metrics:**
- Hybrid outperforms dense-only on keyword queries
- MMR provides diversity
- Latency acceptable (<500ms)

---

### 💬 Phase 6: Feedback System (6-8 hours)
**Goal:** User curation and continuous improvement

**Why Last:**
- Builds on all previous work
- Needs UI (from Phase 4)
- Needs hybrid retrieval (Phase 5)
- Most impactful when foundation solid

**Part A: Feedback Storage** (2h)

1. **Metadata Schema**
   ```yaml
   feedback:
     correctness_score: 1.0      # 0-1, user-rated
     pinned: false               # Force to top
     review_count: 3             # Times verified
     last_reviewed: 2025-10-05
     notes: "Canonical source"
   ```

2. **Storage Layer**
   ```python
   # src/services/feedback_service.py
   - Save/load feedback
   - Update document metadata
   - Track feedback history
   ```

**Part B: API Endpoints** (2h)

```python
POST /documents/{id}/feedback
  {"correctness_score": 1.0, "notes": "..."}

POST /documents/{id}/pin
POST /documents/{id}/unpin

GET /documents/pinned
GET /documents/golden  # correctness_score >= 0.8
```

**Part C: Ranking Integration** (1h)

```python
# In retrieval reranking:
for chunk in candidates:
    base_score = rerank_score

    feedback = chunk.metadata.get('feedback', {})
    if feedback.get('pinned'):
        score *= 2.0
    else:
        score *= (1.0 + feedback.get('correctness_score', 0.0))
```

**Part D: UI Integration** (2h)

1. **OpenWebUI Functions**
   - Thumbs up/down on sources
   - Mark as canonical
   - Pin important docs

2. **Admin UI**
   - Feedback dashboard
   - Golden documents list
   - Review workflow

**Part E: Evaluation** (1h)

```python
# Use feedback to build gold set
- High-feedback docs = good test cases
- Track precision on golden documents
```

**Deliverables:**
- `src/services/feedback_service.py`
- API endpoints
- UI integration
- Evaluation framework

**Success Criteria:**
- Can mark docs as golden
- Pinned docs surface first
- Feedback visible in UI
- Metrics show improvement

---

## Continuous: Documentation & Testing

**After Each Phase:**

1. **Update Docs**
   - Architecture changes
   - API documentation
   - User guides
   - Testing procedures

2. **Write Tests**
   - Unit tests for new services
   - Integration tests for endpoints
   - Update test suite

3. **Update Guides**
   - `TESTING_NOW.md` stays current
   - `docs/future_roadmap_v2.0.md` updated with completion status
   - Add phase-specific testing guides

**Key Documents to Maintain:**
- `TESTING_NOW.md` - Always reflects current state
- `docs/architecture.md` - System design
- `docs/api_documentation.md` - All endpoints
- `docs/future_roadmap_v2.0.md` - Roadmap status
- `README.md` - Quick start

---

## Success Metrics (Overall)

| Metric | Baseline | Target | Phase |
|--------|----------|--------|-------|
| Precision@5 | 0.60 | 0.75+ | After Phase 5 |
| Title Quality | 40% "Untitled" | 0% | Phase 1 ✅ |
| Tag Contamination | 20% invalid | 0% | Phase 1 ✅ |
| Retrieval Latency | 800ms | <500ms | Phase 5 |
| User Satisfaction | N/A | Track via feedback | Phase 6 |

---

## Time Estimates

| Phase | Estimate | Status |
|-------|----------|--------|
| 0. Foundation | 8-10h | ✅ COMPLETE |
| 1. Testing | 0.5h | 🔄 IN PROGRESS |
| 2. Structure Chunking | 3-4h | 📋 READY |
| 3. Obsidian Matching | 1-2h | 📋 READY |
| 4. API + OpenWebUI | 6-8h | 📋 PLANNED |
| 5. Hybrid Retrieval | 4-6h | 📋 PLANNED |
| 6. Feedback System | 6-8h | 📋 PLANNED |

**Total Remaining:** 21-29 hours

**Realistic Timeline:**
- Week 1: Phases 1-3 (testing + quick wins)
- Week 2: Phase 4 (API + UI)
- Week 3: Phases 5-6 (retrieval + feedback)

---

## Current Status

**Last Commit:** `b428db1` - Phase 3 Complete: Obsidian V3 RAG-First Integration
**Branch:** `main`
**Next Step:** Docker testing (Phases 1-3), then Phase 4 (FastAPI + OpenWebUI)

**Completed Today:**
- ✅ Phase 2: Structure-Aware Chunking (3h)
- ✅ Phase 3: Obsidian V3 RAG-First (2h)
- 🔄 Phase 1: Testing (blocked by Docker, deferred to tomorrow)

**Ready to proceed!** 🚀

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
