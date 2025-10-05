# Enrichment V2 - High-Signal Metadata Architecture

**Version:** 2.0
**Date:** 2025-10-05
**Status:** Design → Implementation

---

## Overview

Complete redesign of document enrichment to eliminate tag contamination, improve retrieval quality, and enable advanced features (recency, feedback, graph links).

## Problems Solved

1. ❌ **Tag contamination** - Admin docs getting psychology tags
2. ❌ **No controlled vocabulary** - Inconsistent, invented tags
3. ❌ **"Untitled" documents** - Poor title extraction
4. ❌ **One-size-fits-all enrichment** - Same pipeline for all doc types
5. ❌ **No recency awareness** - Old docs rank same as new
6. ❌ **No user feedback** - Can't boost known-good docs
7. ❌ **No document relationships** - Isolated chunks

---

## New Metadata Schema

```yaml
---
# === IDENTITY ===
id: 2025-10-05_schulkonzept_florianschule_a7f3
source: pdf.upload
path: data/processed/2025-10-05_schulkonzept_florianschule_a7f3.md
created_at: 2025-09-15                    # Document creation date
ingested_at: 2025-10-05                   # System ingest date
doc_type: school.admin.concept            # Hierarchical type

# === TITLE & SUMMARY ===
title: "Schulkonzept - Florianschule Essen"
summary: |
  School concept document covering educational philosophy,
  teaching methods, and organizational structure.

# === CONTROLLED VOCABULARY ===
people: []                                 # From vocabulary/people.yaml
places: [Essen]                           # From vocabulary/places.yaml
projects: [school-2026]                   # From vocabulary/projects.yaml
topics: [school/admin, school/concept]    # From vocabulary/topics.yaml

# === EXTRACTED ENTITIES (not controlled) ===
entities:
  orgs: [Florianschule, Stadt Essen]
  dates: [2025-09-15, 2025-10-02]
  contacts: []
  numbers: []

# === QUALITY SCORING ===
quality_score: 0.94          # OCR/parse quality (0-1)
novelty_score: 0.72          # Uniqueness vs corpus (0-1)
actionability_score: 0.80    # Relevance to watchlist (0-1)
recency_score: 0.95          # Time-based decay (0-1, auto-calculated)
signalness: 0.85             # Composite (0-1)

# === INDEXING CONTROL ===
do_index: true               # Gate based on quality thresholds
index_tier: primary          # primary | secondary | archive

# === SUGGESTED VOCABULARY (for review) ===
suggested_tags:
  - school/curriculum          # User can approve → topics
  - education/methodology      # User can approve → topics

# === RELATIONSHIPS ===
related_docs: []                          # IDs of linked documents
parent_doc: null                          # For multi-part documents
supersedes: null                          # For document versions

# === USER FEEDBACK ===
feedback:
  correctness_score: null                 # User-rated (0-1)
  last_reviewed_by_user: null             # ISO date
  notes: ""                               # User annotations
  pinned: false                           # Force into results

# === PROVENANCE ===
provenance:
  sha256: "7c1a..."
  filename: "Schulkonzept.pdf"
  source_path: "/data/input/Schulkonzept.pdf"
  page_count: 12
  ocr_provider: tesseract
  ocr_confidence: 0.94

# === ENRICHMENT METADATA ===
enrichment_version: 2.0
enrichment_pipeline: school.admin.concept  # Which pipeline used
enrichment_date: 2025-10-05
enrichment_cost: 0.0023                    # USD

---

# Document Content...
```

---

## Controlled Vocabulary System

### File Structure
```
vocabulary/
  people.yaml           # Known people
  places.yaml          # Known places
  projects.yaml        # Active projects
  topics.yaml          # Hierarchical topics
  organizations.yaml   # Known orgs (optional)
```

### Example: `vocabulary/topics.yaml`
```yaml
# Hierarchical topic vocabulary
# Format: category/subcategory or category/subcategory/detail

school:
  - school/admin
  - school/admin/enrollment
  - school/admin/schedule
  - school/concept
  - school/curriculum
  - school/events

kita:
  - kita/admin
  - kita/handover
  - kita/schedule
  - kita/pickup

legal:
  - legal/custody
  - legal/court
  - legal/judgment
  - legal/motion

personal:
  - personal/health
  - personal/finance
  - personal/travel
```

