# V2 Integration Testing Guide

**Date:** October 5, 2025
**Status:** ✅ Integration Complete - Awaiting Docker Testing

---

## Overview

Enrichment V2 with controlled vocabulary has been integrated into the main RAG pipeline. The system now supports **both V1 (multi-stage) and V2 (controlled vocabulary)** enrichment modes.

---

## What Was Integrated

### 1. New Services Added
- ✅ `EnrichmentServiceV2` - Controlled vocabulary enrichment
- ✅ `ObsidianServiceV2` - Clean YAML export
- ✅ `VocabularyService` - Vocabulary management

### 2. Integration Points

**app.py Lines 85-89** - V2 service imports:
```python
from src.services.enrichment_service_v2 import EnrichmentServiceV2
from src.services.obsidian_service_v2 import ObsidianServiceV2
from src.services.vocabulary_service import VocabularyService
```

**app.py Lines 207-209** - Configuration:
```python
USE_ENRICHMENT_V2 = os.getenv("USE_ENRICHMENT_V2", "true").lower() == "true"
VOCABULARY_DIR = os.getenv("VOCABULARY_DIR", "vocabulary")
```

**app.py Lines 672-691** - RAGService initialization:
```python
# Initialize V2 services if available and enabled
if V2_SERVICES_AVAILABLE and USE_ENRICHMENT_V2:
    self.vocabulary_service = VocabularyService(VOCABULARY_DIR)
    self.enrichment_v2 = EnrichmentServiceV2(
        llm_service=self.llm_service,
        vocab_service=self.vocabulary_service
    )
    self.obsidian_v2 = ObsidianServiceV2(output_dir=obsidian_output_dir)
```

**app.py Lines 804-829** - Document enrichment:
```python
# Use V2 enrichment if available, otherwise fall back to standard
if self.enrichment_v2:
    enriched_metadata = await self.enrichment_v2.enrich_document(...)
else:
    enriched_metadata = await self.enrichment_service.enrich_document(...)
```

**app.py Lines 938-965** - Obsidian export:
```python
if self.obsidian_v2:
    file_path = self.obsidian_v2.export_document(...)
elif self.obsidian_service:
    file_path, export_data = await self.obsidian_service.export_to_obsidian(...)
```

---

## Configuration

### Environment Variables

Add to `.env` file:

```bash
# Enrichment V2 Configuration
USE_ENRICHMENT_V2=true          # Enable V2 enrichment (default: true)
VOCABULARY_DIR=vocabulary        # Path to vocabulary configs (default: vocabulary)
```

### Vocabulary Files Required

Ensure these files exist in `vocabulary/` directory:
- ✅ `topics.yaml` - 32 hierarchical topics
- ✅ `projects.yaml` - Active projects with watchlists
- ✅ `places.yaml` - Known locations
- ✅ `people.yaml` - Privacy-safe role identifiers

---

## Testing Plan

### Phase 1: Startup Verification (10 minutes)

**Test:** Docker container starts successfully with V2 enabled

```bash
# Build and start services
docker-compose build rag-service
docker-compose up rag-service

# Expected log output:
# ✅ Initializing Enrichment V2 with controlled vocabulary...
# ✅ Enrichment V2 initialized with controlled vocabulary
#    📚 Topics: 32
#    🏗️  Projects: 2
#    📍 Places: 13
# ✅ Using Enrichment V2 (controlled vocabulary)
```

**Success Criteria:**
- [ ] Container starts without errors
- [ ] V2 services initialize
- [ ] Vocabulary files load successfully
- [ ] Log shows correct counts (32 topics, 2 projects, 13 places)

---

### Phase 2: Health Check (2 minutes)

**Test:** Health endpoint shows V2 status

```bash
curl http://localhost:8001/health | jq
```

**Expected Response:**
```json
{
  "status": "healthy",
  "llm_providers": {...},
  "reranking": {"available": true},
  "enrichment_v2": {
    "enabled": true,
    "topics_count": 32,
    "projects_count": 2,
    "places_count": 13
  }
}
```

**Success Criteria:**
- [ ] Health check returns 200
- [ ] `enrichment_v2.enabled` is true
- [ ] Vocabulary counts are correct

---

### Phase 3: Document Upload Test (15 minutes)

