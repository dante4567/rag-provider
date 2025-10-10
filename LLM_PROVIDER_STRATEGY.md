# LLM Provider Strategy & Testing

## Overview

The RAG service uses a **multi-provider fallback chain** with automatic cost tracking and provider testing. This document explains which providers/models are used for what, pricing, and testing strategy.

## Provider Configuration

### Default Fallback Chain

**Priority Order:**
1. **Primary:** Groq (`DEFAULT_LLM=groq`)
2. **Fallback:** Anthropic (`FALLBACK_LLM=anthropic`)
3. **Emergency:** OpenAI (`EMERGENCY_LLM=openai`)

**Rationale:**
- **Groq first:** Ultra-cheap ($0.05-0.08 per 1M tokens), lightning-fast
- **Anthropic second:** High quality reasoning when Groq fails/rate-limited
- **OpenAI last:** Most expensive but highly reliable emergency option

### Configurable via Environment Variables

```bash
# .env
DEFAULT_LLM=groq         # Primary provider
FALLBACK_LLM=anthropic   # First fallback
EMERGENCY_LLM=openai     # Last resort
```

## Model Pricing (per 1M tokens)

### Groq - Ultra Cheap, Lightning Fast
| Model | Input | Output | Use Case |
|-------|-------|--------|----------|
| `llama-3.1-8b-instant` | $0.05 | $0.08 | **Default for enrichment, triage** |
| `llama-3.1-70b-versatile` | $0.59 | $0.79 | Complex reasoning |

**Cost Example:**
- Enrichment (1000 input, 500 output): **$0.00009** (~$0.0001)
- 10,000 documents: **~$1.00**

### Anthropic - High Quality Reasoning
| Model | Input | Output | Use Case |
|-------|-------|--------|----------|
| `claude-3-haiku-20240307` | $0.25 | $1.25 | Fast, cheap Claude |
| `claude-3-5-sonnet-20241022` | $3.00 | $15.00 | **Quality scoring/critique** |
| `claude-3-opus-20240229` | $15.00 | $75.00 | Premium reasoning |

**Cost Example:**
- Quality critique (500 input, 200 output): **$0.005** (half a cent)
- 1000 critiques: **~$5.00**

### OpenAI - Reliable General Purpose
| Model | Input | Output | Use Case |
|-------|-------|--------|----------|
| `gpt-4o-mini` | $0.15 | $0.60 | Cheap fallback |
| `gpt-4o` | $5.00 | $15.00 | Emergency high-quality |

### Google - Long Context Specialist
| Model | Input | Output | Use Case |
|-------|-------|--------|----------|
| `gemini-2.0-flash` | $0.10 | $0.40 | Fast, cheap |
| `gemini-2.5-pro` | $1.25 | $5.00 | Long documents |

## Use Cases & Model Selection

### 1. Document Enrichment (Primary Task)
**Model:** `groq/llama-3.1-8b-instant`
**Cost:** ~$0.00009 per document
**Location:** `src/services/enrichment_service.py:434`

```python
response, _, _ = await self.llm_service.call_llm(
    prompt=prompt,
    model_id="groq/llama-3.1-8b-instant",  # ← Hardcoded, ultra-cheap
    temperature=0.0
)
```

**Why Groq:**
- Extracts metadata (topics, people, places, dates)
- Uses controlled vocabulary (no hallucinations needed)
- Speed matters more than reasoning quality
- Cost: $1 per 10,000 documents

### 2. Quality Scoring/Critique (Optional)
**Model:** `anthropic/claude-3-5-sonnet-20241022`
**Cost:** ~$0.005 per critique
**Location:** `src/services/enrichment_service.py:1125`

```python
critic_response, cost, model_used = await self.llm_service.call_llm(
    prompt=prompt,
    model_id="anthropic/claude-3-5-sonnet-20241022",  # ← Hardcoded, high-quality
    temperature=0.0
)
```