### Example: `vocabulary/projects.yaml`
```yaml
# Active projects (time-bound focus areas)

active:
  - custody-2025:
      start: 2025-01-01
      end: 2026-01-01
      watchlist: [legal/custody, kita/handover]

  - school-2026:
      start: 2025-09-01
      end: 2026-09-01
      watchlist: [school/admin, school/enrollment]

archived:
  - kita-transition-2024:
      start: 2024-01-01
      end: 2025-01-01
```

---

## Document Type Routing

### Type Hierarchy
```
pdf
  ├── pdf.school.admin
  ├── pdf.school.concept
  ├── pdf.school.letter
  ├── pdf.legal.judgment
  ├── pdf.legal.motion
  ├── pdf.medical.report
  ├── pdf.financial.invoice
  └── pdf.general

email
  ├── email.thread
  └── email.single

note
  └── note.manual
```

### Pipeline Selection
```python
ENRICHMENT_PIPELINES = {
    "pdf.school.admin": SchoolAdminEnricher,
    "pdf.school.concept": SchoolConceptEnricher,
    "pdf.legal.judgment": LegalJudgmentEnricher,
    "email.thread": EmailThreadEnricher,
    "note.manual": NoteEnricher,
    "default": GenericEnricher
}
```

---

## Recency Score Calculation

```python
def calculate_recency_score(created_at: date) -> float:
    """
    Exponential decay based on document age

    - Today = 1.0
    - 1 month ago = 0.9
    - 6 months ago = 0.6
    - 1 year ago = 0.4
    - 2 years ago = 0.2
    - 5+ years ago = 0.05
    """
    from datetime import datetime, timedelta

    today = datetime.now().date()
    age_days = (today - created_at).days

    # Exponential decay: score = e^(-lambda * age_days)
    # lambda = 0.003 gives ~6 month half-life
    import math
    decay_rate = 0.003
    score = math.exp(-decay_rate * age_days)

    return max(0.05, min(1.0, score))  # Clamp to [0.05, 1.0]
```

### Retrieval Boost
```python
def boost_with_recency(rerank_score: float, recency_score: float) -> float:
    """
    Apply recency boost to reranked results

    Recent docs get up to 20% boost
    Old docs get slight penalty (down to 5% of original)
    """
    return rerank_score * (1 + 0.2 * recency_score)
```

---

## Suggested Tags Workflow

### 1. Enrichment Stage
```python
# During enrichment, model proposes new tags
result = {
    "topics": ["school/admin"],           # Only from controlled vocab
    "suggested_tags": [                    # New proposals
        "school/curriculum",
        "education/methodology"
    ]
}
```

### 2. Review Command
```bash
# Weekly review of suggestions
python scripts/review_suggested_tags.py

# Output:
# === Suggested Tags Review ===
#
# "school/curriculum" (5 occurrences)
#   Used in: Schulkonzept.pdf, Lehrplan.pdf, ...
#   [a]pprove  [r]eject  [m]erge into existing  [s]kip
#
# > a
# ✅ Added "school/curriculum" to vocabulary/topics.yaml
```

### 3. Auto-Promotion
```python
# Automatically promote suggestions that appear 5+ times
if suggestion_count >= 5:
    add_to_vocabulary(tag)
    update_all_docs_with_suggestion(tag)
```

---

## Graph Relationships

### Automatic Linking
```python
def extract_relationships(doc, corpus):
    """
    Link documents based on:
    - Shared projects
    - Date ranges
    - Mentioned document titles
    - Reply-to relationships (email)
    """
    related = []

    # Project-based linking
    for project in doc.projects:
        related.extend(find_docs_by_project(project, limit=5))

    # Temporal linking (±7 days)
    related.extend(find_docs_by_date_range(
        doc.created_at - 7,
        doc.created_at + 7,
        limit=3
    ))

    # Title mentions
    mentioned_titles = extract_doc_references(doc.content)
    for title in mentioned_titles:
        match = find_doc_by_title(title)
        if match:
            related.append(match.id)

    return list(set(related))  # Dedupe
```

