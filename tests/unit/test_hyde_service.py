"""
Unit tests for HyDEService

Tests Hypothetical Document Embeddings for improved retrieval
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock

from src.services.hyde_service import HyDEService


class MockLLMService:
    """Mock LLM service for testing"""

    def __init__(self, response="Hypothetical document content."):
        self.response = response
        self.call_count = 0

    async def generate_completion(self, messages, max_tokens=300, temperature=0.7):
        self.call_count += 1
        return self.response


class TestHyDEService:
    """Test the HyDEService class"""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM service"""
        return MockLLMService()

    @pytest.fixture
    def service(self, mock_llm):
        """Create HyDEService instance"""
        return HyDEService(llm_service=mock_llm)

    @pytest.mark.asyncio
    async def test_init(self, mock_llm):
        """Test initialization"""
        service = HyDEService(llm_service=mock_llm)
        assert service.llm_service is mock_llm

    @pytest.mark.asyncio
    async def test_generate_single_hypothetical_document(self, service, mock_llm):
        """Test generating a single hypothetical document"""
        query = "What is the capital of France?"

        result = await service.generate_hypothetical_document(query, num_variants=1)

        assert len(result) == 1
        assert isinstance(result[0], str)
        assert len(result[0]) > 0
        assert mock_llm.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_multiple_hypothetical_documents(self, service, mock_llm):
        """Test generating multiple hypothetical document variants"""
        query = "What is Python?"

        result = await service.generate_hypothetical_document(query, num_variants=3)

        assert len(result) == 3
        assert all(isinstance(doc, str) for doc in result)
        assert mock_llm.call_count == 3

    @pytest.mark.asyncio
    async def test_different_document_styles(self, service):
        """Test different document style hints"""
        query = "Explain machine learning"

        # Test different styles
        for style in ["informative", "technical", "conversational", "email", "report"]:
            result = await service.generate_hypothetical_document(
                query,
                num_variants=1,
                document_style=style
            )
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_expand_query_with_original(self, service):
        """Test query expansion with original query included"""
        query = "Test query"

        result = await service.expand_query_with_hyde(
            query,
            num_variants=2,
            include_original=True
        )

        # Should have original + 2 variants = 3 total
        assert len(result) == 3
        assert result[0] == query  # First should be original

    @pytest.mark.asyncio
    async def test_expand_query_without_original(self, service):
        """Test query expansion without original query"""
        query = "Test query"

        result = await service.expand_query_with_hyde(
            query,
            num_variants=2,
            include_original=False
        )

        # Should have only 2 variants
        assert len(result) == 2
        assert query not in result

    @pytest.mark.asyncio
    async def test_multi_query_search_dedup(self, service):
        """Test multi-query search with deduplication"""
        queries = ["query1", "query2"]

        # Mock search function that returns duplicate results
        async def mock_search(query, top_k):
            return [
                {"id": "doc1", "score": 0.9, "content": "Result 1"},
                {"id": "doc2", "score": 0.8, "content": "Result 2"}
            ]

        result = await service.multi_query_search(
            queries=queries,
            search_function=mock_search,
            top_k_per_query=2,
            final_top_k=5,
            dedup_by_id=True
        )

        # Should deduplicate and return unique results
        assert len(result) <= 2  # At most 2 unique docs
        doc_ids = [r['id'] for r in result]
        assert len(doc_ids) == len(set(doc_ids))  # All unique

    @pytest.mark.asyncio
    async def test_multi_query_search_no_dedup(self, service):
        """Test multi-query search without deduplication"""
        queries = ["query1", "query2"]

        async def mock_search(query, top_k):
            return [
                {"id": "doc1", "score": 0.9}
            ]

        result = await service.multi_query_search(
            queries=queries,
            search_function=mock_search,
            top_k_per_query=1,
            final_top_k=10,
            dedup_by_id=False
        )

        # Should allow duplicates
        assert len(result) == 2  # Same doc appears twice

    @pytest.mark.asyncio
    async def test_multi_query_search_sorting(self, service):
        """Test that multi-query search sorts by score"""
        queries = ["query1"]

        async def mock_search(query, top_k):
            return [
                {"id": "doc1", "score": 0.5},
                {"id": "doc2", "score": 0.9},
                {"id": "doc3", "score": 0.7}
            ]

        result = await service.multi_query_search(
            queries=queries,
            search_function=mock_search,
            top_k_per_query=3,
            final_top_k=3
        )

        # Should be sorted by score (highest first)
        scores = [r['score'] for r in result]
        assert scores == sorted(scores, reverse=True)
        assert result[0]['id'] == "doc2"  # Highest score

    @pytest.mark.asyncio
    async def test_multi_query_search_final_top_k(self, service):
        """Test final_top_k limit"""
        queries = ["query1"]

        async def mock_search(query, top_k):
            return [
                {"id": f"doc{i}", "score": 0.9 - (i * 0.1)}
                for i in range(10)
            ]

        result = await service.multi_query_search(
            queries=queries,
            search_function=mock_search,
            top_k_per_query=10,
            final_top_k=3
        )

        assert len(result) == 3  # Limited to final_top_k

    @pytest.mark.asyncio
    async def test_llm_error_fallback(self):
        """Test fallback to original query on LLM error"""
        # Create LLM that raises error
        class ErrorLLM:
            async def generate_completion(self, messages, max_tokens=300, temperature=0.7):
                raise Exception("LLM service unavailable")

        service = HyDEService(llm_service=ErrorLLM())
        query = "Test query"

        result = await service.generate_hypothetical_document(query)

        # Should fallback to original query
        assert len(result) == 1
        assert result[0] == query

    @pytest.mark.asyncio
    async def test_query_provenance_tracking(self, service):
        """Test that search results track which query variant they came from"""
        queries = ["variant1", "variant2"]

        async def mock_search(query, top_k):
            return [{"id": f"doc_{query}", "score": 0.8}]

        result = await service.multi_query_search(
            queries=queries,
            search_function=mock_search,
            dedup_by_id=False
        )

        # Check provenance tracking
        assert all('from_query_variant' in r for r in result)
        assert any(r['from_query_variant'] == 0 for r in result)
        assert any(r['from_query_variant'] == 1 for r in result)
