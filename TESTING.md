# Testing Guide

## Overview

The RAG Provider includes a comprehensive test suite covering unit tests, integration tests, and end-to-end scenarios.

## Test Structure

```
tests/
├── conftest.py          # Pytest configuration and fixtures
├── unit/                # Unit tests
│   ├── test_auth.py     # Authentication tests
│   └── test_models.py   # Pydantic model tests
└── integration/         # Integration tests
    └── test_api.py      # API endpoint tests
```

## Running Tests

### Prerequisites

Install test dependencies:
```bash
pip install pytest pytest-asyncio httpx
```

### Run All Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src --cov-report=html
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Authentication tests
pytest -k "auth"

# API tests
pytest -k "api"
```

### Run Individual Test Files

```bash
# Authentication tests
pytest tests/unit/test_auth.py

# Model validation tests
pytest tests/unit/test_models.py

# API integration tests
pytest tests/integration/test_api.py
```

## Test Categories

### Unit Tests

Test individual components in isolation:

- **Authentication (`test_auth.py`)**
  - API key validation
  - Public endpoint access
  - Error handling

- **Models (`test_models.py`)**
  - Pydantic model validation
  - Enum value validation
  - Required field validation

### Integration Tests

Test complete workflows:

- **API Endpoints (`test_api.py`)**
  - Health endpoint
  - Authentication flows
  - Document ingestion
  - Search functionality
  - CORS configuration

## Test Configuration

### Environment Variables

Tests use these environment overrides:
```env
REQUIRE_AUTH=false          # Disable auth for most tests
ANTHROPIC_API_KEY=""        # Empty to test error conditions
OPENAI_API_KEY=""
GROQ_API_KEY=""
GOOGLE_API_KEY=""
```

### Fixtures

**`test_client`** - FastAPI test client with auth disabled
```python
def test_example(test_client):
    response = test_client.get("/health")
    assert response.status_code == 200
```

**`mock_chromadb`** - Mocked ChromaDB for testing
```python
def test_search(test_client, mock_chromadb):
    with patch("app.collection", mock_chromadb[1]):
        response = test_client.post("/search", json={"text": "test"})
```

**`sample_document`** - Sample document data
```python
def test_ingest(test_client, sample_document):
    response = test_client.post("/ingest", json=sample_document)
```

## Writing Tests

### Unit Test Example

```python
import pytest
from src.models.schemas import Document, DocumentType

class TestDocumentModel:
    def test_document_creation(self):
        doc = Document(
            content="Test content",
            document_type=DocumentType.text
        )
        assert doc.content == "Test content"
        assert doc.document_type == DocumentType.text
```

### Integration Test Example

```python
class TestAPIEndpoint:
    def test_health_endpoint(self, test_client):
        response = test_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
```

### Async Test Example

```python
import pytest

class TestAsyncFunction:
    @pytest.mark.asyncio
    async def test_async_operation(self):
        result = await some_async_function()
        assert result is not None
```

## Mock Usage

### Mocking External Services

```python
from unittest.mock import patch, Mock

def test_with_mocked_llm():
    with patch("app.llm_clients") as mock_clients:
        mock_clients.__bool__.return_value = True
        # Test code here
```

### Mocking Environment Variables

```python
import os
from unittest.mock import patch

def test_with_env_vars():
    with patch.dict(os.environ, {"API_KEY": "test_key"}):
        # Test code here
```

## Test Data

### Sample Documents

```python
# Text document
text_doc = {
    "content": "This is sample text content",
    "filename": "sample.txt",
    "document_type": "text"
}

# PDF document
pdf_doc = {
    "content": "PDF content here",
    "filename": "document.pdf",
    "document_type": "pdf",
    "process_ocr": False
}
```

### Sample Queries

```python
# Basic search
basic_query = {
    "text": "search term",
    "top_k": 5
}

# Filtered search
filtered_query = {
    "text": "search term",
    "top_k": 10,
    "filter": {"document_type": "pdf"}
}
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v3
```

## Performance Testing

### Load Testing with pytest-benchmark

```bash
pip install pytest-benchmark

# Run performance tests
pytest --benchmark-only
```

### Example Performance Test

```python
def test_document_processing_performance(benchmark):
    def process_document():
        # Document processing code
        return result

    result = benchmark(process_document)
    assert result is not None
```

## Debugging Tests

### Running with Debugging

```bash
# Run with Python debugger
pytest --pdb

# Run specific test with debugging
pytest tests/unit/test_auth.py::TestAuthentication::test_auth_flow --pdb

# Run with detailed output
pytest -vvv -s
```

### Logging in Tests

```python
import logging

def test_with_logging(caplog):
    with caplog.at_level(logging.INFO):
        # Test code that logs
        pass

    assert "Expected log message" in caplog.text
```

## Best Practices

1. **Isolation**: Each test should be independent
2. **Naming**: Use descriptive test names
3. **Arrange-Act-Assert**: Structure tests clearly
4. **Mocking**: Mock external dependencies
5. **Coverage**: Aim for >80% code coverage
6. **Speed**: Keep unit tests fast (<1s each)
7. **Documentation**: Document complex test scenarios

## Coverage Reports

Generate coverage reports:

```bash
# HTML report
pytest --cov=src --cov-report=html

# Terminal report
pytest --cov=src --cov-report=term-missing

# XML report (for CI)
pytest --cov=src --cov-report=xml
```

View HTML report:
```bash
open htmlcov/index.html
```