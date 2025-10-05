# RAG Pipeline V2.0 - Complete Roadmap & Vision

**Date:** October 5, 2025
**Current Status:** Foundation Complete (40-50% of Vision)
**Sources:** User inputs + personal_rag_pipeline_full.md

---

## Vision Summary

Build a **high-signal, low-noise** personal RAG system that:
- Indexes only valuable content (aggressive quality gating)
- Provides accurate, cited answers (hybrid retrieval + reranking)
- Improves over time (user feedback loop)
- Connects knowledge (graph relationships)
- Manages information lifecycle (decay awareness)

---

## Current State vs. Vision

### ✅ Foundation Complete (What You Have Now)

**1. Controlled Vocabulary System**
```yaml
# Implemented: 32 topics, 2 projects, 13 places, role-based people
topics: [school/admin, kita/handover, legal/custody, ...]
projects: [school-2026, custody-2025]
places: [Essen, Köln, ...]
people_roles: [Principal, Teacher, ...]  # Privacy-safe
```
- ✅ Vocabulary loading and validation
- ✅ Auto-suggestion of closest matches
- ✅ Suggested tags workflow (track frequency, auto-promote)
- ✅ Project auto-matching via watchlists

**2. Smart Enrichment**
```yaml
# Implemented: Title extraction, basic scoring
title: "Florianschule Enrollment Information"  # 4-strategy extraction
quality_score: 0.94      # OCR quality + completeness
recency_score: 0.98      # Exponential decay from created_at
enrichment_version: "2.0"
```
- ✅ 4-strategy title extraction (no more "Untitled")
- ✅ Recency scoring (exponential decay)
- ✅ Quality scoring (OCR + completeness)
- ✅ Clean metadata structure

**3. Clean Obsidian Export**
- ✅ Proper YAML formatting (PyYAML)
- ✅ Clean enum handling (pdf not DocumentType.pdf)
- ✅ Dataview inline fields
- ✅ Suggested topics as checklist

**4. Retrieval & Reranking**
- ✅ Cross-encoder reranking (ms-marco-MiniLM-L-12-v2)
- ✅ 30→10 retrieval boosting
- ⚠️ Only dense embeddings (BM25 not yet integrated)

---

## 📋 Phase 1: Advanced Scoring System (NOT YET IMPLEMENTED)

**Goal:** Smart quality gating - only index high-signal content

### Missing Components

**1. Novelty Detection**
```yaml
novelty_score: 0.72  # New info vs. your corpus
```
**How:** TF-IDF or cosine similarity against existing documents
**Why:** Prevents duplicate/redundant content from polluting index
**Effort:** 2-3 hours

**2. Actionability Scoring**
```yaml
actionability_score: 0.80  # Hits watchlist? Leads to decisions?
```
**How:** Check if document matches active projects, people, or time windows
**Why:** Prioritize personally relevant content
**Effort:** 1-2 hours

**3. Composite Signalness**
```python
signalness = (0.4 * quality) + (0.3 * novelty) +
             (0.3 * actionability) + (0.1 * recency)
```
**Effort:** 1 hour

**4. Quality Gates (Per Document Type)**
```python
GATES = {
    "email.thread":      {"min_quality": 0.70, "min_signal": 0.60},
    "pdf.report":        {"min_quality": 0.75, "min_signal": 0.65},
    "web.article":       {"min_quality": 0.70, "min_signal": 0.60},
}

do_index = (signalness >= GATES[doc_type]["min_signal"])
```
**Why:** Keep index small and high-quality
**Effort:** 2 hours

### Implementation Files
- `src/services/scoring_service.py` - Novelty + actionability
- `src/services/enrichment_service_v2.py` - Update to use gates
- `vocabulary/gates.yaml` - Per-type thresholds

**Total Effort:** 6-8 hours

---

## 📋 Phase 2: User Feedback System (NOT YET IMPLEMENTED)

**Goal:** Human-in-the-loop curation - teach the system what's valuable

### Missing Components

**1. Feedback Metadata**
```yaml
feedback:
  correctness_score: 1.0           # User marks as "golden" (0-1)
  last_reviewed_by_user: 2025-10-05
  pinned: false                    # Force into top results
  notes: "Definitive schedule confirmation"
  review_count: 3                  # Times user verified
```
**Effort:** 1 hour (metadata structure)

