# RAG System Improvements Roadmap

**Date:** October 16, 2025
**Context:** After 100-email production test (94% success rate)

## Executive Summary

**Current State:** Production-ready RAG system with smart triage, 100% duplicate detection, and working enrichment pipeline.

**Success Metrics:**
- 94/100 emails ingested successfully (94%)
- 1 duplicate detected correctly (1%)
- 5 failures from schema limits (5%) - **NOW FIXED**
- RAG search working (381ms average)
- Cost: $0.00846 for 94 enrichments

**Issues Fixed:**
1. ✅ Entity limit (20→50 people for recipient lists)
2. ✅ Attachment links error (missing self.settings)

**Next Phase:** Improve enrichment quality, Obsidian UX, and vocabulary management.

---

## 1. Obsidian Filename Conventions

### Current Format
```
2021-01-22__email__20210122-wunschkonzerte__1b3c.md
└─ date  └─ type └─ sanitized-filename └─ hash
```

### Issues
- **Double underscores** (`__`) - reduces readability
- **Date always today** - ingestion date, not email date
- **No attachment numbering** - Hard to track "email 1 of 3 attachments"
- **No document type prefix** - `E01` for email, `A01` for attachment would be clearer

### Proposed Improvements

**New Format:**
```
E_2021-01-22_wunschkonzerte_1b3c.md          (email)
E_2021-01-22_wunschkonzerte_A01_4f8a.md      (attachment 1)
E_2021-01-22_wunschkonzerte_A02_9c3e.md      (attachment 2)
D_2025-10-16_meeting-notes_7b2d.md           (document)
C_2024-03-15_alice-bob_5e1f.md               (chat export)
```

**Benefits:**
- Single underscores (more readable)
- Document type prefix (E=email, A=attachment, D=document, C=chat)
- Attachment numbering (A01, A02, A03...)
- Sortable by type and date
- Hash remains for uniqueness

**Implementation Location:** `src/services/obsidian_service.py:generate_filename()`

---

## 2. Controlled Vocabulary Enhancements

### Current State
- ✅ YAML-based vocabularies (6 files)
- ✅ Hierarchical structure (`category/subcategory/detail`)
- ✅ Dynamic loading (edit-and-go)
- ❌ LLM can't suggest vocabulary additions
- ❌ No hierarchy optimization
- ❌ Limited daycare-specific keywords

### Issues from 100-Email Test

**96% categorized as "archival" (low confidence):**
- Missing German daycare keywords
- Pattern matching too conservative
- No event-specific patterns

**Suggested Topics Not Captured:**
- LLM finds relevant topics not in vocabulary
- No automated "pull request" workflow
- Manual review required

### Proposed Enhancements

#### 2.1 LLM-Driven Vocabulary Growth

**Current Flow:**
```
Document → LLM → Topics (from vocab) + Suggested Topics
                             ↓
                         Manual Review (lost)
```

**Proposed Flow:**
```
Document → LLM → Topics + Suggested Topics
                         ↓
                   Auto-save to suggested_topics.yaml
                         ↓
                   Monthly review → Accept/Reject → Merge to topics.yaml
```

**Implementation:**
1. Create `vocabulary/suggested_topics.yaml` (auto-generated)
2. LLM writes suggestions with context:
   ```yaml
   suggested:
     - topic: "kita/parent-teacher-conference"
       reasoning: "Found in 12 documents, no existing match"
       example_docs: ["doc_id_1", "doc_id_2"]
       frequency: 12
       status: "pending_review"
   ```
3. Monthly script: `python scripts/review_suggestions.py`
4. Accept → Merge to `topics.yaml` with proper hierarchy

#### 2.2 Daycare-Specific Keywords

**Add to `vocabulary/topics.yaml`:**
```yaml
kita:
  - kita/betreuung          # childcare
  - kita/eingewöhnung       # settling-in period
  - kita/elternabend        # parent evening
  - kita/elternbeitrag      # parent contribution/fees
  - kita/schließzeiten      # closing times
  - kita/vertrag            # contract
  - kita/anmeldung          # registration
  - kita/bring-abhol        # drop-off/pick-up
  - kita/notbetreuung       # emergency care
  - kita/gruppengestaltung  # group arrangement
  - kita/personalausfall    # staff absence
  - kita/maskenpflicht      # mask mandate
  - kita/gesundheit         # health/illness
```

