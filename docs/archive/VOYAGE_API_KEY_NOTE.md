# Embedding Model Switch - Voyage → Local Sentence-Transformers

**Date:** 2025-10-12
**Issue:** VOYAGE_API_KEY not configured, OpenAI API key didn't have embedding access
**Solution:** ✅ Switched to local sentence-transformers (completely free, no API keys)

## Background

The system was originally configured to use **Voyage-3-lite** embeddings for optimal cost/quality:
- **Cost:** $0.02/1M tokens
- **Dimensions:** 512
- **Quality:** MTEB score 68.8
- **Requires:** Voyage API key from https://dash.voyageai.com/

## Final Solution

**Switched to sentence-transformers** (`all-MiniLM-L6-v2`) - local embeddings:
- ✅ **Completely free** - no API costs whatsoever
- ✅ **No API keys required** - runs locally in Docker container
- ✅ **Privacy-first** - documents never leave your infrastructure
- ✅ **Already installed** - sentence-transformers==5.1.1 in requirements
- ✅ **Good quality** - MTEB score 56.3 (decent for most use cases)
- ✅ **Faster inference** - no network latency
- ✅ **Smaller vectors** - 384 dims vs 512 (Voyage) or 1536 (OpenAI)

## Performance Comparison

| Model | Cost | Dims | MTEB | API Key | Privacy |
|-------|------|------|------|---------|---------|
| Voyage-3-lite | $0.02/1M | 512 | 68.8 | Required | Cloud |
| OpenAI ada-002 | $0.10/1M | 1536 | 61.0 | Required | Cloud |
| **all-MiniLM-L6-v2** | **FREE** | **384** | **56.3** | **None** | **Local** |

## Testing Results

✅ **End-to-end ingestion working:**

```bash
curl -X POST http://localhost:8001/ingest/file -F "file=@test.txt"
# Result:
{
  "success": true,
  "doc_id": "54add999-d06b-49f3-b914-32d7edb1920a",
  "chunks": 1,
  "title": "Phase 1 Test Document",
  "topics": ["business/finance", "business/operations", "technology/api"],
  "summary": "..."
}
```

## Why This Is Better for Development

1. **No account signup needed** - works out of the box
2. **No billing concerns** - zero cost regardless of volume
3. **No rate limits** - process as fast as hardware allows
4. **No outages** - doesn't depend on external API availability
5. **Data stays local** - GDPR/privacy compliance easier

## When to Consider Upgrading

**Stick with sentence-transformers if:**
- Collection size < 1M documents
- Quality score 56.3 is acceptable for your use case
- Privacy/data locality is important
- Zero cost is a priority

**Upgrade to Voyage-3-lite if:**
- Need highest retrieval quality (+12.5 MTEB points)
- Collection size > 1M documents (storage savings matter)
- Willing to pay $0.02/1M tokens
- Don't mind cloud API dependency

## How to Switch to Voyage (Optional)

1. **Sign up:** https://dash.voyageai.com/
2. **Get API key** (free tier available)
3. **Add to `.env`:**
   ```bash
   VOYAGE_API_KEY=pa-xxxxxxxxxxxxxxxxxxxxx
   ```
4. **Update** `src/services/rag_service.py` line 310-330:
   ```python
   # Replace sentence-transformers code with Voyage code
   # See git commit history for original Voyage implementation
   ```
5. **Rebuild ChromaDB** (dimension change 384 → 512):
   ```bash
   docker-compose down
   docker volume rm rag-provider_chromadb_data
   docker-compose build rag-service
   docker-compose up -d
   ```

## Files Modified

- `src/services/rag_service.py` - Lines 310-330 (embedding function)

## Recommendation

✅ **Use sentence-transformers** for development/testing and small-to-medium production (< 1M docs)

⚡ **Upgrade to Voyage-3-lite** only if you need the extra 12 MTEB points for quality-critical applications

---

**Current Status:** Fully functional with local embeddings, zero API costs, complete privacy.