**2. Feedback API Endpoints**
```python
POST /documents/{doc_id}/feedback
{
  "correctness_score": 1.0,
  "notes": "This is the canonical version"
}

POST /documents/{doc_id}/pin
POST /documents/{doc_id}/unpin
```
**Effort:** 2-3 hours

**3. Feedback-Boosted Ranking**
```python
# In retrieval reranking:
for chunk in candidates:
    base_score = cross_encoder.score(query, chunk)

    # Apply feedback boost
    feedback = chunk.metadata.get('feedback', {})
    correctness = feedback.get('correctness_score', 0.0)
    is_pinned = feedback.get('pinned', False)

    # Massive boost for user-verified content
    if is_pinned:
        final_score = base_score * 2.0
    else:
        final_score = base_score * (1.0 + correctness)
```
**Why:** Golden documents surface immediately
**Effort:** 2-3 hours

**4. Feedback UI/CLI**
```bash
# CLI example
rag feedback mark-golden <doc_id> --score 1.0
rag feedback pin <doc_id>
rag feedback list-golden

# Web UI: Thumbs up/down on sources in chat responses
```
**Effort:** 3-4 hours (CLI) or 8-12 hours (web UI)

### Implementation Files
- `src/api/feedback_routes.py` - API endpoints
- `src/services/feedback_service.py` - Business logic
- `src/services/reranking_service.py` - Update to apply boosts
- `cli/feedback_commands.py` - CLI interface

**Total Effort:** 8-12 hours (CLI) or 14-20 hours (with UI)

---

## 📋 Phase 3: Graph Relationships (NOT YET IMPLEMENTED)

**Goal:** Connect related documents for richer context

### Missing Components

**1. Relationship Metadata**
```yaml
related_docs:
  - id: 2025-09-28_note_planning-session_a4f1
    type: references
    context: "Mentioned in discussion"
  - id: 2025-10-01_email_followup_b3c2
    type: thread
    context: "Part of same conversation"
```
**Effort:** 1-2 hours (metadata structure)

**2. Relationship Extraction**
```python
def extract_relationships(doc, existing_docs):
    """
    Find related documents by:
    - Shared project tags
    - Date proximity (±7 days)
    - Explicit mentions of other doc titles
    - People/organization overlap
    - Thread/conversation chains
    """
    related = []

    # Same project + similar dates
    for other_doc in existing_docs:
        if overlap(doc.projects, other_doc.projects):
            if days_apart(doc.created_at, other_doc.created_at) <= 7:
                related.append(other_doc.id)

    # Title mentions (e.g., "As discussed in...")
    for title in extract_title_mentions(doc.content):
        matching_doc = find_by_title(title, existing_docs)
        if matching_doc:
            related.append(matching_doc.id)

    return related
```
**Effort:** 4-6 hours

**3. Graph Expansion in Retrieval**
```python
# After initial retrieval + reranking:
top_chunks = reranked[:10]

# Expand via graph
expanded_chunks = []
for chunk in top_chunks:
    expanded_chunks.append(chunk)

    # Fetch chunks from related documents
    related_doc_ids = chunk.metadata.get('related_docs', [])
    for related_id in related_doc_ids[:2]:  # Limit expansion
        related_chunks = get_chunks_for_doc(related_id, limit=2)
        expanded_chunks.extend(related_chunks)

# Re-rank expanded set
final_chunks = rerank(query, expanded_chunks)[:10]
```
**Why:** Automatic context expansion (e.g., email thread → planning note)
**Effort:** 3-4 hours

**4. Graph Visualization (Optional)**
```python
# Generate graph.json for visualization
{
  "nodes": [
    {"id": "doc_1", "label": "School Info Day", "type": "email"},
    {"id": "doc_2", "label": "Planning Notes", "type": "note"}
  ],
  "edges": [
    {"source": "doc_1", "target": "doc_2", "type": "references"}
  ]
}
```
**Effort:** 4-6 hours (if using existing graph viz library)

### Implementation Files
- `src/services/graph_service.py` - Relationship extraction & management
- `src/services/enrichment_service_v2.py` - Add relationship extraction
- `src/services/retrieval_service.py` - Graph expansion logic
- `web-ui/graph_viz.html` - Optional visualization