**Test:** Upload test document and verify V2 enrichment

```bash
# Create test document
cat > test_school_doc.txt << 'EOF'
# Florianschule Enrollment Information

The Florianschule in Essen is holding an information evening on October 2, 2025.

This is an important opportunity for parents to learn about the school's educational concept and enrollment procedures for the 2026 school year.

Contact: enrollment@florianschule-essen.de
EOF

# Upload document
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@test_school_doc.txt" \
  -F "process_ocr=false" \
  -F "generate_obsidian=true"
```

**Expected Response:**
```json
{
  "success": true,
  "doc_id": "...",
  "chunks": 1,
  "metadata": {
    "title": "Florianschule Enrollment Information",
    "summary": "...",
    "topics": ["school/admin", "school/info-day"],
    "places": ["Essen"],
    "projects": ["school-2026"],
    "organizations": ["Florianschule"],
    "quality_score": 0.85,
    "recency_score": 0.99,
    "enrichment_version": "2.0"
  },
  "obsidian_path": "/path/to/vault/20251005_Florianschule_Enrollment_abc123.md"
}
```

**Success Criteria:**
- [ ] Upload succeeds (200 response)
- [ ] Title extracted correctly (no "Untitled")
- [ ] Topics are from controlled vocabulary only
- [ ] Project auto-matched to "school-2026"
- [ ] Place detected: "Essen"
- [ ] Organization extracted: "Florianschule"
- [ ] `enrichment_version` = "2.0"
- [ ] Obsidian file created

---

### Phase 4: Obsidian Export Validation (10 minutes)

**Test:** Verify Obsidian YAML is clean

```bash
# Find the exported file
docker exec rag-service cat /path/to/obsidian/vault/20251005_Florianschule_Enrollment_abc123.md
```

**Expected YAML:**
```yaml
---
id: 20251005_abc123
title: Florianschule Enrollment Information
source: test_school_doc.txt
type: text
created_at: 2025-10-05
ingested_at: 2025-10-05

summary: The Florianschule in Essen is holding an information evening...

topics:
  - school/admin
  - school/info-day

places:
  - Essen

projects:
  - school-2026

entities:
  organizations:
    - Florianschule
  dates:
    - 2025-10-02
  contacts:
    - enrollment@florianschule-essen.de

quality_score: 0.85
recency_score: 0.99

suggested_topics:
  - school/curriculum
---

project:: [[school-2026]]

## Summary
The Florianschule in Essen...
```

**Success Criteria:**
- [ ] YAML is valid (no `DocumentType.text`, should be `text`)
- [ ] Lists use proper YAML syntax (not Python arrays)
- [ ] Topics are from controlled vocabulary
- [ ] Projects auto-matched correctly
- [ ] Dataview inline fields present (`project::`)
- [ ] Suggested topics as checklist

---

### Phase 5: Controlled Vocabulary Validation (10 minutes)

**Test:** Upload document with invalid topics

```bash
cat > test_invalid_topics.txt << 'EOF'
# Medical Research Paper

This paper discusses advanced quantum computing applications in medical diagnostics.
EOF

curl -X POST http://localhost:8001/ingest/file \
  -F "file=@test_invalid_topics.txt"
```

**Expected Behavior:**
- LLM might suggest: `"quantum-computing", "medical-research"`
- V2 should:
  - Find closest match in vocabulary (e.g., `"technology/computing"`)
  - OR add to `suggested_topics` for user review
  - NOT add invented tags to main `topics` field

**Success Criteria:**
- [ ] No invented topics in `metadata.topics`
- [ ] Invalid topics appear in `suggested_topics`
- [ ] System suggests closest vocabulary matches
- [ ] No tag contamination

---

### Phase 6: Fallback Test (5 minutes)

**Test:** Disable V2 and verify fallback to V1

```bash
# Update .env
echo "USE_ENRICHMENT_V2=false" >> .env

# Restart service
docker-compose restart rag-service

# Upload document
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@test_school_doc.txt"
```

**Expected Log:**
```
✅ Advanced multi-stage enrichment initialized (Groq + Claude + Triage)
   - Stage 1: Fast classification (Groq)
   - Stage 2: Entity extraction (Claude)
   ...
```

