# Test What Exists - 30 Minute Guide

**Goal:** Validate that Enrichment V2 foundation works correctly

---

## Step 1: Start Docker (5 min)

```bash
# Build with latest code
docker-compose build rag-service

# Start services
docker-compose up rag-service
```

**Expected logs:**
```
✅ Enrichment V2 initialized with controlled vocabulary
   📚 Topics: 32
   🏗️  Projects: 2
   📍 Places: 13
   🎯 Using Enrichment V2 (controlled vocabulary)
```

**If you see errors:** Stop and show me the error message

---

## Step 2: Health Check (2 min)

```bash
curl http://localhost:8001/health | jq
```

**Look for:**
```json
{
  "status": "healthy",
  "llm_providers": {
    "anthropic": {"available": true, ...},
    "groq": {"available": true, ...}
  }
}
```

---

## Step 3: Upload Test Document (5 min)

Create a test file:

```bash
cat > /tmp/test_school_info.txt << 'EOF'
# Florianschule Information Evening

The Florianschule in Essen is holding an information evening on October 2, 2025.

This is an important opportunity for parents to learn about the school's educational concept and enrollment procedures for the 2026 school year.

Parents can register by contacting: enrollment@florianschule-essen.de

The event will take place at:
Florianschule Essen
Hauptstraße 123
45127 Essen
EOF
```

Upload it:

```bash
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@/tmp/test_school_info.txt" \
  -F "generate_obsidian=true" | jq
```

---

## Step 4: Check Response Quality (10 min)

**What to look for in the response:**

### ✅ Good Signs (V2 Working)

```json
{
  "success": true,
  "metadata": {
    "title": "Florianschule Information Evening",  // NOT "Untitled"
    "topics": "school/admin,school/info-day",      // From controlled vocab
    "places": "Essen",                             // Detected
    "projects": "school-2026",                     // Auto-matched!
    "organizations": "Florianschule",              // Extracted
    "quality_score": 0.85,                         // Scored
    "recency_score": 0.99,                         // Very recent
    "enrichment_version": "2.0"                    // Using V2
  },
  "obsidian_path": "/data/obsidian/20251005_Florianschule_Information_abc123.md"
}
```

### ❌ Bad Signs (V2 Not Working)

```json
{
  "metadata": {
    "title": "Untitled",                           // ❌ Old title extraction
    "topics": "education,events,school-systems",   // ❌ Invented tags
    "enrichment_version": "v2.1"                   // ❌ Old enrichment
  }
}
```

---

## Step 5: Verify Obsidian Export (5 min)

Check the generated Obsidian file:

```bash
# Find the file
docker exec rag-service ls -la /data/obsidian/

# View it
docker exec rag-service cat /data/obsidian/20251005_Florianschule*.md
```

**Look for:**

### ✅ Good YAML

```yaml
---
id: 20251005_abc123
title: Florianschule Information Evening
type: text                              # ✅ NOT "DocumentType.text"
topics:                                  # ✅ YAML list
  - school/admin
  - school/info-day
places:
  - Essen
projects:                                # ✅ Auto-matched
  - school-2026
entities:
  organizations:
    - Florianschule
quality_score: 0.85
recency_score: 0.99
---

project:: [[school-2026]]               # ✅ Dataview field

## Summary
The Florianschule in Essen...
```

### ❌ Bad YAML

```yaml
type: DocumentType.text                  # ❌ Python enum leaked
topics: "school/admin,school/info-day"   # ❌ String instead of list
projects: ['school-2026']                # ❌ Python syntax
```

---

## Step 6: Test Chat Retrieval (3 min)

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "wann ist der informationsabend",
    "max_context_chunks": 5,
    "include_sources": true
  }' | jq
```

**Expected:**

```json
{
  "answer": "Der Informationsabend an der Florianschule findet am 2. Oktober 2025 statt.",
  "sources": [
    {
      "metadata": {
        "title": "Florianschule Information Evening",  // ✅ Real title
        "topics": "school/admin,school/info-day",
        "recency_score": 0.99
      }
    }
  ],
  "cost_usd": 0.012
}
```

---

## Success Criteria Checklist

After running all steps, check:

### Must Have (V2 Foundation)
- [ ] Docker starts without errors
- [ ] Logs show "Enrichment V2 initialized"
- [ ] Health check returns 200
- [ ] Document upload succeeds

### V2 Features Working
- [ ] Title is NOT "Untitled" (4-strategy extraction working)
- [ ] Topics are from controlled vocabulary (no invented tags)
- [ ] Project auto-matched to "school-2026" (watchlist working)
- [ ] `enrichment_version` is "2.0"
- [ ] Obsidian YAML is clean (no `DocumentType.text`)
- [ ] Recency score is high (~0.99 for today's doc)

### Retrieval Working
- [ ] Chat returns correct answer
- [ ] Source has proper title (not "Untitled")
- [ ] Cost displayed correctly

---

## What to Do Next

### If Everything ✅ (All Checks Pass)

**Celebrate!** You have:
- Zero tag contamination (controlled vocabulary)
- Better titles (4-strategy extraction)
- Time awareness (recency scoring)
- Auto-organization (project matching)
- Clean Obsidian exports

**Next steps:**
1. Review `docs/future_roadmap_v2.0.md`
2. Pick Tier 1 priority (biggest impact):
   - Structure-aware chunking (precision boost)
   - Feedback system (curation power)
   - Hybrid retrieval (BM25 + embeddings)

### If Partial ⚠️ (Some Checks Fail)

**Tell me:**
- Which checks failed
- Copy the error messages/responses
- I'll help debug

### If Nothing Works ❌

**Don't panic!** Possible issues:
1. V2 not enabled: Check logs for "V2 initialized"
2. Vocabulary files missing: `docker exec rag-service ls vocabulary/`
3. Import errors: Check Docker build logs

**Send me:**
```bash
# Container logs
docker logs rag-service 2>&1 | tail -50

# Check vocabulary
docker exec rag-service ls -la vocabulary/

# Test vocabulary directly
docker exec rag-service python3 test_vocabulary.py
```

---

## Time Budget

| Step | Time | Total |
|------|------|-------|
| 1. Start Docker | 5 min | 5 min |
| 2. Health check | 2 min | 7 min |
| 3. Upload doc | 5 min | 12 min |
| 4. Check response | 10 min | 22 min |
| 5. Verify Obsidian | 5 min | 27 min |
| 6. Test chat | 3 min | 30 min |

**Total: 30 minutes**

---

## Quick Reference

**Documents:**
- **Testing guide:** `docs/v2_integration_testing_guide.md` (comprehensive)
- **Roadmap:** `docs/future_roadmap_v2.0.md` (all future ideas)
- **Integration:** `docs/phase_3_integration_summary.md` (what was done)
- **This file:** `TESTING_NOW.md` (quick 30-min test)

**Commands:**
```bash
# Start
docker-compose up rag-service

# Health
curl http://localhost:8001/health | jq

# Upload
curl -X POST http://localhost:8001/ingest/file -F "file=@test.txt" | jq

# Chat
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "your question"}' | jq

# Check vocabulary
docker exec rag-service python3 test_vocabulary.py

# View logs
docker logs rag-service
```

---

**Ready?** Run Step 1 and let me know what happens!
