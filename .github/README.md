# GitHub Actions CI/CD Setup

This directory contains automated workflows for continuous integration and testing.

## Workflows

### 1. `tests.yml` - Pull Request & Push Validation

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

**Jobs:**

#### Smoke Tests (< 5 seconds)
- **Purpose:** Fast validation of critical functionality
- **Tests:** 11 smoke tests
- **Timeout:** 2 minutes
- **Fail Fast:** Stops on first failure

#### Unit Tests (< 5 minutes)
- **Purpose:** Validate all business logic
- **Tests:** 571 unit tests
- **Coverage:** Uploads to Codecov
- **Timeout:** 5 minutes

#### Fast Integration Tests (< 3 minutes)
- **Purpose:** API validation without LLM calls
- **Tests:** 17 fast integration tests (marked `not slow`)
- **Timeout:** 3 minutes

**Total Runtime:** ~10 minutes

### 2. `nightly.yml` - Comprehensive Nightly Testing

**Triggers:**
- Daily at 2 AM UTC
- Manual trigger via workflow_dispatch

**Jobs:**

#### Full Test Suite (< 30 minutes)
- **Purpose:** Thorough validation including slow LLM tests
- **Tests:** All 582 tests (unit + integration)
- **Features:**
  - HTML test report generation
  - Coverage reporting
  - Artifact uploads
  - Continue on rate limit errors

**Total Runtime:** ~20-30 minutes

## Setup Instructions

### 1. Required Secrets

Add these secrets to your GitHub repository:
(Settings → Secrets and variables → Actions → New repository secret)

```
GROQ_API_KEY          # Required for LLM functionality
ANTHROPIC_API_KEY     # Required for fallback LLM
OPENAI_API_KEY        # Optional, for emergency fallback
GOOGLE_API_KEY        # Optional, for Gemini Vision
```

### 2. Optional: Codecov Integration

For test coverage tracking:

1. Sign up at https://codecov.io/
2. Add your repository
3. Add `CODECOV_TOKEN` secret (if private repo)

### 3. Verify Workflows

After pushing workflows:

1. Go to Actions tab in GitHub
2. You should see "Tests" and "Nightly Tests" workflows
3. Trigger manually to test:
   - Click on workflow
   - Click "Run workflow"
   - Select branch
   - Click "Run workflow"

## Workflow Status Badges

Add to your README.md:

```markdown
![Tests](https://github.com/YOUR_USERNAME/rag-provider/workflows/Tests/badge.svg)
![Nightly Tests](https://github.com/YOUR_USERNAME/rag-provider/workflows/Nightly%20Tests/badge.svg)
```

## Understanding Test Results

### Smoke Tests
- **Expected:** ✅ 11/11 passing
- **Time:** < 5 seconds
- **Failure:** Indicates critical system issue

### Unit Tests
- **Expected:** ✅ 571/571 passing
- **Time:** < 5 minutes
- **Failure:** Indicates business logic bug

### Fast Integration Tests
- **Expected:** ✅ 17/17 passing
- **Time:** < 3 minutes
- **Failure:** Indicates API contract issue

### Slow Integration Tests (Nightly only)
- **Expected:** ⚠️ May have some failures due to rate limits
- **Time:** 10-20 minutes
- **Failure:** Check if due to rate limiting (HTTP 429)

## Customization

### Adjust Test Timeouts

In `tests.yml`:
```yaml
- name: Run smoke tests
  run: pytest tests/integration/test_smoke.py -v
  timeout-minutes: 2  # Adjust this
```

### Change Nightly Schedule

In `nightly.yml`:
```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # Change to desired time
```

Cron format: `minute hour day month weekday`
- `0 2 * * *` = 2 AM UTC daily
- `0 14 * * 1` = 2 PM UTC on Mondays
- `0 0 * * 0` = Midnight UTC on Sundays

### Run Specific Tests Only

```yaml
- name: Run specific tests
  run: |
    pytest tests/unit/test_enrichment_service.py -v
    pytest tests/integration/test_smoke.py -v
```

## Troubleshooting

### Tests Pass Locally, Fail in CI

**Possible causes:**
1. Missing environment variables
2. Different Python/package versions
3. Service startup timing

**Solutions:**
1. Check secret configuration
2. Use `cache: 'pip'` in setup-python action
3. Increase wait time for services

### Service Not Ready

If tests fail with connection errors:

```yaml
- name: Wait for service
  run: |
    for i in {1..60}; do  # Increase retries
      if curl -s http://localhost:8001/health; then
        break
      fi
      sleep 2
    done
```

### ChromaDB Connection Issues

Check service health:

```yaml
services:
  chromadb:
    options: >-
      --health-cmd "curl -f http://localhost:8000/api/v1/heartbeat || exit 1"
      --health-interval 10s
      --health-retries 10  # Increase retries
```

### Rate Limiting (HTTP 429)

Expected in nightly tests with many LLM calls. Solutions:

1. Use `continue-on-error: true` for slow tests
2. Add delays between tests
3. Mock LLM responses for most tests

```yaml
- name: Run slow tests with delays
  run: |
    pytest tests/integration -m "slow" -v --maxfail=3
  continue-on-error: true
```

## Best Practices

### For Pull Requests

1. **Keep tests fast:** Smoke + unit tests should finish in < 10 minutes
2. **Fail fast:** Use `--maxfail=1` for smoke tests
3. **Clear errors:** Use `--tb=short` for readable output

### For Nightly Builds

1. **Comprehensive:** Run all tests including slow ones
2. **Reports:** Generate HTML reports for debugging
3. **Coverage:** Track coverage trends over time
4. **Notifications:** Set up notifications for failures

### For Releases

Before tagging a release:

1. Ensure all tests pass
2. Check nightly build results
3. Review coverage reports
4. Run manual smoke test on production-like environment

## Monitoring

### Check Workflow Status

```bash
# Using GitHub CLI
gh run list --workflow=tests.yml
gh run list --workflow=nightly.yml

# View specific run
gh run view <run-id>

# Download artifacts
gh run download <run-id>
```

### View Coverage Trends

1. Go to Codecov dashboard
2. View coverage graphs
3. Check which files need more tests

## Performance Optimization

### Parallel Testing

For faster execution:

```yaml
- name: Run tests in parallel
  run: |
    pytest tests/unit -n auto  # Requires pytest-xdist
```

### Cache Dependencies

Already configured:

```yaml
- uses: actions/setup-python@v5
  with:
    cache: 'pip'  # Caches pip packages
```

### Matrix Strategy

Test multiple Python versions:

```yaml
strategy:
  matrix:
    python-version: ['3.10', '3.11', '3.12']

steps:
  - uses: actions/setup-python@v5
    with:
      python-version: ${{ matrix.python-version }}
```

## Security

### Secrets Management

- Never commit API keys
- Use GitHub Secrets for sensitive data
- Rotate keys regularly
- Use different keys for CI/CD vs production

### Dependency Scanning

Add Dependabot:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
```

## Support

- **Documentation:** See `/TESTING_GUIDE.md`
- **Issues:** GitHub Issues
- **Questions:** GitHub Discussions

## Version History

- **v1.0** (Oct 9, 2025) - Initial CI/CD setup
  - Smoke tests (11 tests, < 5s)
  - Unit tests (571 tests, < 5min)
  - Fast integration tests (17 tests, < 3min)
  - Nightly comprehensive testing
