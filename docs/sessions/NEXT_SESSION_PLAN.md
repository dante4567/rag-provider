# Next Session Plan - October 16, 2025

## Summary of Today's Work

✅ **Completed:**
1. Fixed dates extraction schema issue (ObsidianMetadata missing dates fields)
2. Fixed Dataview query syntax for date stubs
3. Tested 60 documents (30 emails + 30 chats)
4. Analyzed enrichment quality across 220 documents
5. Comprehensive RAG value-add analysis

**Key Metrics:**
- 220 documents enriched
- 0.89 average quality score
- 1,911 auto-generated WikiLinks
- 80%+ entity coverage
- Knowledge graph: 81 people, 88 orgs, 139 dates

---

## Issues Identified (To Fix Next Session)

### 1. Debug Reranking Model Loading 🔴 HIGH PRIORITY

**Problem:** PyTorch meta tensor error blocking search/chat endpoints

**Error:**
```
Cannot copy out of meta tensor; no data!
Please use torch.nn.Module.to_empty() instead of torch.nn.Module.to()
when moving module from meta to a different device.
```

**Impact:**
- `/search` returns 500 error
- `/chat` returns 500 error
- Cannot test RAG query functionality

**Where to Look:**
- `src/services/reranking_service.py` - Model loading code
- Line where model is moved to device
- Model: `mixedbread-ai/mxbai-rerank-large-v2`

**Debugging Steps:**
1. Check PyTorch version compatibility
2. Look at model loading in reranking_service.py
3. Try using `model.to_empty(device)` instead of `model.to(device)`
4. OR temporarily disable reranking: `ENABLE_RERANKING=false` in .env
5. Test search/chat endpoints after fix

**Files to Edit:**
- `src/services/reranking_service.py` (model loading)
- Possibly `.env` (temporary disable)

---

### 2. Better Entity Type Validation ⚠️ MEDIUM PRIORITY

**Problem:** Tools/software extracted as "people" entities

**Examples Found:**
- "Studio Code" (should be technology)
- "Virtual Machine" (should be technology)
- "Apple Calendar" (should be technology)
- "Jupyter Notebook" (should be technology)
- "State Summary" (should be ignored)
- "Native Install" (should be ignored)

**Impact:**
- Clutters person entity list (81 stubs, ~10 are false positives)
- Reduces entity accuracy
- Confusing in knowledge graph

**Where to Fix:**
- `src/services/enrichment_service.py` - Enrichment prompt
- Possibly add entity type classification validation

**Approach:**

**Option A: Improve Enrichment Prompt**
- Add explicit instruction: "Do NOT extract software tools, applications, or technical concepts as people"
- Add examples of what NOT to extract
- Emphasize: People = real persons only

**Option B: Post-Processing Filter**
- Create list of common tool names (VS Code, Docker, etc.)
- Filter out matches after extraction
- More maintainable

**Option C: Two-Stage Classification**
- First pass: Extract all entities
- Second pass: LLM classifies each as person/org/tech/place
- More accurate but costs more

**Recommendation:** Start with Option A (improve prompt), add Option B (filter) if needed

**Files to Edit:**
- `src/services/enrichment_service.py` (lines ~400-500, enrichment prompt)
- Possibly add `src/utils/entity_filters.py` for common tool names

---

## What to Test After Fixes

### Test Suite: 10 RAG Queries

Once reranking is fixed, test these queries to demonstrate RAG value:

#### Meta Questions (3)
1. "What are the main topics covered in my documents?"
2. "Who are the key people mentioned most frequently?"
3. "Which organizations appear most often?"

#### Timeline Queries (2)
4. "What important events are scheduled for November 2025?"
5. "What happened in April 2021?"

#### Entity Relationship Queries (2)
6. "Which documents mention both Villa Luna and Daniel Teckentrup?"
7. "What technologies are discussed with Linux?"

#### Topic-Specific Queries (2)
8. "Tell me about childcare administration and enrollment"
9. "What communications exist about COVID-19?"

#### Quality-Based Query (1)
10. "Show me recent high-quality documents"

**Test Script:**
- Use `/tmp/test_rag_manual_fixed.sh` (already created)
- Update with correct field name: `question` not `query`

---

## Files Modified Today

1. **src/models/schemas.py** (lines 164-166)
   - Added `dates` and `dates_detailed` fields to ObsidianMetadata

2. **src/services/rag_service.py** (lines 821-823)
   - Populate dates fields in ObsidianMetadata

3. **src/services/enrichment_service.py** (line 1300)
   - Added dates_detailed to extract_enriched_lists return

4. **src/services/obsidian_service.py** (line 997)
   - Fixed Dataview query: `WHERE contains(dates, "{name}")` (removed redundant `dates AND`)

**Commits:**
- a0274d4: Fix dates schema
- b50faeb: Fix Dataview query

---

## Quick Start Commands for Next Session

```bash
# 1. Check current status
docker-compose ps
curl http://localhost:8001/health | jq

# 2. View reranking service code
cat src/services/reranking_service.py | grep -A 20 "def.*load"

# 3. Test search endpoint (currently fails)
curl -s -X POST "http://localhost:8001/search" \
  -H "Content-Type: application/json" \
  -d '{"text": "Villa Luna", "top_k": 5}' | jq

# 4. If needed: Disable reranking temporarily
echo "ENABLE_RERANKING=false" >> .env
docker-compose restart rag-service

# 5. Run RAG evaluation after fix
bash /tmp/test_rag_manual_fixed.sh
```

---

## Success Criteria

### Fix 1: Reranking Model
- ✅ Search endpoint returns results (no 500 error)
- ✅ Chat endpoint returns answers (no 500 error)
- ✅ 10 test queries complete successfully

### Fix 2: Entity Validation
- ✅ No software tools in person entities
- ✅ Re-test with 10 documents
- ✅ Person list only contains real people

---

## Current System State

**Services Running:** ✅
- ChromaDB: Running
- RAG Service: Running (search/chat broken)
- Nginx: Running

**Data:**
- 220 documents enriched
- Obsidian vault: `/data/obsidian/`
- Archive: `/data/processed_originals/`

**Quality Metrics:**
- Average quality: 0.89
- Entity coverage: 80%+
- WikiLinks: 1,911 auto-created

**Known Issues:**
1. Reranking model PyTorch error 🔴
2. Entity type classification ⚠️
3. Date extraction (minor) ⚠️

---

## Priority Order for Next Session

1. 🔴 **Debug reranking model** (15-30 min) - BLOCKS core functionality
2. ✅ **Test search/chat endpoints** (10 min) - Verify fix works
3. 🧪 **Run 10 RAG test queries** (20 min) - Demonstrate value
4. ⚠️ **Fix entity type validation** (30 min) - Improve quality
5. 🧪 **Re-test entity extraction** (10 min) - Verify improvement

**Total Time Estimate:** 1.5-2 hours

---

## Reference Documents

- **Value Analysis:** `/tmp/rag_value_analysis.txt`
- **Evaluation Summary:** `/tmp/rag_evaluation_summary.md`
- **Test Script:** `/tmp/test_rag_manual_fixed.sh`
- **Query Set:** `/tmp/rag_evaluation_queries.json`

---

## Notes for Claude Next Session

- User wants comprehensive RAG evaluation with meta-questions
- Reranking issue is blocking search/chat functionality
- Entity type validation is quality improvement (not blocking)
- Focus on demonstrating RAG value-add once search/chat working
- User is happy with enrichment quality overall (0.89 score)
