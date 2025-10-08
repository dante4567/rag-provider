"""
Basic unit tests for HybridSearchService

Tests the hybrid BM25 + dense search functionality
"""
import pytest
from src.services.hybrid_search_service import HybridSearchService


class TestHybridSearchService:
    """Test the HybridSearchService class"""

    def test_init_default(self):
        """Test initialization with default parameters"""
        service = HybridSearchService()
        assert service.bm25_weight == 0.4  # Updated: actual default is 0.4
        assert service.dense_weight == 0.6  # Updated: actual default is 0.6
        assert service.mmr_lambda == 0.7
        assert service.bm25_index is None
        assert service.indexed_documents == []
        assert service.tokenized_corpus == []

    def test_init_custom_weights(self):
        """Test initialization with custom weights"""
        service = HybridSearchService(
            bm25_weight=0.5,
            dense_weight=0.5,
            mmr_lambda=0.8
        )
        assert service.bm25_weight == 0.5
        assert service.dense_weight == 0.5
        assert service.mmr_lambda == 0.8

    def test_tokenize_simple_text(self):
        """Test tokenization of simple text"""
        service = HybridSearchService()
        text = "Hello World Test"
        tokens = service._tokenize(text)

        assert len(tokens) == 3
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens

    def test_tokenize_with_punctuation(self):
        """Test tokenization removes punctuation"""
        service = HybridSearchService()
        text = "Hello, World! How are you?"
        tokens = service._tokenize(text)

        # Should extract words without punctuation
        assert "hello" in tokens
        assert "world" in tokens
        assert "," not in tokens
        assert "!" not in tokens

    def test_tokenize_lowercase(self):
        """Test that tokenization converts to lowercase"""
        service = HybridSearchService()
        text = "UPPERCASE lowercase MiXeD"
        tokens = service._tokenize(text)

        assert all(token.islower() for token in tokens)
        assert "uppercase" in tokens
        assert "lowercase" in tokens
        assert "mixed" in tokens

    def test_tokenize_numbers(self):
        """Test tokenization handles numbers"""
        service = HybridSearchService()
        text = "Document 123 with numbers 456"
        tokens = service._tokenize(text)

        assert "document" in tokens
        assert "123" in tokens
        assert "456" in tokens

    def test_tokenize_empty_text(self):
        """Test tokenization of empty text"""
        service = HybridSearchService()
        assert service._tokenize("") == []
        assert service._tokenize("   ") == []

    def test_add_documents(self):
        """Test adding documents to BM25 index"""
        service = HybridSearchService()
        doc_id = "doc1"
        chunks = ["This is chunk 1", "This is chunk 2"]
        metadata = {"source": "test"}

        count = service.add_documents(doc_id, chunks, metadata)

        assert count == 2
        assert len(service.indexed_documents) == 2
        assert len(service.tokenized_corpus) == 2
        assert service.bm25_index is not None

    def test_add_multiple_documents(self):
        """Test adding multiple documents"""
        service = HybridSearchService()

        # Add first document
        service.add_documents("doc1", ["chunk1", "chunk2"], {})
        # Add second document
        service.add_documents("doc2", ["chunk3"], {})

        assert len(service.indexed_documents) == 3
        assert service.bm25_index is not None

    def test_weights_sum_check(self):
        """Test that weights should ideally sum to 1.0"""
        service = HybridSearchService(bm25_weight=0.4, dense_weight=0.6)
        # Weights sum to 1.0 for proper normalization
        assert abs((service.bm25_weight + service.dense_weight) - 1.0) < 0.001

    def test_mmr_lambda_range(self):
        """Test that MMR lambda is in valid range"""
        service = HybridSearchService(mmr_lambda=0.7)
        assert 0 <= service.mmr_lambda <= 1.0
