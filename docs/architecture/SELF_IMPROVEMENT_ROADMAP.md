# Self-Improvement Loop Roadmap

**Date:** October 8, 2025, 23:50 CET
**Based on:** LLM RAG Improver pattern analysis
**Current Grade:** A- (91/100)
**Target Grade:** A++ (99/100)

---

## 📊 What We Have vs. What's Recommended

### ✅ Already Implemented (Today, Oct 8, 2025)

| Component | Recommended | Our Status | Notes |
|-----------|-------------|------------|-------|
| **LLM-as-Critic Scoring** | ✅ 7-point rubric (0-5) | ✅ **IMPLEMENTED** | `src/services/enrichment_service.py:critique_enrichment()` |
| **Rubric Dimensions** | 7 dimensions | ✅ **IMPLEMENTED** | schema, entities, topics, summary, tasks, privacy, chunking |
| **Critic Output** | JSON with scores + issues | ✅ **IMPLEMENTED** | Returns `CritiqueResult` with scores + suggestions |
| **Controlled Vocabulary** | ✅ Tag ontology | ✅ **IMPLEMENTED** | `vocabulary/*.yaml` |
| **Lossless Archiving** | ✅ Never mutate source | ✅ **IMPLEMENTED** | `/data/processed_originals/` |
| **Embeddings Out of YAML** | ✅ Store refs only | ✅ **IMPLEMENTED** | ChromaDB stores embeddings, YAML has doc_id |
| **Gold Query Evaluation** | ✅ Query feedback | ✅ **IMPLEMENTED** | `scripts/evaluate_retrieval.py` |
| **Quality Scoring Log** | ✅ Trend quality | ✅ **PARTIAL** | Scores returned but not persisted to DB |

### ⚠️ Partially Implemented

| Component | Recommended | Our Status | Gap |
|-----------|-------------|------------|-----|
| **Frontmatter Schema** | Versioned, future-proof | ⚠️ **PARTIAL** | Missing: `rag.versions`, `review.*`, `quality.pii_risk` |
| **Task Extraction** | Extract deadlines/actions | ⚠️ **MISSING** | Prompt includes tasks but not validated |

### ❌ Not Implemented (Critical Gaps)

| Component | Recommended | Our Status | Effort to Add |
|-----------|-------------|------------|---------------|
| **LLM-as-Editor** | JSON patch generator | ❌ **MISSING** | **8-12 hours** |
| **Patch Application** | Safe YAML merge | ❌ **MISSING** | **4 hours** |
| **JSON Schema Validation** | Pre-write validation | ❌ **MISSING** | **3 hours** |
| **Diff Logging** | Before/after diffs | ❌ **MISSING** | **2 hours** |
| **Iteration Loop** | Score → Edit → Re-score | ❌ **MISSING** | **4 hours** |
| **Quality Trending** | Store scores in DB | ❌ **MISSING** | **2 hours** |
| **Active Learning** | Query feedback → Re-enrich | ❌ **MISSING** | **1-2 days** |
| **Entity Canonicalization** | "Dr. Weber" = "Thomas Weber" | ❌ **MISSING** | **1-2 days** |
| **Batch Re-enrichment** | Update old docs with new prompts | ❌ **MISSING** | **4 hours** |

---

## 🎯 Implementation Roadmap

### Phase 1: Complete Self-Improvement Loop (2-3 days)
**Goal:** Full "critic → editor → validate → apply" cycle

#### 1.1 LLM-as-Editor (8-12 hours)
**File:** `src/services/editor_service.py` (NEW)

**Implementation:**
```python
class EditorService:
    """LLM-based YAML editor that generates safe JSON patches"""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.forbidden_paths = [
            'id', 'source.*', 'rag.vector_ref.*',
            'doc_time.created', 'source.content_hash'
        ]

    async def generate_patch(
        self,
        current_yaml: dict,
        critic_result: CritiqueResult,
        body_text: str
    ) -> dict:
        """
        Generate JSON patch from critic suggestions

        Returns:
            {
                "add": {"entities.places": ["Essen"]},
                "replace": {"summary.tl_dr": "Updated summary"},
                "remove": ["topics[2]"]
            }
        """
        # Build editor prompt
        # Call LLM with strict JSON output
        # Validate patch doesn't touch forbidden paths
        # Return validated patch
```

**Prompt Template:**
```
You are a YAML Frontmatter Editor for a RAG enrichment system.

RULES:
1. Output ONLY a JSON patch object with keys: add, replace, remove
2. NEVER modify: id, source.*, rag.vector_ref.*, doc_time.created, source.content_hash
3. Keep summaries ≤120 words, key_points ≤5, topics ≤5
4. Use controlled vocabulary from: {vocabulary_tags}
5. Do not hallucinate dates - omit if not explicit in text

Input YAML:
{current_yaml}

Critic Suggestions:
{critic_suggestions}

Document Body:
{body_text}

Output JSON patch:
```