**Total Effort:** 12-18 hours

---

## 📋 Phase 4: Hybrid Retrieval (PARTIAL)

**Current:** Only dense embeddings (ChromaDB)
**Goal:** BM25 + dense + metadata filters

### Missing Components

**1. BM25 Index**
```python
from rank_bm25 import BM25Okapi

# Build sparse index
corpus_tokens = [doc.split() for doc in corpus]
bm25 = BM25Okapi(corpus_tokens)

# Query
query_tokens = query.split()
bm25_scores = bm25.get_scores(query_tokens)
```
**Effort:** 2-3 hours

**2. Hybrid Fusion**
```python
def retrieve_hybrid(query, top_k=20):
    # Sparse retrieval
    bm25_candidates = bm25.topk(query, k=50)

    # Dense retrieval
    dense_candidates = chroma.search(query, k=50)

    # MMR fusion (diversity + relevance)
    fused = mmr_union(
        bm25_candidates,
        dense_candidates,
        k=top_k,
        lambda_diversity=0.5
    )

    return fused
```
**Why:** BM25 great for names/IDs, embeddings for concepts
**Effort:** 3-4 hours

**3. Metadata Filtering**
```python
# Already partially working via ChromaDB where clauses
# Enhance with:
filters = {
    "projects": ["school-2026"],
    "date_range": ("2025-09-01", "2025-12-31"),
    "people": ["Principal"],
    "min_quality_score": 0.75
}
```
**Effort:** 1-2 hours (already mostly done)

### Implementation Files
- `src/services/bm25_service.py` - Sparse index
- `src/services/retrieval_service.py` - Hybrid fusion
- Update `/search` and `/chat` endpoints

**Total Effort:** 6-9 hours

---

## 📋 Phase 5: Structure-Aware Chunking (NOT IMPLEMENTED)

**Current:** Simple text splitter (fixed size, basic overlap)
**Goal:** Semantic boundaries (headings, sections, tables)

### Missing Components

**1. Structure Detection**
```python
def detect_structure(markdown_content):
    """
    Parse Markdown structure:
    - H1/H2/H3 headings
    - List blocks (bullet/numbered)
    - Tables
    - Code blocks
    - Paragraphs
    """
    from markdown_it import MarkdownIt

    md = MarkdownIt()
    tokens = md.parse(markdown_content)

    sections = []
    for token in tokens:
        if token.type == 'heading_open':
            sections.append({
                'type': 'heading',
                'level': int(token.tag[1]),
                'content': ...
            })
        elif token.type == 'table_open':
            sections.append({
                'type': 'table',
                'content': ...
            })

    return sections
```
**Effort:** 4-6 hours

**2. Smart Chunking**
```python
def chunk_by_structure(sections, target_size=512):
    """
    Create chunks along semantic boundaries:
    - Each H2 section = potential chunk
    - Tables = standalone chunks
    - Combine small sections to reach target_size
    - Add metadata: section_title, parents, sequence
    """
    chunks = []

    for section in sections:
        if section['type'] == 'table':
            # Tables always separate
            chunks.append({
                'content': section['content'],
                'metadata': {
                    'chunk_type': 'table',
                    'section_title': section.get('title'),
                    'parent_sections': section.get('parents', [])
                }
            })
        elif section['type'] == 'heading':
            # Combine with content until target_size
            chunk_content = build_chunk(section, target_size)
            chunks.append({
                'content': chunk_content,
                'metadata': {
                    'chunk_type': 'section',
                    'section_title': section['title'],
                    'heading_level': section['level']
                }
            })

    return chunks
```
**Why:** Huge precision boost - chunks have semantic coherence
**Effort:** 6-8 hours

### Implementation Files
- `src/services/chunking_service.py` - New service
- `src/services/document_service.py` - Replace simple splitter
- Update metadata schema to include `section_title`, `chunk_type`

**Total Effort:** 10-14 hours

---

## 📋 Phase 6: Advanced Document Processing (PARTIAL)

### Per-Document-Type Pipelines