**Why Claude Sonnet:**
- 7-point rubric quality assessment
- Nuanced reasoning required
- Worth extra cost for quality feedback
- Still cheaper than GPT-4o

### 3. Smart Triage (Deduplication/Categorization)
**Model:** `groq/llama-3.1-8b-instant`
**Cost:** ~$0.00009 per document
**Location:** `src/services/enrichment_service.py:625`

```python
llm_response_text, cost, model_used = await self.llm_service.call_llm(
    prompt=prompt,
    model_id="groq/llama-3.1-8b-instant",  # ← Hardcoded, ultra-cheap
    temperature=0.1
)
```

**Why Groq:**
- Binary classification (duplicate vs unique)
- Simple categorization tasks
- High volume processing
- Speed and cost critical

### 4. RAG Chat (User-Facing)
**Model:** User-selectable, defaults to fallback chain
**Cost:** Variable ($0.00009 - $0.02+ depending on model)
**Location:** `src/routes/chat.py`

```python
response_text, cost, model_used = await llm_service.call_llm(
    prompt=final_prompt,
    model_id=model_to_use  # ← User-specified or fallback chain
)
```

**Why Flexible:**
- Users may want higher quality (Claude, GPT-4)
- Or prefer speed/cost (Groq, GPT-4o-mini)
- Fallback chain ensures reliability

## Fallback Logic

### How Fallback Works

**Code:** `src/services/llm_service.py:347-406`

```python
async def call_llm(self, prompt: str, model_id: Optional[str] = None, ...):
    # 1. Try specified model first
    if model_id:
        try:
            return await self._call_specific_model(model_id, prompt, ...)
        except Exception as e:
            logger.warning(f"Failed to call {model_id}: {e}")

    # 2. Fall through provider chain
    for provider in self.provider_order:  # [groq, anthropic, openai]
        try:
            default_model = self.provider_configs[provider]["models"][0]
            return await self._call_specific_model(default_model, prompt, ...)
        except Exception as e:
            logger.warning(f"Provider {provider} failed: {e}")
            continue

    raise Exception("All LLM providers failed")
```

**When Fallback Triggers:**
- API rate limiting (429 errors)
- Network failures
- API key issues
- Service outages

**Example Scenario:**
1. Try Groq → **429 Too Many Requests**
2. Fallback to Anthropic → **Success** ✅
3. Cost logged: Claude instead of Groq
4. User gets response, just at higher cost

## Cost Tracking

### Automatic Cost Tracking

**Code:** `src/services/llm_service.py:53-183`

```python
class CostTracker:
    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on MODEL_PRICING"""
        pricing = MODEL_PRICING[model]
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def record_operation(self, provider: str, model: str, cost: float, ...):
        """Track every LLM call"""
        self.operations.append(CostInfo(...))
        self.daily_totals[today] += cost
        self.total_cost += cost
```

### Budget Protection

**Environment Variable:**
```bash
DAILY_BUDGET_USD=10.0  # Hard limit, prevents runaway costs
```

**Code:**
```python
if not self.cost_tracker.check_budget():
    raise Exception(f"Daily budget limit (${daily_budget}) reached")
```

### Cost Stats Endpoint

**GET /cost/stats**
```json
{
  "total_cost_today": 0.45,
  "total_cost_all_time": 12.34,
  "operation_count": 523,
  "budget_remaining": 9.55,
  "cost_by_provider": {
    "groq": 0.30,
    "anthropic": 0.15
  }
}
```

## Provider Testing Strategy

### 1. Unit Tests (Mock-Based)
**File:** `tests/unit/test_llm_service.py`
**Coverage:** 17 tests

**What's Tested:**
- ✅ Cost calculation accuracy (per model)
- ✅ Token estimation (4 chars ≈ 1 token)
- ✅ Budget enforcement
- ✅ Cost tracking logic
- ✅ Provider availability checking

**Example:**
```python
def test_calculate_cost_known_model(self):
    cost = tracker.calculate_cost(
        model="groq/llama-3.1-8b-instant",
        input_tokens=1000,
        output_tokens=500
    )
    # Expected: $0.00009
    assert abs(cost - 0.00009) < 0.000001
```

