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
            id="doc1",
            content="Test content",
            metadata={"filename": "test.txt"},
            similarity=0.85,
            document_id="doc1",
            chunk_index=0
        )
        assert result.id == "doc1"
        assert result.similarity == 0.85
        assert result.document_id == "doc1"
        assert result.chunk_index == 0

    def test_search_response(self):
        """Test SearchResponse model"""
        result = SearchResult(
            id="doc1",
            content="Test content",
            metadata={"filename": "test.txt"},
            similarity=0.85,
            document_id="doc1",
            chunk_index=0
        )
        response = SearchResponse(
            results=[result],
            query="test",
            total_results=1,
            processing_time=0.5
        )
        assert len(response.results) == 1
        assert response.query == "test"
        assert response.total_results == 1
        assert response.processing_time == 0.5


class TestChatModels:
    """Test chat-related models"""

    def test_chat_request_minimal(self):
        """Test ChatRequest with minimal fields"""
        request = ChatRequest(question="What is this?")
        assert request.question == "What is this?"
        assert request.conversation_id is None
        assert request.max_context_chunks == 5
        assert request.llm_provider is None
        assert request.include_sources is True

    def test_chat_request_full(self):
        """Test ChatRequest with all fields"""
        request = ChatRequest(
            question="What is this?",
            conversation_id="conv123",
            max_context_chunks=10,
            llm_provider=LLMProvider.anthropic,
            include_sources=False
        )
        assert request.question == "What is this?"
        assert request.conversation_id == "conv123"
        assert request.max_context_chunks == 10
        assert request.llm_provider == LLMProvider.anthropic
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
        assert LLMModel.claude_haiku == "anthropic/claude-3-haiku-20240307"
        assert LLMModel.gpt4o_mini == "openai/gpt-4o-mini"