**Effort:** 8-12 hours
- Service implementation: 4 hours
- Prompt engineering: 2 hours
- Path validation logic: 2 hours
- Testing: 4 hours

---

#### 1.2 JSON Schema Validation (3 hours)
**File:** `src/schemas/enrichment_schema.json` (NEW)

**Implementation:**
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id", "source", "doc_time"],
  "properties": {
    "id": {"type": "string", "pattern": "^[0-9a-f-]+$"},
    "source": {
      "type": "object",
      "properties": {
        "type": {"enum": ["email", "pdf", "whatsapp", "web", "note"]},
        "path": {"type": "string"},
        "content_hash": {"type": "string", "pattern": "^sha256:"}
      }
    },
    "summary": {
      "type": "object",
      "properties": {
        "tl_dr": {"type": "string", "maxLength": 600},
        "key_points": {
          "type": "array",
          "maxItems": 5,
          "items": {"type": "string"}
        }
      }
    },
    "topics": {
      "type": "array",
      "maxItems": 5,
      "items": {"type": "string"}
    }
  }
}
```

**Validation Service:**
```python
from jsonschema import validate, ValidationError

class SchemaValidator:
    def __init__(self, schema_path: str):
        with open(schema_path) as f:
            self.schema = json.load(f)

    def validate_enrichment(self, yaml_dict: dict) -> tuple[bool, list[str]]:
        """Validate YAML against schema"""
        try:
            validate(instance=yaml_dict, schema=self.schema)
            return True, []
        except ValidationError as e:
            return False, [str(e)]
```

**Effort:** 3 hours
- Schema definition: 1 hour
- Validator implementation: 1 hour
- Testing: 1 hour

---

#### 1.3 Patch Application & Diff Logging (4 hours)
**File:** `src/services/patch_service.py` (NEW)

**Implementation:**
```python
import jsonpatch
from deepdiff import DeepDiff

class PatchService:
    """Apply JSON patches safely with diff logging"""

    def apply_patch(
        self,
        original: dict,
        patch: dict,
        forbidden_paths: list[str]
    ) -> tuple[dict, dict]:
        """
        Apply patch and return (patched_yaml, diff)

        Raises:
            ValueError if patch touches forbidden paths
        """
        # Validate patch paths
        self._validate_paths(patch, forbidden_paths)

        # Apply patch
        patched = self._merge_patch(original, patch)

        # Generate diff for logging
        diff = DeepDiff(original, patched, verbose_level=2)

        return patched, diff

    def _validate_paths(self, patch: dict, forbidden: list[str]):
        """Ensure patch doesn't touch forbidden fields"""
        for action in ['add', 'replace', 'remove']:
            if action in patch:
                for path in patch[action].keys():
                    if any(path.startswith(fp) for fp in forbidden):
                        raise ValueError(f"Cannot modify {path}")
```

**Effort:** 4 hours
- Patch application: 2 hours
- Diff generation: 1 hour
- Testing: 1 hour

---

#### 1.4 Iteration Loop (4 hours)
**File:** `src/services/enrichment_service.py` (UPDATE)

**New Method:**
```python
async def enrich_with_iteration(
    self,
    text: str,
    filename: str,
    max_iterations: int = 2,
    min_avg_score: float = 4.0
) -> tuple[dict, CritiqueResult]:
    """
    Iterative enrichment with critic feedback

    Loop:
    1. Initial enrichment
    2. Critic scores it
    3. If avg score < min_avg_score and iterations left:
       - Editor generates patch
       - Validate patch
       - Apply patch
       - Re-score with critic
    4. Return final enrichment + final critique
    """
    current_enrichment = await self.enrich_document(text, filename)

    for iteration in range(max_iterations):
        critique = await self.critique_enrichment(current_enrichment, text)

        avg_score = sum(critique.scores.dict().values()) / 7

        if avg_score >= min_avg_score:
            logger.info(f"✅ Quality threshold reached: {avg_score:.2f}")
            break

        # Generate and apply patch
        patch = await self.editor.generate_patch(
            current_enrichment, critique, text
        )

        # Validate and apply
        patched, diff = self.patcher.apply_patch(
            current_enrichment, patch, forbidden_paths
        )

        # Log diff
        logger.info(f"📝 Iteration {iteration+1} patch applied: {diff}")

        current_enrichment = patched

    return current_enrichment, critique