**Add to `vocabulary/projects.yaml`:**
```yaml
villa_luna:
  name: "Villa Luna Köln"
  type: "ongoing"
  keywords: ["villa luna", "bonner wall", "neustadt", "raderthal"]
  location: "Köln"
```

#### 2.3 Hierarchy Visualization

**Tool:** `python scripts/visualize_vocabulary.py`

**Output:**
```
topics.yaml (89 topics, 5 levels deep)
├── education/ (23)
│   ├── school/ (12)
│   │   ├── enrollment (3 docs)
│   │   ├── events (8 docs)
│   │   └── admin (15 docs)
│   ├── childcare/ (11)
│   │   └── daycare (42 docs)  ← HIGH USAGE
└── legal/ (31)
    └── court/ (9)
        └── decision (5 docs)

📊 Usage stats:
- Most used: education/childcare (42 docs)
- Least used: legal/court (5 docs)
- Suggested: 12 pending review
```

---

## 3. Enrichment Quality Improvements

### Current State
- ✅ Groq Llama 3.3 70B ($0.00009/doc)
- ✅ Pydantic validation via Instructor
- ✅ Optional LLM-as-critic (disabled by default)
- ❌ Conservative topic assignment (defaults to "archival")
- ❌ Limited German keyword recognition

### Issues from 100-Email Test

**Root Causes of 94% "archival":**
1. Vocabulary doesn't include German daycare terms
2. LLM prompt may not emphasize German keyword matching
3. Confidence threshold may be too high

### Proposed Improvements

#### 3.1 Enhanced German Keyword Prompting

**Update enrichment prompt in `src/services/enrichment_service.py`:**

```python
ENRICHMENT_PROMPT_V3 = """
Analyze this document and extract structured metadata.

IMPORTANT - GERMAN KEYWORD AWARENESS:
- Many documents are in German (daycare/kita correspondence)
- German keywords: betreuung, eingewöhnung, elternabend, anmeldung, vertrag
- Match German keywords to English topics:
  - "Betreuungsvertrag" → education/childcare, kita/contract
  - "Elternabend" → kita/events, education/parent-meeting
  - "Anmeldung" → education/enrollment, kita/registration

TOPIC ASSIGNMENT:
- Assign 8-15 topics (broad + specific)
- Use hierarchical paths: category/subcategory/detail
- Match German content to English vocabulary
- If no exact match, use suggested_topics

CONTROLLED VOCABULARY:
Topics: {available_topics}
Projects: {available_projects}
Places: {available_places}

Document content:
{content}
"""
```

#### 3.2 Multi-Pass Enrichment (Optional)

**For high-value documents:**
```python
# Pass 1: Fast extraction (Groq Llama 3.3 70B)
initial_enrichment = await enrich(content, temperature=0.3)

# Pass 2: Quality critique (if quality_score < 0.7)
if initial_enrichment.quality_score < 0.7:
    critique = await critique_enrichment(
        content,
        enrichment=initial_enrichment,
        model="anthropic/claude-3-5-sonnet"  # Higher quality
    )

    # Pass 3: Re-enrich with critique feedback
    final_enrichment = await enrich(
        content,
        previous_enrichment=initial_enrichment,
        critique_suggestions=critique.suggestions
    )
```

**Cost:** $0.00009 (pass 1) + $0.005 (passes 2-3 if needed) = ~$0.005 per low-quality doc

#### 3.3 Entity Alias Resolution

**Current:** Each mention creates separate entity
**Problem:** "Villa Luna", "Villa Luna gGmbH", "Villa Luna Köln" → 3 entities

**Solution:** Add alias resolution to `SmartTriageService`:

```python
def resolve_entity_aliases(self, entities: Dict) -> Dict:
    """
    Resolve entity aliases to canonical forms

    Examples:
    - "Villa Luna" / "Villa Luna gGmbH" → "Villa Luna Kindertagesstätten GmbH"
    - "Daniel T" / "Daniel Teckentrup" → "Daniel Teckentrup"
    - "Dr. Reul" / "Dr. Jürgen Reul" → "Dr. Jürgen Reul"
    """
    # Fuzzy matching + Levenshtein distance
    # Check against known_entities collection
    # Return canonical entity with mention_count++
```

**Benefit:** Cleaner entity list, accurate mention counts, better knowledge graph

---

## 4. Obsidian Layout Improvements

### Current State
- ✅ Markdown files with YAML frontmatter
- ✅ Auto-linking (WikiLinks to entities)
- ✅ Separate refs/ directory for entity pages
- ❌ No Obsidian templates
- ❌ No Dataview queries included
- ❌ refs/ subdirectories not used

