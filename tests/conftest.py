"""
Pytest configuration and fixtures for RAG Provider tests
"""
import pytest
import asyncio
import os
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app"""
    # Mock environment variables for testing
    with patch.dict(os.environ, {
        "REQUIRE_AUTH": "false",
        "ANTHROPIC_API_KEY": "",
        "OPENAI_API_KEY": "",
        "GROQ_API_KEY": "",
        "GOOGLE_API_KEY": "",
        "CHROMA_HOST": "localhost",
        "CHROMA_PORT": "8000"
    }):
        from app import app
        client = TestClient(app)
        yield client


@pytest.fixture
def mock_chromadb():
    """Mock ChromaDB client"""
    mock_client = Mock()
    mock_collection = Mock()
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_collection.add.return_value = None
    mock_collection.query.return_value = {
        "ids": [["doc1"]],
        "documents": [["Test document content"]],
        "metadatas": [[{"filename": "test.txt"}]],
        "distances": [[0.1]]
    }
    return mock_client, mock_collection


@pytest.fixture
def sample_document():
    """Sample document for testing"""
    return {
        "content": "This is a test document for RAG processing.",
        "filename": "test_document.txt",
        "document_type": "text",
        "metadata": {"source": "test"},
        "process_ocr": False,
        "generate_obsidian": True
    }


@pytest.fixture
def sample_query():
    """Sample query for testing"""
    return {
        "text": "test document",
        "top_k": 5
    }