```

**Effort:** 4 hours
- Integration: 2 hours
- Testing: 2 hours

---

### Phase 2: Schema Upgrade (1 day)
**Goal:** Future-proof frontmatter with versioning

#### 2.1 Add Missing Schema Fields
**Current schema:** Missing `rag.versions`, `review.*`, `quality.pii_risk`

**New fields:**
```yaml
quality:
  ocr_confidence: 0.93
  pii_risk: "low|medium|high"  # NEW

rag:
  index_status: "raw|enriched|indexed|needs_review"
  versions:  # NEW
    enrichment_prompt: "v2.2"
    model: "groq/llama-3.1-8b-instant"
    enriched_at: "2025-10-08T21:15:00Z"

review:  # NEW
  human: null
  last_checked: null
  needs_attention: false
```

**Effort:** 2 hours
- Schema update: 1 hour
- Migration script: 30 min
- Testing: 30 min

---

#### 2.2 Quality Score Persistence
**Goal:** Track quality trends over time

**Database Schema:**
```sql
CREATE TABLE enrichment_quality (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255),
    enriched_at TIMESTAMP,
    schema_score FLOAT,
    entities_score FLOAT,
    topics_score FLOAT,
    summary_score FLOAT,
    tasks_score FLOAT,
    privacy_score FLOAT,
    chunking_score FLOAT,
    avg_score FLOAT,
    model_used VARCHAR(100),
    prompt_version VARCHAR(50)
);
```

**Effort:** 2 hours
- Table creation: 30 min
- Insert logic: 1 hour
- Query endpoints: 30 min

---

#### 2.3 Batch Re-enrichment Tool
**Goal:** Update old documents with new prompts

**Script:** `scripts/batch_reenrich.py`
```python
#!/usr/bin/env python3
"""Re-enrich documents with new prompt version"""

async def batch_reenrich(
    collection,
    prompt_version: str,
    filter_criteria: dict = None
):
    """
    Re-enrich documents that:
    - Have prompt version < target version
    - Or have avg_score < 4.0
    - Or are missing key fields
    """
    # Get documents needing update
    docs = collection.get(where=filter_criteria)

    for doc in docs:
        # Re-run enrichment with iteration
        new_enrichment, critique = await enrich_with_iteration(
            doc['content'], doc['filename']
        )

        # Update document
        collection.update(
            ids=[doc['id']],
            metadatas=[new_enrichment]
        )

        logger.info(f"✅ Re-enriched {doc['filename']}: {critique.avg_score:.2f}")
```

**Effort:** 4 hours
- Script implementation: 2 hours
- Safety checks: 1 hour
- Testing: 1 hour

---

### Phase 3: Entity Canonicalization (1-2 days)
**Goal:** "Dr. Weber" = "Thomas Weber" = "T. Weber"

#### 3.1 Entity Registry
**File:** `src/services/entity_canonicalization_service.py` (NEW)

**Implementation:**
```python
from rapidfuzz import fuzz, process

class EntityCanonicalizer:
    """Deduplicate and canonicalize entity names"""

    def __init__(self):
        self.canonical_people = {}  # "thomas weber" -> "Dr. Thomas Weber"
        self.canonical_orgs = {}
        self.aliases = {}  # "HNBK" -> "Heinz-Nixdorf Berufskolleg"

    def canonicalize_person(self, name: str) -> str:
        """Return canonical form or register new"""
        normalized = name.lower().strip()

        # Exact match
        if normalized in self.canonical_people:
            return self.canonical_people[normalized]

        # Fuzzy match (>90% similarity)
        matches = process.extract(
            normalized,
            self.canonical_people.keys(),
            scorer=fuzz.token_sort_ratio,
            limit=1
        )

        if matches and matches[0][1] > 90:
            canonical = self.canonical_people[matches[0][0]]
            # Store alias
            self.canonical_people[normalized] = canonical
            return canonical

        # New entity - register
        self.canonical_people[normalized] = name
        return name
```

**Effort:** 1-2 days
- Service implementation: 4 hours
- Alias database: 2 hours
- Integration with enrichment: 4 hours
- Migration of existing entities: 4 hours
- Testing: 2 hours

---

### Phase 4: Active Learning (2-3 days)
**Goal:** Learn from query feedback and improve

#### 4.1 Query Logging
**Table:**
```sql
CREATE TABLE query_feedback (
    id SERIAL PRIMARY KEY,
    query_text TEXT,
    retrieved_docs JSONB,
    user_clicked_doc VARCHAR(255),
    user_feedback VARCHAR(20),  -- 'helpful', 'not_helpful'
    timestamp TIMESTAMP,
    relevance_scores JSONB
);
```

**Endpoint:**
```python
@router.post("/feedback/query")
async def log_query_feedback(
    query: str,
    clicked_doc_id: str,
    helpful: bool
):
    """User clicked a doc - was it helpful?"""
    # Store in DB
    # If not helpful, flag for review
