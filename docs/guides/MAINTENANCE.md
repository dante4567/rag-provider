# Model Pricing & Selection Maintenance Guide

## Overview

This system uses multiple LLM providers with specific pricing. To ensure cost-effectiveness and quality, model choices and pricing should be reviewed **monthly**.

## Philosophy: Quality First

**We prioritize quality improvements and are willing to pay more for significant gains.**

- ✅ Switch to better models if quality improvement is substantial
- ✅ Accept higher costs for meaningful quality gains (critique, reasoning)
- ✅ Test new models aggressively (monthly reviews)
- ✅ Balance cost vs quality, but quality wins when there's real improvement

## Automated Reminders

### GitHub Actions Workflow

A GitHub Actions workflow (`.github/workflows/monthly-model-review.yml`) automatically:
- Runs **monthly** on the 1st of each month at 9 AM UTC
- Executes `scripts/check_model_pricing.py`
- Creates a GitHub Issue with checklist and report
- Uploads report as artifact

**To manually trigger:**
```bash
# Via GitHub UI: Actions → Monthly Model Review Reminder → Run workflow

# Or locally:
python scripts/check_model_pricing.py
```

## Manual Review Process

### 1. Run the Check Script

```bash
python scripts/check_model_pricing.py
```

This generates a report with:
- Current model inventory
- Hardcoded model locations
- Provider pricing URLs
- New model suggestions
- Monthly review checklist

### 2. Verify Current Pricing

Visit these URLs and compare against `MODEL_PRICING` in `src/services/llm_service.py`:

| Provider | URL | Current Models |
|----------|-----|----------------|
| **Groq** | https://groq.com/pricing | llama-3.1-8b-instant, llama-3.1-70b-versatile |
| **Anthropic** | https://www.anthropic.com/pricing | claude-3-haiku, claude-3-5-sonnet, claude-3-opus |
| **OpenAI** | https://openai.com/pricing | gpt-4o-mini, gpt-4o, gpt-4-turbo |
| **Google** | https://ai.google.dev/pricing | gemini-1.5-pro, gemini-2.0-flash, gemini-2.5-pro |

### 3. Update Pricing (if changed)

**File:** `src/services/llm_service.py`

```python
# Model pricing (per 1M tokens)
# Last updated: YYYY-MM-DD  ← Update this date
# Next review: YYYY-MM-DD (quarterly)
MODEL_PRICING = {
    "groq/llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},  ← Update if changed
    # ...
}
```

**Steps:**
1. Update pricing values
2. Update `Last updated:` timestamp
3. Update `Next review:` to +3 months
4. Save file

### 4. Check for New Models

Check provider documentation for new models:

| Provider | Docs URL | What to Look For |
|----------|----------|------------------|
| Groq | https://console.groq.com/docs/models | Llama 3.2, Llama 3.3, Mixtral variants |
| Anthropic | https://docs.anthropic.com/en/docs/about-claude/models | Claude 3.5 updates, Claude 4 |
| OpenAI | https://platform.openai.com/docs/models | GPT-4.5, GPT-5, cheaper variants |
| Google | https://ai.google.dev/gemini-api/docs/models/gemini | Gemini 2.5, Gemini Ultra |

**If new models found:**
1. Add to `MODEL_PRICING`
2. Evaluate cost/quality vs current choices
3. Update `MODEL_DECISION_MATRIX.md` with comparison
4. Consider if should replace hardcoded selections

### 5. Run Tests

Verify all model validation tests still pass:

```bash
pytest tests/unit/test_model_choices.py -v
```

**Expected:** 14/14 tests pass

**If tests fail:**
- Cost validation tests may need threshold updates if pricing changed
- Update test assertions to match new pricing
- Re-run to verify fixes

### 6. Review Actual Usage

Check real-world cost distribution:

```bash
curl http://localhost:8001/cost/stats
```

**Expected patterns:**
```json
{
  "total_cost_today": 0.45,
  "cost_by_provider": {
    "groq": 0.30,      // Should be 60-70% (enrichment/triage)
    "anthropic": 0.15  // Should be 30-40% (critique)
  }
}
```