### Proposed Improvements

#### 4.1 Obsidian Templates

**Create `.obsidian/templates/` in vault:**

**Email Template (`template_email.md`):**
```markdown
---
tags: [doc/email, inbox]
status: pending
priority: {{priority}}
---

# {{title}}

> [!summary]
> {{summary}}

## Quick Actions
- [ ] Respond
- [ ] File
- [ ] Archive

## Context
**From:** {{sender}}
**To:** {{recipients}}
**Date:** {{date}}

## Content
{{content}}

## Related Documents
```dataview
LIST
FROM #doc
WHERE contains(people, this.people)
SORT file.ctime DESC
LIMIT 5
```

## People Mentioned
```dataview
TABLE role, email
FROM "refs/persons"
WHERE file.name IN this.people
```
```

**Daily Note Template (`template_daily.md`):**
```markdown
---
date: {{date}}
tags: [daily-note]
---

# {{date}}

## Documents Ingested Today
```dataview
TABLE title, doc_type, people, topics
FROM #doc
WHERE ingested_at = date(this.file.name)
SORT file.ctime DESC
```

## Key People Active Today
```dataview
TABLE count(rows) as "Documents"
FROM #doc
WHERE ingested_at = date(this.file.name)
FLATTEN people as person
GROUP BY person
SORT rows.length DESC
LIMIT 10
```

## Topics Trending
```dataview
TABLE count(rows) as "Documents"
FROM #doc
WHERE ingested_at = date(this.file.name)
FLATTEN topics as topic
GROUP BY topic
SORT rows.length DESC
LIMIT 10
```
```

#### 4.2 Improved refs/ Directory Structure

**Current:**
```
refs/
├── persons/daniel-teckentrup.md
├── orgs/villa-luna.md
└── places/koln.md
```

**Proposed:**
```
refs/
├── persons/
│   ├── daniel-teckentrup.md
│   └── _index.md  (Dataview: all persons)
├── orgs/
│   ├── villa-luna-gmbh.md
│   └── _index.md  (Dataview: all orgs)
├── places/
│   ├── koln.md
│   └── _index.md  (Dataview: all places)
└── topics/
    ├── education-childcare.md
    └── _index.md  (Dataview: all topics)
```

**Index File Example (`refs/persons/_index.md`):**
```markdown
---
tags: [index, persons]
---

# People Index

```dataview
TABLE
    role as "Role",
    email as "Email",
    length(file.inlinks) as "Mentions"
FROM "refs/persons"
WHERE file.name != "_index"
SORT length(file.inlinks) DESC
```

## Most Active (Last 30 Days)
```dataview
TABLE
    count(rows) as "Documents"
FROM #doc
WHERE file.ctime >= date(today) - dur(30 days)
FLATTEN people as person
GROUP BY person
SORT rows.length DESC
LIMIT 20
```
```

#### 4.3 Obsidian Canvas for Timeline View

**Auto-generate canvas files for email threads:**

**File:** `threads/thread_ce10b3f0aadc.canvas`
```json
{
  "nodes": [
    {
      "id": "email1",
      "type": "file",
      "file": "2021-01-22__email__wunschkonzerte__1b3c.md",
      "x": 0,
      "y": 0,
      "width": 400,
      "height": 600
    },
    {
      "id": "email2",
      "type": "file",
      "file": "2021-01-25__email__re-wunschkonzerte__4c2f.md",
      "x": 500,
      "y": 0,
      "width": 400,
      "height": 600
    }
  ],
  "edges": [
    {
      "id": "reply1",
      "fromNode": "email1",
      "toNode": "email2",
      "label": "Reply"
    }
  ]
}
```

**Implementation:** `src/services/canvas_service.py` (new service)

---

## 5. RAG Retrieval Enhancements

### Current State
- ✅ Voyage-3-lite embeddings (fast, cheap)
- ✅ ChromaDB vector storage
- ✅ Metadata filtering
- ❌ No hybrid search (semantic + keyword)
- ❌ No reranking (disabled to save memory)
- ❌ No query expansion

### Test Results (100 emails)
```bash
Query: "Villa Luna kindergarten enrollment"
Results: 3 documents
Search time: 381ms
Relevance scores: 0.60, 0.51, 0.31
```

**Issues:**
- Third result low relevance (0.31)
- No BM25 keyword fallback
- No query expansion ("kindergarten" → "kita", "daycare")

### Proposed Improvements

#### 5.1 Hybrid Search (Semantic + BM25)

