# Pre-Commit Hooks Setup Guide

## Overview

Pre-commit hooks automatically check and format code before each commit, catching issues early.

## What Gets Checked

✅ **Code Formatting**
- Black - Python code formatter (line length: 120)
- isort - Import statement organizer

✅ **Code Quality**
- Ruff - Fast Python linter (modern replacement for flake8/pylint)

✅ **Security**
- detect-secrets - Prevent committing API keys, passwords, tokens

✅ **File Quality**
- Trailing whitespace removal
- End-of-file newline fixing
- YAML/JSON validation
- Large file detection (>500KB)
- Merge conflict detection

## Installation

### 1. Install Dependencies

```bash
# Install pre-commit and tools
pip install pre-commit black isort ruff detect-secrets

# Or use requirements.txt
pip install -r requirements.txt
```

### 2. Install Hooks

```bash
# Install git hooks
pre-commit install

# ✅ Done! Hooks will run automatically on git commit
```

### 3. Initial Run (Optional)

```bash
# Run on all files to see current state
pre-commit run --all-files
```

## Usage

### Automatic (Recommended)

Just commit normally:
```bash
git add .
git commit -m "Your message"

# Hooks run automatically
# ✅ If all checks pass → commit succeeds
# ❌ If checks fail → commit blocked, files auto-fixed (re-add and commit)
```

### Manual

Run hooks without committing:
```bash
# Check all files
pre-commit run --all-files

# Check specific files
pre-commit run --files src/services/*.py
```

### Skip Hooks (Use Sparingly)

```bash
# Skip all hooks
SKIP=black,ruff git commit -m "WIP: work in progress"

# Skip one hook
SKIP=ruff git commit -m "Quick fix"

# Skip all hooks (not recommended)
git commit -m "Emergency fix" --no-verify
```

## Common Scenarios

### Scenario 1: Hooks Auto-Fix Files

```bash
$ git commit -m "Add feature"
black....................................................................Failed
- hook id: black
- files were modified by this hook

reformatted src/services/new_service.py
```

**Solution:** Files were auto-formatted, just re-add and commit:
```bash
git add .
git commit -m "Add feature"
# ✅ Now passes
```

### Scenario 2: Linting Errors

```bash
$ git commit -m "Add feature"
ruff.....................................................................Failed
- hook id: ruff

src/services/new_service.py:45:1: F401 'os' imported but unused
```

**Solution:** Fix the error manually:
```bash
# Remove unused import
vim src/services/new_service.py

git add .
git commit -m "Add feature"
# ✅ Now passes
```

### Scenario 3: Secret Detected

```bash
$ git commit -m "Add config"
detect-secrets...........................................................Failed
Potential secrets detected in config.py
```

**Solution:** Remove the secret or update baseline if false positive:
```bash
# If real secret → remove it, use environment variables
# If false positive → update baseline
detect-secrets scan --baseline .secrets.baseline
git add .secrets.baseline
```

## Configuration

### `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks:
      - id: black
        args: [--line-length=120]
```

### Customize

Edit `.pre-commit-config.yaml`:
- Change line length: `args: [--line-length=100]`
- Add/remove hooks
- Update versions

After changes:
```bash
pre-commit install --install-hooks
```

## Troubleshooting

### Hooks Not Running

```bash
# Reinstall hooks
pre-commit uninstall
pre-commit install

# Verify
ls -la .git/hooks/pre-commit
```

### Update Hook Versions

```bash
# Update to latest versions
pre-commit autoupdate

# Check
git diff .pre-commit-config.yaml
```

### Slow Hooks

The pytest hook is commented out by default (can be slow). Uncomment in `.pre-commit-config.yaml` if you want tests on every commit:

```yaml
# Uncomment to enable
- repo: local
  hooks:
    - id: pytest
      name: pytest
      entry: pytest
      language: system
      types: [python]
      files: ^tests/
```

## Integration with CI/CD

Pre-commit hooks also run in CI/CD:

```yaml
# .github/workflows/tests.yml
- name: Run pre-commit
  run: pre-commit run --all-files
```

## Best Practices

✅ **Do:**
- Run `pre-commit run --all-files` before big commits
- Keep hooks fast (< 10 seconds)
- Update `.secrets.baseline` when adding safe patterns
- Commit formatted code

❌ **Don't:**
- Use `--no-verify` regularly (defeats the purpose)
- Commit with unfixed linting errors
- Skip security checks (detect-secrets)

## Summary

**Setup:** One-time, 30 seconds
```bash
pip install pre-commit && pre-commit install
```

**Usage:** Automatic, zero friction
```bash
git commit -m "message"
# Hooks run automatically ✅
```

**Benefits:**
- Consistent code formatting
- Catch bugs early (unused imports, syntax errors)
- Prevent secrets in commits
- Better code reviews (no style debates)