**Success Criteria:**
- [ ] V2 not initialized
- [ ] Falls back to V1 enrichment
- [ ] Document still processes successfully
- [ ] Backward compatibility maintained

---

### Phase 7: Chat Test with V2 Metadata (10 minutes)

**Test:** Query uploaded documents

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "wann sind informationsabende",
    "max_context_chunks": 5,
    "include_sources": true
  }' | jq
```

**Expected Response:**
```json
{
  "question": "wann sind informationsabende",
  "answer": "Der Informationsabend an der Florianschule in Essen findet am 2. Oktober 2025 statt.",
  "sources": [
    {
      "content": "...",
      "metadata": {
        "title": "Florianschule Enrollment Information",
        "topics": "school/admin,school/info-day",
        "projects": "school-2026",
        "recency_score": 0.99
      },
      "relevance_score": 0.85
    }
  ],
  "llm_provider_used": "anthropic",
  "llm_model_used": "anthropic/claude-3-5-sonnet-20241022",
  "total_chunks_found": 5,
  "cost_usd": 0.012345
}
```

**Success Criteria:**
- [ ] Chat endpoint works with V2 metadata
- [ ] Sources show proper titles (not "Untitled")
- [ ] V2 metadata fields present
- [ ] Recency scoring visible
- [ ] Answer quality good

---

## Verification Checklist

### Code Quality
- [x] All Python files compile successfully
- [x] Import statements correct
- [x] Backward compatibility maintained
- [x] Environment variables documented

### Integration
- [x] V2 services imported in app.py
- [x] RAGService initialization updated
- [x] Document enrichment flow updated
- [x] Obsidian export flow updated
- [x] Fallback to V1 implemented

### Documentation
- [x] Configuration documented
- [x] Testing guide created
- [x] Integration points documented
- [x] Success criteria defined

### Pending (Docker Testing Required)
- [ ] Container starts successfully
- [ ] V2 services initialize
- [ ] Document upload works
- [ ] Controlled vocabulary validated
- [ ] Obsidian YAML clean
- [ ] Chat endpoint works
- [ ] Fallback to V1 works

---

## Troubleshooting

### Issue: V2 Services Not Loading

**Symptoms:**
```
⚠️  V2 services initialization failed: ...
   Falling back to standard enrichment
```

**Checks:**
1. Verify `vocabulary/` directory exists
2. Check all 4 YAML files present
3. Validate YAML syntax: `docker exec rag-service python3 test_vocabulary.py`
4. Check environment variable: `USE_ENRICHMENT_V2=true`

### Issue: Invented Tags Appearing

**Symptoms:** Tags not in `vocabulary/topics.yaml` appear in `metadata.topics`

**Debug:**
```python
# Check vocabulary validation
vocab = VocabularyService("vocabulary")
print(vocab.is_valid_topic("invalid/tag"))  # Should return False
```

**Fix:** Review `enrichment_service_v2.py:296-350` - `_validate_with_vocabulary()`

### Issue: Obsidian YAML Malformed

**Symptoms:** `type: DocumentType.pdf` instead of `type: pdf`

**Debug:**
```python
# Check ObsidianServiceV2:92
# Should use: str(document_type).replace("DocumentType.", "")
```

---

## Next Steps

1. **Docker Testing** - Run full test suite in Docker environment
2. **Migration Script** - Re-enrich existing 101 documents with V2
3. **Advanced Features** - Implement graph relationships, feedback API
4. **Performance Monitoring** - Compare V1 vs V2 enrichment costs

---

## Related Files

**Integration:**
- `app.py:85-89` - Imports
- `app.py:672-691` - Initialization
- `app.py:804-829` - Enrichment
- `app.py:938-965` - Export

**V2 Services:**
- `src/services/enrichment_service_v2.py`
- `src/services/obsidian_service_v2.py`
- `src/services/vocabulary_service.py`

**Vocabulary:**
- `vocabulary/topics.yaml`
- `vocabulary/projects.yaml`
- `vocabulary/places.yaml`
- `vocabulary/people.yaml`

**Documentation:**
- `docs/enrichment_v2_design.md` - Architecture
- `docs/session_summary_2025-10-05.md` - Development log
- `docs/v2_integration_testing_guide.md` - This file

---

**Generated:** October 5, 2025
**Status:** Ready for Docker testing
