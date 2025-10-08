"""
Unit tests for Pydantic models
"""
import pytest
from pydantic import ValidationError

from src.models.schemas import (
    Document, DocumentType, Query, SearchResult, SearchResponse,
    ChatRequest, ChatResponse, TestLLMRequest, LLMProvider, LLMModel
)


class TestDocumentModel:
    """Test Document model validation"""

    def test_document_minimal(self):
        """Test document with minimal required fields"""
        doc = Document(content="Test content")
        assert doc.content == "Test content"
        assert doc.filename is None
        assert doc.document_type == DocumentType.text
        assert doc.process_ocr is False
        assert doc.generate_obsidian is True

    def test_document_full(self):
        """Test document with all fields"""
        doc = Document(
            content="Test content",
            filename="test.txt",
            document_type=DocumentType.pdf,
            metadata={"source": "test"},
            process_ocr=True,
            generate_obsidian=False
        )
        assert doc.content == "Test content"
        assert doc.filename == "test.txt"
        assert doc.document_type == DocumentType.pdf
        assert doc.metadata == {"source": "test"}
        assert doc.process_ocr is True
        assert doc.generate_obsidian is False

    def test_document_invalid_type(self):
        """Test document with invalid document type"""
        with pytest.raises(ValidationError):
            Document(content="Test", document_type="invalid_type")


class TestQueryModel:
    """Test Query model validation"""

    def test_query_minimal(self):
        """Test query with minimal fields"""
        query = Query(text="search text")
        assert query.text == "search text"
        assert query.top_k == 5
        assert query.filter is None

    def test_query_full(self):
        """Test query with all fields"""
        query = Query(
            text="search text",
            top_k=10,
            filter={"document_type": "pdf"}
        )
        assert query.text == "search text"
        assert query.top_k == 10
        assert query.filter == {"document_type": "pdf"}

    def test_query_invalid_top_k(self):
        """Test query with invalid top_k"""
        with pytest.raises(ValidationError):
            Query(text="search", top_k="invalid")


class TestSearchModels:
    """Test search-related models"""

    def test_search_result(self):
        """Test SearchResult model"""
        result = SearchResult(
            content="Test content",
            metadata={"filename": "test.txt"},
            relevance_score=0.85,
            chunk_id="doc1_chunk_0"
        )
        assert result.content == "Test content"
        assert result.relevance_score == 0.85
        assert result.chunk_id == "doc1_chunk_0"
        assert result.metadata["filename"] == "test.txt"

    def test_search_response(self):
        """Test SearchResponse model"""
        result = SearchResult(
            content="Test content",
            metadata={"filename": "test.txt"},
            relevance_score=0.85,
            chunk_id="doc1_chunk_0"
        )
        response = SearchResponse(
            results=[result],
            query="test",
            total_results=1,
            search_time_ms=123.45
        )
        assert len(response.results) == 1
        assert response.query == "test"
        assert response.total_results == 1
        assert response.search_time_ms == 123.45


class TestChatModels:
    """Test chat-related models"""

    def test_chat_request_minimal(self):
        """Test ChatRequest with minimal fields"""
        request = ChatRequest(question="What is this?")
        assert request.question == "What is this?"
        assert request.max_context_chunks == 5
        assert request.llm_provider is None
        assert request.include_sources is True

    def test_chat_request_full(self):
        """Test ChatRequest with all fields"""
        request = ChatRequest(
            question="What is this?",
            max_context_chunks=10,
            llm_provider=LLMProvider.anthropic,
            llm_model=LLMModel.anthropic_claude_3_haiku,
            include_sources=False
        )
        assert request.question == "What is this?"
        assert request.max_context_chunks == 10
        assert request.llm_provider == LLMProvider.anthropic
        assert request.llm_model == LLMModel.anthropic_claude_3_haiku
        assert request.include_sources is False


class TestLLMModels:
    """Test LLM-related models"""

    def test_test_llm_request_minimal(self):
        """Test TestLLMRequest with minimal fields"""
        request = TestLLMRequest()
        assert request.provider is None
        assert request.model is None
        assert request.prompt == "Hello, this is a test."

    def test_test_llm_request_full(self):
        """Test TestLLMRequest with all fields"""
        request = TestLLMRequest(
            provider=LLMProvider.groq,
            model=LLMModel.groq_llama3_8b,
            prompt="Custom test prompt"
        )
        assert request.provider == LLMProvider.groq
        assert request.model == LLMModel.groq_llama3_8b
        assert request.prompt == "Custom test prompt"

    def test_llm_provider_enum(self):
        """Test LLMProvider enum values"""
        assert LLMProvider.anthropic == "anthropic"
        assert LLMProvider.openai == "openai"
        assert LLMProvider.groq == "groq"
        assert LLMProvider.google == "google"

    def test_llm_model_enum(self):
        """Test LLMModel enum values"""
        assert LLMModel.groq_llama3_8b == "groq/llama-3.1-8b-instant"
        assert LLMModel.anthropic_claude_3_haiku == "anthropic/claude-3-haiku-20240307"
        assert LLMModel.openai_gpt_4o_mini == "openai/gpt-4o-mini"