### Graph Expansion During Retrieval
```python
def retrieve_with_graph_expansion(query, top_k=10):
    # Phase 1: Standard retrieval
    initial_results = hybrid_retrieve(query, k=30)
    reranked = rerank(query, initial_results, k=top_k)

    # Phase 2: Graph expansion
    expanded = []
    for doc in reranked:
        expanded.append(doc)

        # Add highly related docs (if not already in results)
        for related_id in doc.related_docs[:2]:  # Top 2 related
            related_doc = get_doc(related_id)
            if related_doc not in expanded:
                expanded.append(related_doc)

    # Phase 3: Re-rerank expanded set
    final = rerank(query, expanded, k=top_k)
    return final
```

---

## User Feedback System

### Manual Review Interface
```python
# After retrieving a document, user can rate it
@app.post("/feedback")
async def add_feedback(doc_id: str, feedback: UserFeedback):
    doc = get_doc(doc_id)
    doc.feedback = {
        "correctness_score": feedback.score,
        "last_reviewed_by_user": datetime.now(),
        "notes": feedback.notes,
        "pinned": feedback.pinned
    }
    save_doc(doc)
```

### Feedback-Boosted Retrieval
```python
def apply_feedback_boost(results):
    """
    Boost documents with user feedback

    - Pinned docs: Always in top 3
    - High correctness (>0.8): +30% boost
    - Medium correctness (0.5-0.8): +15% boost
    - Low/no feedback: No change
    """
    boosted = []
    pinned = []

    for doc in results:
        if doc.feedback.pinned:
            pinned.append(doc)
        elif doc.feedback.correctness_score:
            if doc.feedback.correctness_score > 0.8:
                doc.score *= 1.30
            elif doc.feedback.correctness_score > 0.5:
                doc.score *= 1.15
        boosted.append(doc)

    # Pinned docs go first
    return pinned + sorted(boosted, key=lambda x: x.score, reverse=True)
```

---

## Implementation Phases

### Phase 1: Foundation (2-3 hours)
- [x] Create vocabulary config files
- [x] Design new metadata schema
- [ ] Implement VocabularyService
- [ ] Update DocumentMetadata model

### Phase 2: Enrichment Refactor (3-4 hours)
- [ ] Create doc-type classifiers
- [ ] Build type-specific enrichers
- [ ] Implement suggested_tags extraction
- [ ] Add recency_score calculation
- [ ] Fix title extraction

### Phase 3: Relationships & Feedback (2-3 hours)
- [ ] Implement relationship extraction
- [ ] Add graph expansion to retrieval
- [ ] Create feedback API endpoints
- [ ] Build feedback-boosted ranking

### Phase 4: Integration (1-2 hours)
- [ ] Update RAGService to use new pipeline
- [ ] Update Obsidian export with clean YAML
- [ ] Add suggested_tags review script
- [ ] Update health check with vocab stats

---

## Quality Gates (per doc type)

```python
QUALITY_GATES = {
    "pdf.school.admin": {
        "min_quality": 0.75,
        "min_signalness": 0.65,
        "tier": "primary"
    },
    "pdf.legal.judgment": {
        "min_quality": 0.80,
        "min_signalness": 0.70,
        "tier": "primary"
    },
    "email.thread": {
        "min_quality": 0.70,
        "min_signalness": 0.60,
        "tier": "primary"
    },
    "note.manual": {
        "min_quality": 0.60,
        "min_signalness": 0.50,
        "tier": "primary"
    },
    "default": {
        "min_quality": 0.65,
        "min_signalness": 0.55,
        "tier": "secondary"
    }
}
```

---

## Migration Strategy

### Existing Documents
```bash
# Script to migrate existing docs to new schema
python scripts/migrate_to_enrichment_v2.py

# Options:
# --dry-run          # Show changes without applying
# --batch-size 10    # Process in batches
# --re-enrich        # Re-run enrichment with new pipelines
```

### Backward Compatibility
- Keep old `tags` field but mark deprecated
- Map old tags to new `topics` + `suggested_tags`
- Gradual migration over 2 weeks

---

## Success Metrics

**After implementing V2:**
- ✅ 0 tag contamination (admin docs get admin tags only)
- ✅ 95%+ documents have proper titles (not "Untitled")
- ✅ Controlled vocab covers 80%+ of content (20% in suggestions)
- ✅ Recency boost improves answer relevance by 20%
- ✅ User feedback creates "golden" document set
- ✅ Graph expansion increases answer completeness by 30%

---

*Keep it controlled, measured, and user-driven.*
