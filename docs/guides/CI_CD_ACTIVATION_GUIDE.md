# CI/CD Activation Guide

**Status:** Ready for activation
**Workflows:** Configured and pushed to `.github/workflows/`
**Required:** GitHub repository secrets

## 🎯 Quick Start (5 minutes)

### Step 1: Add GitHub Secrets

Navigate to your GitHub repository:

```
https://github.com/YOUR_USERNAME/rag-provider/settings/secrets/actions
```

Click **"New repository secret"** and add each of the following:

| Secret Name | Value | Required | Purpose |
|-------------|-------|----------|---------|
| `GROQ_API_KEY` | `gsk_...` | ✅ Yes | Primary LLM (ultra-cheap) |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | ✅ Yes | Fallback LLM |
| `OPENAI_API_KEY` | `sk-...` | ⚠️ Recommended | Emergency fallback |
| `GOOGLE_API_KEY` | `...` | ❌ Optional | Gemini Vision |

**Where to get keys:**
- **Groq:** https://console.groq.com/keys
- **Anthropic:** https://console.anthropic.com/settings/keys
- **OpenAI:** https://platform.openai.com/api-keys
- **Google:** https://makersuite.google.com/app/apikey

### Step 2: Verify Workflows Exist

Check that workflows are in your repository:

```bash
ls -la .github/workflows/
# Should show:
# - tests.yml
# - nightly.yml
```

### Step 3: Trigger First Run

**Option A: Push a commit (automatic)**
```bash
git commit --allow-empty -m "Test CI/CD"
git push
```

**Option B: Manual trigger (recommended for first test)**
1. Go to: `https://github.com/YOUR_USERNAME/rag-provider/actions`
2. Click on **"Tests"** workflow
3. Click **"Run workflow"** dropdown
4. Select branch: `main`
5. Click **"Run workflow"** button

### Step 4: Monitor First Run

1. Go to Actions tab: `https://github.com/YOUR_USERNAME/rag-provider/actions`
2. Click on the running workflow
3. Watch the jobs execute:
   - ✅ Smoke Tests (< 2 min)
   - ✅ Unit Tests (< 5 min)
   - ✅ Fast Integration Tests (< 3 min)

**Expected Result:** All jobs complete successfully with green checkmarks ✅

## 📋 Detailed Setup

### GitHub Actions Workflows Overview

**1. tests.yml** - Pull Request & Push Validation

**Triggers:**
- Every push to `main` or `develop`
- Every pull request to `main` or `develop`

**Jobs:**
```
smoke-tests (2 min)
├── Install dependencies
├── Start ChromaDB service
├── Start RAG service
└── Run 11 smoke tests

unit-tests (5 min)
├── Install dependencies
├── Run 571 unit tests
└── Upload coverage to Codecov

fast-integration-tests (3 min)
├── Install dependencies
├── Start ChromaDB service
├── Start RAG service
└── Run 17 fast integration tests (no LLM calls)
```

**Total Runtime:** ~10 minutes

**2. nightly.yml** - Comprehensive Nightly Testing

**Triggers:**
- Daily at 2 AM UTC
- Manual via workflow_dispatch

**Jobs:**
```
full-test-suite (20-30 min)
├── Install dependencies
├── Start ChromaDB service
├── Start RAG service
├── Run 571 unit tests
├── Run 23 integration tests (including slow)
├── Generate HTML test report
├── Upload coverage to Codecov
└── Upload test artifacts
```

**Total Runtime:** ~20-30 minutes

### Environment Setup

**Required Services:**

The workflows automatically start these services:

1. **ChromaDB** (vector database)
   - Image: `chromadb/chroma:latest`
   - Port: 8000
   - Health checks: Automatic
   - Retries: 5 attempts with 10s interval

2. **RAG Service** (main application)
   - Starts from repository code
   - Port: 8001
   - Health endpoint: `/health`
   - Startup wait: 10 seconds + retries

**System Dependencies:**

Automatically installed in CI:
- tesseract-ocr (multiple languages)
- poppler-utils (PDF processing)
- libmagic1 (file type detection)
- Python 3.11

**Python Dependencies:**

Automatically installed from `requirements.txt`:
- FastAPI, Uvicorn
- ChromaDB, sentence-transformers
- LLM clients (litellm, anthropic, openai, groq)
- Document processing (unstructured, pypdf, python-docx)
- Testing (pytest, pytest-asyncio, pytest-cov)

## 🔍 Troubleshooting

### Issue 1: "Secrets not found"

**Symptom:** Workflow fails with missing environment variables

**Solution:**
1. Verify secrets are added: Settings → Secrets → Actions
2. Check secret names match exactly (case-sensitive)
3. Re-run workflow after adding secrets

**Verification:**
```yaml
# Secrets should be visible in workflow logs as:
GROQ_API_KEY: ***
ANTHROPIC_API_KEY: ***
```

### Issue 2: "ChromaDB connection failed"

**Symptom:** Tests fail with connection refused errors

**Cause:** ChromaDB service not ready

**Solution:** Already handled by workflow retries

**Check logs:**
```
Step: Wait for service
✅ Service is ready (attempt 3/30)
```

### Issue 3: "Rate limit exceeded (HTTP 429)"

**Symptom:** Slow integration tests fail

**Expected:** Normal for batch LLM tests

**Solution:**
- Smoke tests: No LLM calls, always pass ✅
- Fast integration tests: No LLM calls, always pass ✅
- Slow integration tests: Run in nightly only, `continue-on-error: true`

**Status:** Not a failure, by design

### Issue 4: "Tests pass locally, fail in CI"