**Red flags:**
- OpenAI has significant costs → Fallback triggering too often
- Anthropic > Groq → Critique being used too frequently
- Total costs unexpectedly high → Check for rate limit loops

### 7. Update Documentation

If model choices or pricing changed significantly:

**Files to update:**
- `MODEL_DECISION_MATRIX.md` - Decision comparisons
- `MODEL_GOVERNANCE.md` - Quick reference table
- `LLM_PROVIDER_STRATEGY.md` - Pricing tables
- `README.md` - Cost estimates
- `CHANGELOG.md` - Note changes

### 8. Commit Changes

```bash
# Update pricing only
git add src/services/llm_service.py
git commit -m "Update model pricing - [Provider] [Model] changed from $X to $Y"

# Add new model
git add src/services/llm_service.py MODEL_DECISION_MATRIX.md
git commit -m "Add [Provider] [Model] to pricing - $X input, $Y output"

# Change hardcoded selection
git add src/services/enrichment_service.py src/services/llm_service.py MODEL_DECISION_MATRIX.md
git commit -m "Switch enrichment from [Old] to [New] - [Reason]"

git push
```

## Hardcoded Model Locations

These are the files where models are hardcoded:

### Enrichment Service
**File:** `src/services/enrichment_service.py`

| Line | Model | Use Case | Reason |
|------|-------|----------|--------|
| 434 | `groq/llama-3.1-8b-instant` | Document classification | Cost ($0.00009/doc) |
| 625 | `groq/llama-3.1-8b-instant` | Metadata enrichment | Cost + Speed |
| 1125 | `anthropic/claude-3-5-sonnet-20241022` | Quality critique | Quality ($0.005/critique) |

**To change a hardcoded model:**
1. Update the `model_id="..."` line
2. Add pricing to `MODEL_PRICING` if not present
3. Update tests in `tests/unit/test_model_choices.py`
4. Update documentation with rationale

## When to Switch Models

### Quality-First Decision Framework

**Our Philosophy:** Quality improvements justify cost increases.

#### For Critique/Quality-Critical Tasks
- ✅ **Switch if:** Noticeable quality improvement, even at 2-3x cost
- ✅ **Example:** Claude 4 at 2x cost but 30% better reasoning → Switch
- ⚠️ **Test:** Compare on sample critique tasks, blind evaluation

**Rationale:** Critique is low-volume (~100 calls/day), quality is paramount. Even 5x cost ($0.025/critique) is acceptable for significant gains.

#### For Enrichment/High-Volume Tasks
- ✅ **Switch if:** Quality improvement is **substantial** (30%+ better)
- ⚠️ **Cost limit:** Max 2x current cost ($0.0002/doc vs $0.00009/doc)
- ❌ **Don't switch if:** Minor quality gain (<10%) at any cost increase

**Rationale:** High-volume (1000s/day) means cost matters. Need clear, measurable quality gain.

#### For Embeddings/Reranking
- ✅ **Stay local:** Free is hard to beat
- ✅ **Switch to API if:** Domain-specific embeddings needed (legal, medical, multilingual)
- ⚠️ **Cost limit:** Max $10/day for embeddings (~10K docs)

**Rationale:** Local embeddings are "good enough" for general RAG. Only switch for specialized domains.

### Example Decision Trees

**New Model: Claude 4 Haiku**
- Cost: $0.40/$2.00 (60% more than Claude 3 Haiku)
- Quality: 20% better at classification, 15% better at extraction

**Decision for Enrichment:**
- Current: Groq at $0.00009/doc
- Claude 4 Haiku: $0.0008/doc (9x more expensive)
- Quality gain: 15-20%
- **Verdict:** ❌ Not worth 9x cost for enrichment
- **Alternative:** Test for critique only

**Decision for Critique:**
- Current: Claude 3.5 Sonnet at $0.005/critique
- Claude 4 Haiku: $0.008/critique (60% more)
- Quality gain: 20% better reasoning
- **Verdict:** ✅ Switch - quality gain justifies cost for low-volume critique

