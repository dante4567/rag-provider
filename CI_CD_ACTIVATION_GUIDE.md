# CI/CD Activation Guide
**Time Required:** 5 minutes
**Prerequisites:** GitHub repository with workflows configured

---

## Quick Start (5 Minutes)

### Step 1: Get Your API Keys

You need API keys for at least one LLM provider (Groq recommended for cost):

1. **Groq** (Recommended - Free tier, fast)
   - Go to: https://console.groq.com/keys
   - Sign up / Log in
   - Click "Create API Key"
   - Copy the key (starts with `gsk_`)

2. **Anthropic** (Optional - Higher quality)
   - Go to: https://console.anthropic.com/settings/keys
   - Sign up / Log in
   - Click "Create Key"
   - Copy the key (starts with `sk-ant-`)

3. **OpenAI** (Optional - Fallback)
   - Go to: https://platform.openai.com/api-keys
   - Sign up / Log in
   - Click "Create new secret key"
   - Copy the key (starts with `sk-`)

4. **Voyage AI** (Required for embeddings)
   - Go to: https://dashboard.voyageai.com/
   - Sign up / Log in
   - Add payment method (for production rate limits)
   - Go to API Keys → Create Key
   - Copy the key

---

### Step 2: Add Secrets to GitHub

1. Go to your GitHub repository
2. Click **Settings** (top right)
3. In left sidebar: **Secrets and variables** → **Actions**
4. Click **New repository secret**

Add these secrets one by one:

| Secret Name | Value | Required? |
|-------------|-------|-----------|
| `GROQ_API_KEY` | Your Groq key (`gsk_...`) | Yes |
| `ANTHROPIC_API_KEY` | Your Anthropic key (`sk-ant-...`) | Optional |
| `OPENAI_API_KEY` | Your OpenAI key (`sk-...`) | Optional |
| `VOYAGE_API_KEY` | Your Voyage key | Yes |

**Note:** You need at least `GROQ_API_KEY` for the system to work.

---

### Step 3: Trigger Workflows

**Option A: Push a commit**
```bash
git commit --allow-empty -m "Trigger CI/CD"
git push
```

**Option B: Manually trigger**
1. Go to **Actions** tab in GitHub
2. Select workflow (e.g., "Tests")
3. Click **Run workflow**
4. Select branch: `main`
5. Click **Run workflow**

---

### Step 4: Verify It Works

1. Go to **Actions** tab
2. See your workflow running (yellow dot)
3. Wait for completion (green checkmark = success)
4. If red X → Click workflow → See logs → Fix issue

---

## Workflow Configuration

### tests.yml (Fast Tests on PR)
**Triggers:** Every push to `main` or PR
**Duration:** ~3-5 minutes
**Tests:**
- Unit tests (921 tests)
- Smoke tests (11 tests)
- Skips slow integration tests (marked `@pytest.mark.slow`)

**Expected Result:** All tests pass except slow ones

---

### nightly.yml (Full Test Suite)
**Triggers:** Every night at 2 AM UTC
**Duration:** ~15-20 minutes (includes slow tests)
**Tests:**
- All unit tests
- All integration tests (including slow LLM tests)
- Full end-to-end validation

**Expected Result:** May have some flaky tests (39% integration pass rate currently)

**Known Issues:**
- Integration tests flaky due to LLM rate limits
- Voyage rate limiting may cause failures
- Search timeout issue needs fixing

---

### monthly-model-review.yml (Model Pricing Check)
**Triggers:** 1st of every month at 9 AM UTC
**Duration:** ~2 minutes
**Purpose:**
- Check if model pricing changed
- Discover new models
- Generate report
- Create GitHub issue with recommendations

**Expected Result:** GitHub issue created with pricing report

---

## Troubleshooting

### ❌ Workflow fails: "API key not found"
**Solution:** Add the missing API key to GitHub Secrets (Step 2)

### ❌ Workflow fails: "Voyage rate limit exceeded"
**Solution:**
1. Add payment method to Voyage account (unlocks 300 RPM)
2. OR implement local embeddings fallback (see PRODUCTION_READINESS_ASSESSMENT.md)

### ❌ Integration tests timeout
**Solution:**
- This is expected (search timeout issue)
- See PRODUCTION_READINESS_ASSESSMENT.md for investigation steps
- For now, fast tests should pass

### ❌ All tests fail
**Solution:** Check Docker logs:
```bash
docker logs rag_service --tail 100
```

---

## Next Steps After Activation

1. **Fix Production Blockers** (see PRODUCTION_READINESS_ASSESSMENT.md)
   - Voyage rate limiting
   - Search timeout

2. **Monitor CI/CD**
   - Check daily for failures
   - Fix flaky integration tests
   - Add more test coverage if needed

3. **Monthly Model Review**
   - Review automated pricing reports
   - Evaluate new models
   - Update model selections if better options appear

4. **Performance Monitoring**
   - Add Prometheus metrics
   - Set up Grafana dashboards
   - Monitor latency/throughput in production

---

## FAQ

**Q: Do I need all 4 API keys?**
A: No. Minimum: `GROQ_API_KEY` + `VOYAGE_API_KEY`. Others are fallbacks.

**Q: Will this cost money?**
A: Groq free tier is generous. Voyage needs payment method but you have 200M free tokens.

**Q: What if CI/CD fails?**
A: Check logs, fix issues, push again. Integration tests may be flaky (known issue).

**Q: Can I disable slow tests?**
A: Yes. They're marked `@pytest.mark.slow` and skipped in fast workflows.

**Q: How do I run tests locally?**
A:
```bash
# Fast tests
pytest tests/unit/ -v

# All tests except slow
pytest -m "not slow" -v

# Everything (including slow)
pytest tests/ -v
```

---

## Security Best Practices

1. **Never commit API keys** to git
2. **Use GitHub Secrets** for all sensitive data
3. **Rotate keys** if accidentally exposed
4. **Use separate keys** for dev/staging/prod
5. **Monitor API usage** for unexpected spikes

---

## Useful Commands

```bash
# Check workflow status
gh run list --limit 10

# Watch live workflow
gh run watch

# View workflow logs
gh run view --log

# Trigger manual workflow
gh workflow run tests.yml
```

---

*This guide is part of the production readiness validation (2025-10-13). For production blocker fixes, see PRODUCTION_READINESS_ASSESSMENT.md.*