**Possible causes:**
1. Missing environment variables
2. Different Python/package versions
3. Timing issues

**Debug steps:**
```bash
# 1. Check workflow logs for specific error
# 2. Reproduce locally with exact CI Python version
docker run -it python:3.11-slim bash
pip install -r requirements.txt
pytest tests/integration/test_smoke.py -v

# 3. Check service startup timing in logs
```

## 📊 Monitoring & Badges

### Status Badges

Already added to README.md:

```markdown
![Tests](https://github.com/YOUR_USERNAME/rag-provider/workflows/Tests/badge.svg)
![Nightly Tests](https://github.com/YOUR_USERNAME/rag-provider/workflows/Nightly%20Tests/badge.svg)
```

**Badge Status:**
- 🟢 Green: All tests passing
- 🔴 Red: Some tests failing
- ⚪ Gray: Workflow not run yet

### GitHub CLI Monitoring

```bash
# Install GitHub CLI
brew install gh  # macOS
# or: https://cli.github.com/

# Authenticate
gh auth login

# List recent runs
gh run list --workflow=tests.yml
gh run list --workflow=nightly.yml

# View specific run
gh run view <run-id>

# Watch live run
gh run watch

# Download artifacts
gh run download <run-id>
```

### Email Notifications

**Configure in GitHub:**
1. Go to: https://github.com/settings/notifications
2. Under "Actions":
   - ✅ Enable "Send notifications for failed workflows only"
   - Or: Custom notification settings

## 🎨 Optional Enhancements

### 1. Codecov Integration

**Setup:**
1. Sign up: https://codecov.io/
2. Add repository
3. Get upload token
4. Add `CODECOV_TOKEN` secret (if private repo)

**Benefit:** Coverage tracking over time

**Status:** Already configured in workflows, awaiting token

### 2. Slack Notifications

Add to workflows:

```yaml
- name: Notify Slack
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {
        "text": "❌ Tests failed on ${{ github.ref }}"
      }
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### 3. Matrix Testing (Multiple Python Versions)

```yaml
strategy:
  matrix:
    python-version: ['3.10', '3.11', '3.12']

steps:
  - uses: actions/setup-python@v5
    with:
      python-version: ${{ matrix.python-version }}
```

**Benefit:** Test compatibility across Python versions

**Trade-off:** 3x longer CI runtime

### 4. Dependabot (Automated Dependency Updates)

Create `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
```

**Benefit:** Automatic PRs for dependency updates

## ✅ Verification Checklist

After activation, verify:

- [ ] Secrets added to GitHub repository
- [ ] Workflow badges appear in README
- [ ] First workflow run completed successfully
- [ ] Smoke tests passing (< 5s)
- [ ] Unit tests passing (< 5min)
- [ ] Fast integration tests passing (< 3min)
- [ ] Workflow logs accessible
- [ ] Coverage reports generated
- [ ] Test artifacts uploaded

## 📚 Related Documentation

- **[Testing Guide](TESTING_GUIDE.md)** - How to run tests locally
- **[CI/CD Setup](.github/README.md)** - Detailed workflow documentation
- **[Integration Test Analysis](INTEGRATION_TEST_ANALYSIS.md)** - Optimization details
- **[Project Status](PROJECT_STATUS.md)** - Overall system status

## 🚀 Next Steps

**After CI/CD activation:**

1. **Monitor first few runs**
   - Watch for any environment-specific issues
   - Verify all test suites pass
   - Check timing matches expectations

2. **Configure branch protection** (recommended)
   - Go to: Settings → Branches → Add rule
   - Branch name pattern: `main`
   - ✅ Require status checks to pass before merging
   - Select: "Smoke Tests", "Unit Tests", "Fast Integration Tests"
   - ✅ Require branches to be up to date before merging

3. **Set up notifications**
   - GitHub email notifications
   - Slack integration (optional)
   - Custom webhooks (optional)

4. **Production deployment**
   - Choose hosting platform
   - Set up monitoring
   - Configure backups

## 🎓 Best Practices

### For Pull Requests

1. **Keep tests fast**
   - Smoke tests: < 5s
   - Unit tests: < 5min
   - Skip slow LLM tests

2. **Fail fast**
   - Smoke tests run first
   - Use `--maxfail=1` for smoke tests
   - Stop on first critical failure

3. **Clear feedback**
   - Descriptive test names
   - Good error messages
   - Logs available on failure

### For Nightly Builds

1. **Comprehensive coverage**
   - Run all tests including slow ones
   - Generate full reports
   - Track coverage trends

2. **Graceful degradation**
   - Use `continue-on-error: true` for rate-limited tests
   - Upload reports even on partial failure
   - Clear status in final summary

### For Releases

**Before tagging:**
1. ✅ All tests passing (including nightly)
2. ✅ Coverage meeting targets
3. ✅ No critical bugs
4. ✅ Documentation updated

**Tag and release:**
```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

## 📞 Support

**If workflows fail:**
1. Check workflow logs in Actions tab
2. Review troubleshooting section above
3. Consult [TESTING_GUIDE.md](TESTING_GUIDE.md)
4. Verify secrets configuration
5. Test locally first

**Common commands:**
```bash
# Run smoke tests locally
pytest tests/integration/test_smoke.py -v

# Check service health
curl http://localhost:8001/health

# View workflow logs
gh run view --log

# Re-run failed jobs
gh run rerun <run-id> --failed
```

---

**Activation Status:** ⏸️ Awaiting GitHub secrets
**Estimated Time:** 5 minutes
**Next Action:** Add API keys to GitHub secrets