**Implementation in `src/services/vector_service.py`:**

```python
async def hybrid_search(
    self,
    query: str,
    top_k: int = 10,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3
) -> List[Document]:
    """
    Hybrid search combining:
    1. Semantic (vector) search
    2. BM25 keyword search
    3. Weighted fusion
    """
    # Semantic search (Voyage embeddings)
    semantic_results = await self.search(query, top_k=top_k*2)

    # BM25 keyword search (using rank-bm25 lib)
    keyword_results = self.bm25_search(query, top_k=top_k*2)

    # Reciprocal Rank Fusion (RRF)
    fused_results = self._fuse_results(
        semantic_results,
        keyword_results,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight
    )

    return fused_results[:top_k]
```

**Benefits:**
- Better recall (catches exact keyword matches)
- Better precision (semantic understands synonyms)
- 10-20% accuracy improvement (industry standard)

#### 5.2 Query Expansion

**Add German/English synonym expansion:**

```python
QUERY_EXPANSIONS = {
    "kindergarten": ["kita", "daycare", "preschool", "betreuung"],
    "enrollment": ["anmeldung", "registration", "sign-up"],
    "contract": ["vertrag", "agreement", "betreuungsvertrag"],
    "parent": ["eltern", "mother", "father", "mutter", "vater"],
}

def expand_query(query: str) -> str:
    """Expand query with synonyms"""
    expanded_terms = []
    for term in query.split():
        expanded_terms.append(term)
        if term.lower() in QUERY_EXPANSIONS:
            expanded_terms.extend(QUERY_EXPANSIONS[term.lower()])
    return " ".join(expanded_terms)
```

#### 5.3 Cloud Reranking (Voyage)

**Current:** Disabled (saves 3GB memory)
**Alternative:** Use Voyage reranking API (already integrated via LiteLLM)

```python
# After initial retrieval (get top 50)
initial_results = await search(query, top_k=50)

# Rerank with Voyage (costs ~$0.0001/query)
reranked = await litellm.rerank(
    model="voyage-rerank-2",
    query=query,
    documents=[r.content for r in initial_results],
    top_n=10
)

return reranked_results
```

**Cost:** $0.0001 per search query (acceptable for production)
**Benefit:** 15-25% accuracy improvement (Voyage benchmark)

---

## 6. LLM Suggestions at Ingestion Time

### Current State
- LLM sees document content + vocabulary
- Extracts metadata (topics, entities, dates)
- No "thinking out loud" or suggestions

### Proposed: LLM Reflection Field

**Add to `EnrichmentResponse` model:**

```python
class EnrichmentResponse(BaseModel):
    # ... existing fields ...

    llm_suggestions: Optional[str] = Field(
        default=None,
        description="LLM's observations, suggestions, or insights about this document (optional thinking out loud)",
        max_length=500
    )
```

**Update prompt:**

```python
ENRICHMENT_PROMPT_WITH_REFLECTION = """
...

OPTIONAL - LLM REFLECTION:
If you notice anything interesting about this document, you may add a brief note:
- Missing information that would be valuable
- Suggestions for follow-up
- Connections to other topics
- Quality concerns or OCR issues
- Proposed projects or vocabulary additions

Keep it under 2-3 sentences.
"""
```

**Example Output:**

```yaml
llm_suggestions: "This appears to be part of an ongoing enrollment process. Consider creating a 'Villa Luna Enrollment 2021' project to group related documents. The German term 'Wunschkonzert' (wish concert) is used metaphorically here."
```

**Use Cases:**
1. Suggest new projects based on document patterns
2. Identify document series (contracts, invoices, etc.)
3. Flag OCR quality issues
4. Suggest vocabulary additions
5. Note cross-document connections

**Cost Impact:** Minimal (part of existing enrichment call)

---

## Implementation Priority

### Phase 1: Quick Wins (1-2 hours)
1. ✅ Fix entity limit (20→50) - **DONE**
2. ✅ Fix attachment links error - **DONE**
3. ⏳ Add German daycare keywords to `vocabulary/topics.yaml`
4. ⏳ Update enrichment prompt with German keyword awareness

### Phase 2: Vocabulary Management (3-4 hours)
1. Create `suggested_topics.yaml` auto-save
2. Build `scripts/review_suggestions.py` tool
3. Add vocabulary hierarchy visualization
4. Add entity alias resolution to triage