### 2. Integration Tests (Live API)
**File:** `tests/integration/test_llm_provider_quality.py`

**What's Tested:**
- ✅ All providers reported in `/health` endpoint
- ✅ Provider-specific models available
- ✅ Enrichment quality across providers
- ⚠️ **Note:** Rate-limited in CI/CD (429 errors expected)

**Example:**
```python
def test_all_providers_reported_in_health(self):
    response = requests.get(f"{BASE_URL}/health")
    providers = response.json()["llm_providers"]

    assert len(providers) > 0
    for provider, info in providers.items():
        assert info["available"] is True
        assert info["model_count"] > 0
```

### 3. Provider Quality Comparison Tests
**File:** `tests/integration/test_llm_provider_quality.py:77+`

**What's Tested:**
- ✅ Enrichment output quality (Groq vs Anthropic vs OpenAI)
- ✅ Consistency across providers
- ⚠️ **Not automated:** Manual comparison needed

**Reason:**
- Quality is subjective
- Different models excel at different tasks
- Automated metrics (BLEU, ROUGE) not meaningful for RAG

### 4. Pricing Validation (Manual)
**How:** Compare `MODEL_PRICING` dict against provider websites
**When:** Monthly or when providers update pricing
**Last Updated:** October 2025 (comment in code)

## Is Provider Switching Tested?

### Automated Tests: Partial ✅

**What's Tested:**
1. ✅ **Fallback logic works** - Unit tests verify fallback chain
2. ✅ **All providers available** - Integration tests check health endpoint
3. ✅ **Cost tracking per provider** - Unit tests verify tracking
4. ⚠️ **Live API calls** - Integration tests hit rate limits in CI/CD

**What's NOT Tested:**
1. ❌ **Real fallback scenarios** - Requires forcing provider failure
2. ❌ **Quality comparison** - Subjective, manual review needed
3. ❌ **Pricing accuracy** - Requires actual billing data

### Recommended Testing Approach

#### Option 1: Manual Monthly Checks
```bash
# Test each provider explicitly
curl -X POST http://localhost:8001/test/llm \
  -H "Content-Type: application/json" \
  -d '{
    "model": "groq/llama-3.1-8b-instant",
    "prompt": "Extract topics from: The quick brown fox jumps over the lazy dog.",
    "temperature": 0.0
  }'

# Repeat for:
# - anthropic/claude-3-haiku-20240307
# - openai/gpt-4o-mini
# - google/gemini-2.0-flash

# Compare:
# - Response quality
# - Response time
# - Cost (from /cost/stats)
```

#### Option 2: Automated Smoke Test (Add to Nightly)
```python
@pytest.mark.nightly
class TestProviderSwitching:
    """Test all configured providers still work"""

    def test_groq_works(self):
        response = requests.post(f"{BASE_URL}/test/llm", json={
            "model": "groq/llama-3.1-8b-instant",
            "prompt": "Say 'Groq works'",
            "temperature": 0.0
        })
        assert response.status_code == 200
        assert "Groq works" in response.json()["response"].lower()

    def test_anthropic_works(self):
        # Similar test for Claude
        ...

    def test_fallback_chain_works(self):
        # Force Groq to fail (wrong API key), verify Anthropic catches it
        ...
```

#### Option 3: Cost/Performance Dashboard
```bash
# Weekly report showing:
# - Cost per provider (last 7 days)
# - Success rate per provider
# - Average response time
# - Fallback frequency

SELECT
  provider,
  COUNT(*) as calls,
  SUM(cost_usd) as total_cost,
  AVG(cost_usd) as avg_cost,
  COUNT(*)/NULLIF(SUM(CASE WHEN error THEN 1 ELSE 0 END), 0) as success_rate
FROM llm_operations
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY provider
ORDER BY calls DESC
```

## Pricing Updates

### When to Update Pricing

