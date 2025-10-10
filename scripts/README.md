# Scripts Directory

Utility scripts for development, testing, and maintenance.

## Directory Structure

### `/analysis/`
Analysis and benchmarking scripts:
- `analyze_scale_test.py` - Analyze scale test results

### `/testing/`
Test execution and monitoring scripts:
- `test_comprehensive_suite.sh` - Run full test suite
- `test_with_real_docs.sh` - Test with real documents
- `monitor_progress.sh` - Monitor processing progress

### Root Scripts
- `check_model_pricing.py` - Monthly model pricing checker (automated via GitHub Actions)

## Usage

**Model pricing check:**
```bash
python scripts/check_model_pricing.py
```

**Run comprehensive tests:**
```bash
./scripts/testing/test_comprehensive_suite.sh
```

**Analyze scale test results:**
```bash
python scripts/analysis/analyze_scale_test.py
```

## Development

Scripts follow these conventions:
- Python scripts: Use `#!/usr/bin/env python3` shebang
- Shell scripts: Use `#!/bin/bash` shebang and `set -euo pipefail`
- All scripts should be executable (`chmod +x`)
- Include brief description at top of file
