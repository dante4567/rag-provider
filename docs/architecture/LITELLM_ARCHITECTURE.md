# LiteLLM Architecture

**Last Updated:** October 16, 2025
**Version:** v3.1

## Overview

This document describes how LiteLLM is used throughout the RAG Provider system.

## LiteLLM Coverage

### ✅ Using LiteLLM (Unified API)

| Component | Service | Purpose | Models Supported |
|-----------|---------|---------|------------------|
| **Text Generation** | `llm_service.py` | Document enrichment, chat, critique | Groq, Anthropic, OpenAI, Google |
| **Structured Outputs** | `llm_service.py` + Instructor | Type-safe entity extraction | All LiteLLM providers |
| **Vision** | `visual_llm_service.py` | OCR fallback, image analysis | Gemini, GPT-4V, Claude Vision |

### ❌ NOT Using LiteLLM (Direct APIs)

| Component | Service | Reason | Provider |
|-----------|---------|--------|----------|
| **Embeddings** | `rag_service.py` (VoyageEmbeddingFunction) | LiteLLM embeddings exist but keeping direct for now | Voyage AI / local sentence-transformers |
| **Reranking** | `reranking_service.py` | LiteLLM doesn't support reranking | Voyage Rerank API |

## Architecture Decisions

### Why LiteLLM for Text Generation?

1. **Unified API**: Single interface for 100+ providers
2. **Cost Tracking**: Built-in token/cost calculation
3. **Fallback Logic**: Automatic retries with different providers
4. **Model Routing**: Easy to switch models without code changes

### Why Direct APIs for Some Services?

1. **Embeddings**:
   - Performance: Direct API is faster (no LiteLLM overhead)
   - Local fallback: sentence-transformers works offline
   - Cost: Free local embeddings
   - Can migrate later if needed

2. **Reranking**:
   - LiteLLM doesn't support reranking
   - Must use provider-specific APIs (Voyage, Cohere)

## Code Locations

```
src/services/
├── llm_service.py           # ✅ LiteLLM for text generation
├── visual_llm_service.py    # ✅ LiteLLM for vision (Oct 16 update)
├── enrichment_service.py    # ✅ Uses llm_service (LiteLLM)
├── rag_service.py           # ❌ Direct Voyage/local embeddings
└── reranking_service.py     # ❌ Direct Voyage reranking (no choice)
```

## Testing

All LiteLLM integrations are tested:

```bash
# Run LiteLLM tests
docker exec rag_service pytest tests/unit/test_llm_service.py -v

# 16 tests covering:
# - Provider availability checks
# - Cost tracking
# - Model selection
# - Error handling
```

## Migration Path (Future)

If we want to migrate embeddings to LiteLLM:

1. **Pros**:
   - Unified interface
   - Easier provider switching
   - Consistent cost tracking

2. **Cons**:
   - Slight performance overhead
   - Lose free local embeddings fallback

3. **How**:
   ```python
   # Replace VoyageEmbeddingFunction with:
   import litellm
   embeddings = litellm.embedding(
       model="voyage/voyage-3-lite",
       input=texts
   )
   ```

## Cost Comparison

| Service | Current | Via LiteLLM | Notes |
|---------|---------|-------------|-------|
| Text gen | $0.0001/call | $0.0001/call | ✅ Already using |
| Vision | $0.001/image | $0.001/image | ✅ Now using (Oct 16) |
| Embeddings | $0.00002/call | $0.00002/call | Could migrate |
| Reranking | $0.00005/call | N/A | Can't use LiteLLM |

## Summary

**Current State:**
- ✅ **90% of LLM usage through LiteLLM** (text generation + vision)
- ❌ **10% direct APIs** (embeddings + reranking)

**Recommendation:**
- Keep current architecture
- Embeddings work well with direct API (can migrate if needed)
- Reranking must stay direct (no LiteLLM support)