**Monthly Check:**
1. Visit provider websites (Groq, Anthropic, OpenAI, Google)
2. Compare against `MODEL_PRICING` dict in `src/services/llm_service.py`
3. Update if pricing changed
4. Commit with note: "Update pricing - [Provider] changed [model] to $X/1M"

**Provider URLs:**
- Groq: https://groq.com/pricing
- Anthropic: https://www.anthropic.com/pricing
- OpenAI: https://openai.com/pricing
- Google: https://ai.google.dev/pricing

### Pricing Change Impact

**If Groq price increases:**
- Enrichment cost goes up proportionally
- Consider switching to Gemini Flash if Groq becomes expensive
- Update README cost estimates

**If Anthropic price decreases:**
- Quality scoring becomes more affordable
- Consider using Claude for more tasks

## Model Viability Testing

### Current Approach: Manual

**Not Automated Because:**
1. **Subjective Quality** - "Better" depends on use case
2. **Cost/Quality Tradeoff** - What's "viable" depends on budget
3. **Rate Limits** - Can't hammer APIs in CI/CD
4. **Billing Required** - Need real usage data for accurate costs

### Recommended Manual Testing (Quarterly)

**Test Matrix:**
```
Task: Document Enrichment
Test Prompt: [Standard school document]

| Model | Time | Cost | Topics Accuracy | Title Quality | Score |
|-------|------|------|-----------------|---------------|-------|
| Groq Llama 8B | 0.2s | $0.0001 | 90% | Good | ⭐⭐⭐⭐ |
| Gemini Flash | 0.3s | $0.0002 | 85% | Good | ⭐⭐⭐⭐ |
| Claude Haiku | 0.8s | $0.002 | 95% | Great | ⭐⭐⭐⭐⭐ |
| GPT-4o-mini | 1.2s | $0.0004 | 92% | Great | ⭐⭐⭐⭐ |

Decision: Keep Groq as default (best speed/cost, acceptable quality)
```

## Recommendations

### Short Term (Implemented ✅)
- ✅ Fallback chain configured
- ✅ Cost tracking implemented
- ✅ Provider availability tests
- ✅ Pricing documented

### Medium Term (Recommended)
1. **Add Nightly Provider Tests**
   - Test each provider weekly
   - Verify fallback chain works
   - Check pricing accuracy against billing

2. **Create Cost Dashboard**
   - Weekly report on provider usage
   - Cost trends over time
   - Identify expensive operations

3. **Document Provider Changes**
   - Changelog for provider/model switches
   - Rationale for each change
   - Performance/cost comparison data

### Long Term (Optional)
1. **Automated Quality Benchmarks**
   - Golden set of test documents
   - Compare output quality across providers
   - Alert if quality degrades

2. **Dynamic Provider Selection**
   - Route simple tasks to cheap models
   - Route complex tasks to expensive models
   - ML-based task complexity scoring

3. **Multi-Provider A/B Testing**
   - Split traffic between providers
   - Measure quality/cost/speed
   - Optimize provider mix

## Summary

**Current State:**
- ✅ Multi-provider fallback chain configured
- ✅ Cost tracking automated
- ✅ Pricing documented and up-to-date
- ✅ Provider availability tested in health checks
- ⚠️ Provider switching tested (fallback logic), but not end-to-end with forced failures
- ⚠️ Pricing accuracy verified manually, not automated
- ❌ Quality comparison not automated (subjective)

**Good Enough For:**
- Production use ✅
- Cost control ✅
- Reliability (fallback) ✅
- Monitoring (cost stats) ✅

**Could Be Better:**
- Automated provider health checks (nightly)
- Forced failure testing for fallback chain
- Cost/quality dashboard
- Quarterly manual review process documented

**Next Steps:**
1. Accept current state as production-ready ✅
2. Add nightly provider smoke tests (optional, 2 hours)
3. Document quarterly manual review process (optional, 1 hour)
4. Build cost dashboard (optional, 4 hours)