**1. Email Threading** (NOT IMPLEMENTED)
```python
# Current: Each email separate
# Goal: 1 MD per thread with message array

{
  "id": "2025-10-05_thread_kita-handover_7c1a",
  "messages": [
    {"from": "Mother", "date": "2025-10-02", "content": "..."},
    {"from": "Daniel", "date": "2025-10-02", "content": "..."}
  ]
}
```
**Effort:** 6-8 hours

**2. WhatsApp Daily Bundles** (NOT IMPLEMENTED)
```yaml
# Goal: 1 MD per day with timeline
id: 2025-10-05_whatsapp-daily_xyz
timeline:
  - time: "07:30"
    sender: "Mother"
    content: "Morning pickup at 8?"
  - time: "07:45"
    sender: "Daniel"
    content: "Yes, confirmed"
```
**Effort:** 4-6 hours

**3. Document Intelligence for Tables/Forms** (PARTIAL)
```python
# Current: Basic OCR
# Goal: Cloud fallback for complex documents

if ocr_confidence < 0.65 or table_count > 0:
    # Escalate to Google Document AI / Azure Form Recognizer
    structured_data = doc_ai.parse(pdf_path)
    # Returns: tables as CSV, forms as key-value pairs
```
**Effort:** 8-12 hours (cloud integration)

**Total Effort:** 18-26 hours

---

## 📋 Phase 7: Evaluation & Observability (NOT IMPLEMENTED)

**Goal:** Continuous improvement with metrics

### Missing Components

**1. Gold Test Set**
```yaml
# 50_eval_gold/queries.yaml
- query: "wann sind informationsabende"
  expected_docs: ["2025-10-05_school-info_abc"]
  expected_answer_contains: ["2. Oktober 2025", "Florianschule"]

- query: "who do I contact about enrollment"
  expected_docs: ["2025-09-15_contact-list_xyz"]
  expected_answer_contains: ["enrollment@florianschule"]
```
**Effort:** 2-3 hours (initial set)

**2. Nightly Metrics**
```python
def evaluate_gold_set():
    results = {
        "precision@5": [],
        "any_good_citation": [],
        "median_latency_ms": []
    }

    for test_case in gold_set:
        retrieved = search(test_case.query, top_k=5)

        # Precision: % of expected docs in top-5
        precision = len(set(retrieved) & set(test_case.expected_docs)) / 5
        results["precision@5"].append(precision)

        # Answer quality
        answer = chat(test_case.query)
        has_good_citation = any(
            expected in answer.sources
            for expected in test_case.expected_docs
        )
        results["any_good_citation"].append(has_good_citation)

    return {k: mean(v) for k, v in results.items()}
```
**Effort:** 4-6 hours

**3. Bad Answers Inbox**
```python
# Every time user flags answer as bad:
POST /feedback/bad-answer
{
  "query": "...",
  "answer": "...",
  "sources": [...],
  "reason": "Missing key information"
}

# → Automatically added to gold set for regression testing
```
**Effort:** 2-3 hours

**4. Simple Dashboard**
```
Last 7 Days:
  Precision@5: 0.78 (↑ 0.05)
  Good Citations: 0.82 (↓ 0.03)
  Avg Latency: 450ms

Index Health:
  Total Docs: 105
  Avg Quality: 0.87
  Pending Re-OCR: 3
  Duplicates Removed: 12
```
**Effort:** 6-8 hours (simple CLI dashboard) or 12-16 hours (web dashboard)

### Implementation Files
- `50_eval_gold/` - Gold set queries
- `src/services/evaluation_service.py` - Metrics calculation
- `scripts/nightly_eval.py` - Scheduled evaluation
- `web-ui/dashboard.html` - Optional web dashboard

**Total Effort:** 14-20 hours

---

## 📋 Phase 8: Lifecycle Management (NOT IMPLEMENTED)

**Goal:** Manage knowledge decay and vocabulary evolution

### Missing Components

**1. Vocabulary Lifecycle**
```python
# Review suggested tags quarterly
def review_suggested_tags():
    """
    Group suggested_tags by frequency
    Present for user decision:
    - Approve → add to vocabulary/topics.yaml
    - Reject → blacklist
    - Merge → combine with existing tag
    """
    suggestions = db.query("""
        SELECT suggested_topic, COUNT(*) as freq
        FROM enriched_metadata
        WHERE suggested_topic IS NOT NULL
        GROUP BY suggested_topic
        ORDER BY freq DESC
    """)

    for tag, freq in suggestions:
        if freq >= 5:  # Auto-promotion threshold
            print(f"Auto-promote '{tag}' (used {freq} times)")
            add_to_vocabulary(tag)
```
**Effort:** 3-4 hours

