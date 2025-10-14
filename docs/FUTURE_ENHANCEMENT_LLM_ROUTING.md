# Smart Model Routing for Document Types

## Problem
LLM chat exports (ChatGPT, Claude conversations) are:
- **Long** - 50-100+ messages = 10K-50K tokens
- **Context-dependent** - Later messages reference earlier ones
- **Complex** - Multi-turn reasoning, code snippets, evolving solutions

**Current limitation:**
```python
# All documents use same model
model = "groq/llama-3.1-8b-instant"  # 8K context limit
```

For long conversations, content gets truncated → poor enrichment quality.

## Solution: Document-Aware Model Routing

### Strategy
```python
def select_enrichment_model(doc_type: str, content: str, metadata: dict) -> str:
    """
    Choose enrichment model based on document complexity

    Routing logic:
    1. Estimate token count
    2. Check document type
    3. Select appropriate model for context size + capability needed
    """

    # Estimate tokens (rough: 4 chars per token)
    estimated_tokens = len(content) // 4

    # LLM chats need capable models with large context
    if doc_type == "llm_chat":
        if estimated_tokens > 32000:
            # Very long conversation
            return "google/gemini-2.5-pro"  # 1M context, $1.25/M tokens
        elif estimated_tokens > 6000:
            # Medium conversation
            return "anthropic/claude-3-5-sonnet-20241022"  # 200K context, $3.00/M
        else:
            # Short conversation
            return "groq/llama-3.1-8b-instant"  # 8K context, $0.05/M

    # Email with attachments might be large
    elif doc_type == "email" and estimated_tokens > 6000:
        return "anthropic/claude-3-haiku-20240307"  # 200K context, $0.25/M

    # Standard documents - use fast/cheap model
    else:
        return "groq/llama-3.1-8b-instant"
```

### Context Limits Reference

| Model | Context | Input Cost | Best For |
|-------|---------|------------|----------|
| **Groq Llama-3.1-8B** | 8K | $0.05/M | Short docs, emails, PDFs |
| **Anthropic Haiku** | 200K | $0.25/M | Medium conversations, long emails |
| **Anthropic Sonnet** | 200K | $3.00/M | Complex analysis, high quality |
| **Google Gemini 2.5 Pro** | 1M | $1.25/M | Very long chats, full books |

### Cost Impact Analysis

**Scenario: 518 Villa Luna emails**
- Current (all Groq): ~$0.08
- With routing (20% use Haiku): ~$0.12 (+50% cost, better quality)

**Scenario: 100 LLM chat exports**
- Current (Groq, truncated): ~$0.05 (poor quality)
- With routing (Sonnet for long ones): ~$0.25 (5x cost, proper context)

**Verdict:** Small cost increase for MUCH better quality on complex docs.

## Implementation Plan

### Phase 1: Token-Based Routing (Simple)
```python
# In enrichment_service.py
def enrich_document(self, content, filename, document_type, ...):
    # Select model based on size
    model = self._select_model(document_type, content)

    llm_response, cost, model_used = await self.llm_service.call_llm_structured(
        prompt=prompt,
        response_model=EnrichmentResponse,
        model_id=model,  # Dynamic model selection
        temperature=0.1
    )
```

### Phase 2: Complexity-Based Routing (Advanced)
```python
# Check if LLM can handle the task
def assess_complexity(self, content: str, doc_type: str) -> dict:
    """
    Quick assessment: Can Groq handle this or do we need more capable model?

    Returns:
        {
            "needs_large_context": bool,
            "needs_high_capability": bool,
            "recommended_model": str
        }
    """

    # For LLM chats specifically
    if doc_type == "llm_chat":
        message_count = content.count(">>") + content.count("ASSISTANT:")
        has_code = "```" in content
        has_complex_reasoning = any(keyword in content.lower()
                                   for keyword in ["algorithm", "proof", "analysis"])

        if message_count > 50 or (has_code and has_complex_reasoning):
            return {
                "needs_large_context": True,
                "needs_high_capability": True,
                "recommended_model": "anthropic/claude-3-5-sonnet-20241022"
            }

    # Default: fast model
    return {
        "needs_large_context": False,
        "needs_high_capability": False,
        "recommended_model": "groq/llama-3.1-8b-instant"
    }
```

### Phase 3: Self-Assessment (LLM decides)
```python
# Let the LLM assess if it can handle the task
quick_assessment = await llm_service.call_llm(
    prompt=f"""Quick assessment: Can you properly analyze this {doc_type} document?

    Document length: {len(content)} chars
    Type: {doc_type}

    Respond ONLY with JSON:
    {{
        "can_handle": true/false,
        "reason": "why or why not",
        "recommended_model": "if can't handle, which model?"
    }}""",
    model_id="groq/llama-3.1-8b-instant",  # Fast assessment
    max_tokens=100
)

if not assessment["can_handle"]:
    # Route to recommended model
    model = assessment["recommended_model"]
```

## Benefits

1. **Cost-optimized** - Use cheap models when possible
2. **Quality-optimized** - Use capable models when needed
3. **Context-aware** - No truncation for long documents
4. **Automatic** - No manual configuration needed

## Testing Strategy

```python
# Test cases
test_cases = [
    {
        "name": "Short email",
        "content": "Hi, meeting at 3pm. Thanks!",
        "doc_type": "email",
        "expected_model": "groq/llama-3.1-8b-instant"
    },
    {
        "name": "Long LLM chat (100 messages)",
        "content": "..." * 20000,  # 80K chars
        "doc_type": "llm_chat",
        "expected_model": "anthropic/claude-3-5-sonnet-20241022"
    },
    {
        "name": "Very long conversation (200+ messages)",
        "content": "..." * 50000,  # 200K chars
        "doc_type": "llm_chat",
        "expected_model": "google/gemini-2.5-pro"
    }
]

for test in test_cases:
    selected = select_enrichment_model(test["doc_type"], test["content"], {})
    assert selected == test["expected_model"]
```

## Next Steps

- [ ] Implement token counting in enrichment_service.py
- [ ] Add model selection logic
- [ ] Update tests to cover routing
- [ ] Monitor cost impact (should be minimal for emails, higher for LLM chats)
- [ ] Measure quality improvement on long conversations

## Related Files

- `src/services/enrichment_service.py` - Add routing logic here
- `src/services/llm_service.py` - Already supports dynamic model selection ✅
- `tests/unit/test_enrichment_service.py` - Add routing tests