```

**Effort:** 4 hours

---

#### 4.2 Gold Query Builder
**Goal:** Auto-build gold queries from user feedback

```python
async def build_gold_queries_from_feedback():
    """
    Find queries where:
    - User clicked a specific doc
    - Marked it as helpful
    - That doc wasn't in top 3

    → Add to gold query set
    """
    # Query feedback DB
    # Generate gold_queries.yaml entries
    # Flag docs for re-enrichment
```

**Effort:** 8 hours

---

#### 4.3 Feedback-Driven Re-enrichment
**Goal:** When queries fail, improve the docs

```python
async def reenrich_from_failed_queries():
    """
    For queries with low relevance:
    1. Identify which fields were missing
    2. Re-run enrichment with focus on those fields
    3. Re-index
    4. Test if query now succeeds
    """
```

**Effort:** 1 day

---

## 📊 Effort Summary

| Phase | Component | Effort | Grade Impact |
|-------|-----------|--------|--------------|
| **Phase 1** | Self-Improvement Loop | **2-3 days** | **+5 points → A+ (96%)** |
| 1.1 | LLM-as-Editor | 8-12 hours | |
| 1.2 | JSON Schema Validation | 3 hours | |
| 1.3 | Patch Application | 4 hours | |
| 1.4 | Iteration Loop | 4 hours | |
| **Phase 2** | Schema Upgrade | **1 day** | **+1 point → A (92%)** |
| 2.1 | Missing Fields | 2 hours | |
| 2.2 | Quality Persistence | 2 hours | |
| 2.3 | Batch Re-enrichment | 4 hours | |
| **Phase 3** | Entity Canonicalization | **1-2 days** | **+2 points → A+ (96%)** |
| 3.1 | Entity Registry | 1-2 days | |
| **Phase 4** | Active Learning | **2-3 days** | **+3 points → A++ (99%)** |
| 4.1 | Query Logging | 4 hours | |
| 4.2 | Gold Query Builder | 8 hours | |
| 4.3 | Feedback Re-enrichment | 1 day | |

**Total Effort to A++ (99/100): 6-9 days**

**Critical Path to A+ (96/100): 3-5 days** (Phase 1 + Phase 3)

---

## 🎯 Recommended Next Steps

### Immediate (This Week)
1. **Pin dependencies** (2 hours) **← CRITICAL**
2. **Fix 48 failing tests** (4-6 hours)
3. **Implement LLM-as-Editor** (8-12 hours)
4. **Add JSON Schema validation** (3 hours)

**Result:** Grade A (93/100) in 1.5 days

---

### Short-term (Next 2 Weeks)
5. **Implement iteration loop** (4 hours)
6. **Add missing schema fields** (2 hours)
7. **Build entity canonicalization** (1-2 days)

**Result:** Grade A+ (96/100) in 3-5 days total

---

### Medium-term (This Month)
8. **Quality score persistence** (2 hours)
9. **Batch re-enrichment tool** (4 hours)
10. **Query logging** (4 hours)
11. **Active learning loop** (2-3 days)

**Result:** Grade A++ (99/100) in 6-9 days total

---

## 💡 Key Insights from Pattern Analysis

**What we did right:**
- ✅ LLM-as-critic with 7-point rubric (exactly as recommended)
- ✅ Controlled vocabulary (exactly as recommended)
- ✅ Lossless archiving (exactly as recommended)
- ✅ Embeddings out of YAML (exactly as recommended)
- ✅ Gold query evaluation (exactly as recommended)

**What we're missing:**
- ❌ LLM-as-editor (the second half of the pattern)
- ❌ Safe patch application with validation
- ❌ Iteration loop (score → edit → re-score)
- ❌ Schema versioning
- ❌ Active learning from query feedback

**Critical insight:**
We implemented the **measurement** side perfectly (critic, evaluation, archiving). We're missing the **improvement** side (editor, iteration, learning). This is why we're at A- (91/100) instead of A++ (99/100).

**The pattern author is right:** The critic without the editor is like having a code reviewer who points out bugs but never fixes them. We need both.

---

## 📝 Conclusion

**Current State:** We have an excellent foundation with quality measurement. We're **91% there**.

**Next 9% (to reach 100%):**
- Editor + iteration loop (2-3 days) → **+5 points**
- Entity canonicalization (1-2 days) → **+2 points**
- Active learning (2-3 days) → **+2 points**

**Realistic timeline:** 6-9 days of focused work to reach A++ (99/100).

**What to build first:** LLM-as-Editor (Phase 1.1) - This is the critical missing piece that unlocks the entire self-improvement loop.

---

**Document created:** October 8, 2025, 23:55 CET
**By:** Claude (Sonnet 4.5) based on LLM RAG Improver pattern analysis
**Status:** Actionable roadmap with realistic effort estimates