**2. Knowledge Decay Management**
```python
# Quarterly review of old docs
def review_stale_docs():
    """
    Find docs where recency_score < 0.3
    User decides:
    - Archive (remove from index)
    - Update (re-enrich with new date)
    - Keep (still relevant despite age)
    """
    stale = db.query("""
        SELECT id, title, recency_score, created_at
        FROM documents
        WHERE recency_score < 0.3
        ORDER BY recency_score ASC
    """)

    for doc in stale:
        action = prompt_user(f"Archive {doc.title}? (archive/update/keep)")
        if action == "archive":
            remove_from_index(doc.id)
            move_to_archive(doc.id)
```
**Effort:** 2-3 hours

**3. Archival System**
```
/rag/
  20_archived_not_indexed/
    by-year/
      2023/
      2024/
      2025/
```
**Effort:** 1-2 hours

### Implementation Files
- `scripts/review_vocabulary.py` - Tag review workflow
- `scripts/review_stale.py` - Decay management
- `src/services/archival_service.py` - Archive operations

**Total Effort:** 6-9 hours

---

## Implementation Priority Ranking

### Tier 1: Biggest Impact, Medium Effort
1. **Structure-Aware Chunking** (10-14h) - Huge precision boost
2. **Feedback System - Basic** (8-12h) - Immediate curation power
3. **Hybrid Retrieval (BM25+dense)** (6-9h) - Robust retrieval

**Total:** 24-35 hours

### Tier 2: High Value, Higher Effort
4. **Graph Relationships** (12-18h) - Connected knowledge
5. **Advanced Scoring + Gates** (6-8h) - Index quality
6. **Evaluation Framework** (14-20h) - Continuous improvement

**Total:** 32-46 hours

### Tier 3: Refinements
7. **Document-Type Pipelines** (18-26h) - Source-specific handling
8. **Lifecycle Management** (6-9h) - Long-term maintenance
9. **Visualization & Dashboards** (12-16h) - Observability

**Total:** 36-51 hours

---

## Quick Wins (Can Do Now)

### Already Integrated, Just Need Testing
- ✅ Controlled vocabulary (test tag quality)
- ✅ Recency scoring (verify time awareness)
- ✅ Auto-project matching (check watchlists)
- ✅ Clean Obsidian exports (inspect YAML)

### Easy Additions (1-3 hours each)
- **Metadata filters in search** - Already mostly there
- **Simple feedback CLI** - Mark docs as golden
- **Actionability scoring** - Check against active projects
- **Quality gate thresholds** - Per-type min scores

---

## Testing Plan (Option A - Now)

See: `docs/v2_integration_testing_guide.md`

**Quick version:**
```bash
# 1. Start Docker
docker-compose build rag-service
docker-compose up rag-service

# 2. Check health
curl http://localhost:8001/health | jq

# 3. Upload test doc
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@test_school_doc.txt"

# 4. Verify metadata quality
# Expected: proper title, controlled topics, auto-matched project

# 5. Test chat
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "wann sind informationsabende"}'
```

---

## Reference Documents

**What you gave me:**
- `/Users/danielteckentrup/Downloads/personal_rag_pipeline_full.md`
- Previous conversation about V2.0 enhancements
- Four enhancement ideas (recency, vocab lifecycle, graph, feedback)

**What exists now:**
- `docs/enrichment_v2_design.md` - V2 architecture
- `docs/session_summary_2025-10-05.md` - Development log
- `docs/v2_integration_testing_guide.md` - Testing guide
- `docs/phase_3_integration_summary.md` - Integration status

**This document:**
- Complete roadmap of all ideas
- What's done vs. what's pending
- Effort estimates for each phase
- Priority recommendations

---

**Status:** Foundation solid, ready to test. Future phases well-documented.
**Next:** Test Option A (30 min), then decide on Tier 1 priorities.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