**New Model: Groq Llama 3.2 Turbo**
- Cost: $0.03/$0.05 (40% cheaper than 3.1)
- Quality: 5% better, 2x faster

**Decision:**
- Quality: Minor improvement
- Speed: Significant improvement (2x faster)
- Cost: 40% savings
- **Verdict:** ✅ Switch immediately - better on all metrics

### Never Switch If:
- Quality regression (even if cheaper)
- Provider reliability concerns (check status pages, uptime)
- Breaking API changes (incompatible with current code)
- Worse latency (>50% slower) without major quality gain

## Emergency Updates

If a provider **raises prices significantly** (>50%) mid-quarter:

**Immediate actions:**
1. Update `MODEL_PRICING` immediately
2. Check `/cost/stats` for budget impact
3. If over budget, switch to cheaper alternative:
   - Enrichment: Groq → Gemini Flash ($0.10/$0.40)
   - Critique: Claude Sonnet → Claude Haiku ($0.25/$1.25)
4. Run tests to verify
5. Commit with note: "URGENT: Pricing change - switched to [alternative]"

## Cost Monitoring

### Daily Check (Automated)
Budget enforcement is automatic via `DAILY_BUDGET_USD` in `.env`.

**No action needed** unless:
- Budget limit errors in logs
- Costs trending >80% of daily budget

### Weekly Check (Manual)
```bash
curl http://localhost:8001/cost/stats
```

**Look for:**
- Total costs vs expected (~$0.001 per document processed)
- Groq should be 60-70% of costs
- No unexpected OpenAI usage (emergency fallback only)

### Monthly Check (Manual)
```bash
# Get monthly total from logs
docker-compose logs rag-service | grep "total_cost" | tail -100
```

**Calculate:**
- Documents processed this month
- Cost per document
- Projected monthly cost

**Red flags:**
- Cost per doc > $0.002 → Something using expensive models
- Projected monthly > $50 for <25K docs → Investigate

## Troubleshooting

### Tests Failing After Pricing Update

**Symptom:** `test_enrichment_cost_under_threshold` fails

**Fix:**
```python
# tests/unit/test_model_choices.py
def test_enrichment_cost_under_threshold(self):
    cost = tracker.calculate_cost(
        model="groq/llama-3.1-8b-instant",
        input_tokens=1000,
        output_tokens=300
    )
    assert cost < 0.0001  ← Increase threshold if pricing increased
```

### New Model Not Working

**Symptom:** API errors when using new model

**Checklist:**
- [ ] Model ID matches provider's exact format
- [ ] API key has access to new model
- [ ] Pricing added to `MODEL_PRICING`
- [ ] Provider SDK version supports model

### Unexpected High Costs

**Investigation:**
1. Check provider breakdown: `curl http://localhost:8001/cost/stats`
2. Check logs for expensive calls: `docker-compose logs rag-service | grep "cost:"`
3. Check fallback frequency: `docker-compose logs rag-service | grep "fallback"`

**Common causes:**
- Rate limiting → Fallback to expensive provider
- Critique enabled by default → Should be optional
- Large documents → Excessive token usage

## Summary

**Monthly (1st of each month):**
- ✅ Automated GitHub Issue created
- ✅ Run `python scripts/check_model_pricing.py`
- ✅ Verify pricing at provider websites
- ✅ Check for new models aggressively
- ✅ Test new models if quality improvements claimed
- ✅ Update `MODEL_PRICING` if changed
- ✅ Run tests
- ✅ Review actual costs
- ✅ Commit with updated timestamp

**Emergency (As needed):**
- ⚠️ Major price increases (>50%)
- ⚠️ Provider reliability issues
- ⚠️ Budget overruns

**Next Review:** See `src/services/llm_service.py` line 31 for scheduled date (1st of next month).

**Philosophy:** Quality first - we're willing to pay 2-3x more for meaningful quality improvements in critique/reasoning tasks.

---

For questions or issues, see:
- `MODEL_GOVERNANCE.md` - Governance framework
- `MODEL_DECISION_MATRIX.md` - Decision analysis
- `LLM_PROVIDER_STRATEGY.md` - Provider strategy
