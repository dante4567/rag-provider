"""
Unit tests for RerankingService

Tests cross-encoder reranking functionality including:
- Model lazy loading
- Basic reranking
- Top-K filtering
- Metadata generation
- Singleton pattern
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.services.reranking_service import RerankingService, get_reranking_service


# =============================================================================
# Fixtures (Module-level so all test classes can access)
# =============================================================================

@pytest.fixture
def mock_cross_encoder():
    """Create mock CrossEncoder model"""
    mock_model = Mock()
    # Mock predict to return scores based on content quality
    # Longer content gets higher scores (simulating relevance)
    def mock_predict(pairs):
        return [len(pair[1]) / 100.0 for pair in pairs]
    mock_model.predict = mock_predict
    return mock_model


# =============================================================================
# RerankingService Tests
# =============================================================================

class TestRerankingService:
    """Test the RerankingService class"""

    @pytest.fixture
    def service(self):
        """Create RerankingService instance"""
        return RerankingService(model_name="cross-encoder/ms-marco-MiniLM-L-12-v2")

    def test_init(self, service):
        """Test RerankingService initialization"""
        assert service.model_name == "cross-encoder/ms-marco-MiniLM-L-12-v2"
        assert service.model is None  # Model not loaded until first use

    def test_lazy_model_loading(self, service, mock_cross_encoder):
        """Test that model is loaded lazily on first use"""
        assert service.model is None

        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder):
            service._ensure_model_loaded()
            assert service.model is not None
            assert service.model == mock_cross_encoder

    def test_rerank_empty_results(self, service):
        """Test reranking with empty results"""
        results = service.rerank(query="test", results=[])
        assert results == []

    def test_rerank_basic(self, service, mock_cross_encoder):
        """Test basic reranking functionality"""
        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder):
            results = [
                {'content': 'Short text', 'metadata': {'id': '1'}},
                {'content': 'This is a much longer and more detailed text that should rank higher', 'metadata': {'id': '2'}},
                {'content': 'Medium length text here', 'metadata': {'id': '3'}}
            ]

            reranked = service.rerank(query="test query", results=results)

            # Should have rerank_score added
            assert all('rerank_score' in r for r in reranked)

            # Should be sorted by score (highest first)
            scores = [r['rerank_score'] for r in reranked]
            assert scores == sorted(scores, reverse=True)

            # Longest content should rank highest
            assert reranked[0]['metadata']['id'] == '2'

    def test_rerank_with_top_k(self, service, mock_cross_encoder):
        """Test reranking with top_k limit"""
        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder):
            results = [
                {'content': f'Content {i}' * 10, 'metadata': {'id': str(i)}}
                for i in range(10)
            ]

            reranked = service.rerank(query="test", results=results, top_k=3)

            assert len(reranked) == 3
            # All should have rerank_score
            assert all('rerank_score' in r for r in reranked)

    def test_rerank_preserves_original_fields(self, service, mock_cross_encoder):
        """Test that reranking preserves original result fields"""
        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder):
            results = [
                {
                    'content': 'Test content',
                    'metadata': {'filename': 'test.txt', 'custom_field': 'value'},
                    'chunk_id': 'abc123',
                    'relevance_score': 0.8
                }
            ]

            reranked = service.rerank(query="test", results=results)

            # Original fields should be preserved
            assert reranked[0]['metadata']['filename'] == 'test.txt'
            assert reranked[0]['metadata']['custom_field'] == 'value'
            assert reranked[0]['chunk_id'] == 'abc123'
            assert reranked[0]['relevance_score'] == 0.8

            # New field should be added
            assert 'rerank_score' in reranked[0]

    def test_rerank_with_metadata(self, service, mock_cross_encoder):
        """Test rerank_with_metadata method"""
        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder):
            results = [
                {'content': 'Content A' * 10, 'metadata': {'id': 'a'}},
                {'content': 'Content B' * 5, 'metadata': {'id': 'b'}},
                {'content': 'Content C' * 7, 'metadata': {'id': 'c'}}
            ]

            reranked, metadata = service.rerank_with_metadata(
                query="test",
                results=results,
                top_k=2
            )

            # Check reranked results
            assert len(reranked) == 2
            assert all('rerank_score' in r for r in reranked)

            # Check metadata
            assert metadata['total_results'] == 3
            assert metadata['returned_results'] == 2
            assert metadata['reranked'] is True
            assert metadata['model'] == service.model_name
            assert 'score_range' in metadata
            assert 'max' in metadata['score_range']
            assert 'min' in metadata['score_range']

    def test_rerank_with_metadata_empty_results(self, service):
        """Test rerank_with_metadata with empty results"""
        reranked, metadata = service.rerank_with_metadata(query="test", results=[])

        assert reranked == []
        assert metadata['total_results'] == 0
        assert metadata['reranked'] is False

    def test_model_reused_after_loading(self, service, mock_cross_encoder):
        """Test that model is reused and not reloaded"""
        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder) as mock_constructor:
            # First call loads model
            service._ensure_model_loaded()
            assert mock_constructor.call_count == 1

            # Second call should not reload
            service._ensure_model_loaded()
            assert mock_constructor.call_count == 1  # Still 1, not 2


# =============================================================================
# Singleton Pattern Tests
# =============================================================================

class TestSingletonPattern:
    """Test singleton pattern for reranking service"""

    def test_get_reranking_service_singleton(self):
        """Test that get_reranking_service returns singleton"""
        # Import fresh to reset singleton
        from src.services import reranking_service
        reranking_service._reranking_service = None

        service1 = get_reranking_service()
        service2 = get_reranking_service()

        assert service1 is service2  # Same instance

    def test_singleton_shares_model(self, mock_cross_encoder):
        """Test that singleton instances share the loaded model"""
        from src.services import reranking_service
        reranking_service._reranking_service = None

        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder):
            service1 = get_reranking_service()
            service1._ensure_model_loaded()

            service2 = get_reranking_service()

            # Both should reference the same model
            assert service2.model is not None
            assert service1.model is service2.model


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def service(self):
        return RerankingService()

    def test_rerank_results_without_content_field(self, service, mock_cross_encoder):
        """Test handling of results missing 'content' field"""
        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder):
            results = [
                {'metadata': {'id': '1'}},  # No content field
                {'content': 'Has content', 'metadata': {'id': '2'}}
            ]

            # Should not crash, treats missing content as empty string
            reranked = service.rerank(query="test", results=results)
            assert len(reranked) == 2

    def test_rerank_single_result(self, service, mock_cross_encoder):
        """Test reranking with single result"""
        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder):
            results = [{'content': 'Only one result', 'metadata': {'id': '1'}}]

            reranked = service.rerank(query="test", results=results)

            assert len(reranked) == 1
            assert 'rerank_score' in reranked[0]

    def test_rerank_with_none_top_k(self, service, mock_cross_encoder):
        """Test that None top_k returns all results"""
        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder):
            results = [
                {'content': f'Result {i}', 'metadata': {'id': str(i)}}
                for i in range(5)
            ]

            reranked = service.rerank(query="test", results=results, top_k=None)

            assert len(reranked) == 5  # All results returned

    def test_different_model_names(self):
        """Test initialization with different model names"""
        models = [
            "cross-encoder/ms-marco-MiniLM-L-12-v2",
            "cross-encoder/ms-marco-TinyBERT-L-2-v2",
            "cross-encoder/ms-marco-MiniLM-L-6-v2"
        ]

        for model_name in models:
            service = RerankingService(model_name=model_name)
            assert service.model_name == model_name
            assert service.model is None