### Phase 3: Obsidian UX (4-6 hours)
1. Implement new filename convention (E_date_title_hash.md)
2. Create Obsidian templates (email, daily note)
3. Improve refs/ directory structure with index files
4. Add Dataview queries to templates

### Phase 4: RAG Enhancements (6-8 hours)
1. Implement hybrid search (semantic + BM25)
2. Add query expansion (German/English synonyms)
3. Enable Voyage cloud reranking
4. Add search analytics/logging

### Phase 5: Enrichment Quality (4-6 hours)
1. Add LLM reflection field
2. Implement multi-pass enrichment (optional)
3. Enhanced German keyword prompting
4. Project auto-detection from patterns

---

## Success Metrics

### Phase 1 Target (Immediate)
- ✅ 0 failures from schema limits
- ⏳ <50% documents categorized as "archival"
- ⏳ 80%+ confidence scores on topic assignment

### Phase 2 Target (Vocabulary)
- ⏳ 20+ suggested topics captured per 100 docs
- ⏳ 90%+ vocabulary coverage (fewer suggested topics)
- ⏳ Monthly vocabulary growth rate: 5-10 new topics

### Phase 3 Target (Obsidian UX)
- ⏳ 100% files follow new naming convention
- ⏳ Templates used for all document types
- ⏳ Dataview queries working in vault

### Phase 4 Target (RAG Quality)
- ⏳ Hybrid search improves relevance by 15%+
- ⏳ Search time stays <500ms
- ⏳ Top-3 accuracy >80%

### Phase 5 Target (Enrichment)
- ⏳ LLM suggestions in 50%+ enrichments
- ⏳ 3+ projects auto-detected per 100 docs
- ⏳ Entity deduplication reduces entity count by 20%

---

## Best Practices Research

### Document Management Systems
- **Notion:** Uses `@` mentions for entity linking (similar to our WikiLinks)
- **Confluence:** Uses labels (tags) with hierarchy
- **SharePoint:** Uses managed metadata with term stores (like our controlled vocabulary)

### Knowledge Graphs
- **Obsidian Graph View:** Requires consistent linking (our auto-linking helps)
- **Roam Research:** Uses `[[]]` for bidirectional links (we use this)
- **Logseq:** Uses namespaces for hierarchy (similar to our `category/subcategory`)

### RAG Systems
- **LlamaIndex:** Uses hybrid search (semantic + keyword)
- **LangChain:** Uses query expansion and reranking
- **Pinecone:** Recommends sparse-dense hybrid for production

### Filename Conventions
- **ISO 8601 dates:** `YYYY-MM-DD` prefix for sorting
- **Type prefixes:** Common in medical records (LAB_, XRAY_, etc.)
- **Attachment numbering:** `_A01`, `_A02` standard in legal documents

---

## Cost Projections

### Current Costs (100 docs)
- Enrichment: $0.00846 (94 docs × $0.00009)
- Embeddings: ~$0.00005 (Voyage-3-lite)
- **Total:** $0.00851 per 100 docs

### With All Improvements
- Enrichment: $0.00846 (no change)
- Multi-pass (10% of docs): $0.05 (10 docs × $0.005)
- Reranking (all searches): $0.0001 per query
- **Total:** ~$0.06 per 100 docs (if multi-pass enabled)

### Cost vs Value
- **Hybrid search:** Free (uses existing BM25 lib)
- **Query expansion:** Free (dictionary lookup)
- **Vocabulary management:** Free (YAML files)
- **Obsidian improvements:** Free (templates + Dataview)
- **LLM reflection:** Free (included in enrichment call)

**Only paid additions:**
- Multi-pass enrichment: $0.005 per low-quality doc (optional)
- Voyage reranking: $0.0001 per search (minimal)

---

## Next Steps

1. **Immediate (Tonight):**
   - ✅ Fix entity limit - **DONE**
   - ✅ Fix attachment links - **DONE**
   - ⏳ Add German keywords to vocabulary
   - ⏳ Test with failed emails again

2. **This Week:**
   - ⏳ Implement new filename convention
   - ⏳ Create Obsidian templates
   - ⏳ Add hybrid search

3. **This Month:**
   - ⏳ Vocabulary management workflow
   - ⏳ Entity alias resolution
   - ⏳ LLM reflection field

4. **Nice to Have:**
   - ⏳ Obsidian Canvas timeline view
   - ⏳ Multi-pass enrichment
   - ⏳ Search analytics dashboard

---

**Document Version:** 1.0
**Last Updated:** October 16, 2025
**Status:** Draft - Ready for Implementation
