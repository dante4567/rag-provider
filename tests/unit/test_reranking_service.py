"""
Unit tests for RerankingService

Tests cross-encoder reranking functionality including:
- Model lazy loading
- Basic reranking
- Top-K filtering
- Metadata generation
- Singleton pattern
- Advanced features (cache, batch, multi-stage)
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from src.services.reranking_service import (
    RerankingService,
    RerankingCache,
    get_reranking_service
)


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


# =============================================================================
# RerankingCache Tests (Phase 4 - Advanced Features)
# =============================================================================

class TestRerankingCache:
    """Test the RerankingCache class with LRU eviction and TTL"""

    @pytest.fixture
    def cache(self):
        """Create RerankingCache instance"""
        return RerankingCache(max_size=3, ttl_seconds=1)

    def test_cache_init(self, cache):
        """Test cache initialization"""
        assert cache.max_size == 3
        assert cache.ttl_seconds == 1
        assert len(cache.cache) == 0
        assert cache.hits == 0
        assert cache.misses == 0

    def test_cache_miss(self, cache):
        """Test cache miss"""
        results = [{'content': 'test', 'chunk_id': '1'}]
        cached = cache.get("query", results, top_k=5)

        assert cached is None
        assert cache.misses == 1
        assert cache.hits == 0

    def test_cache_set_and_hit(self, cache):
        """Test cache set and hit"""
        query = "test query"
        results = [{'content': 'test', 'chunk_id': '1'}]
        value = [{'content': 'test', 'chunk_id': '1', 'rerank_score': 0.9}]

        # Set value
        cache.set(query, results, top_k=5, value=value)
        assert len(cache.cache) == 1

        # Get value (should hit)
        cached = cache.get(query, results, top_k=5)
        assert cached == value
        assert cache.hits == 1
        assert cache.misses == 0

    def test_cache_ttl_expiration(self, cache):
        """Test that cache entries expire after TTL"""
        query = "test query"
        results = [{'content': 'test', 'chunk_id': '1'}]
        value = [{'content': 'test', 'chunk_id': '1', 'rerank_score': 0.9}]

        # Set value
        cache.set(query, results, top_k=5, value=value)

        # Immediate get should hit
        cached = cache.get(query, results, top_k=5)
        assert cached == value
        assert cache.hits == 1

        # Wait for TTL to expire (1 second + small buffer)
        time.sleep(1.1)

        # Get again should miss (expired)
        cached = cache.get(query, results, top_k=5)
        assert cached is None
        assert cache.hits == 1
        assert cache.misses == 1

    def test_cache_lru_eviction(self, cache):
        """Test LRU eviction when cache is full"""
        results1 = [{'content': 'test1', 'chunk_id': '1'}]
        results2 = [{'content': 'test2', 'chunk_id': '2'}]
        results3 = [{'content': 'test3', 'chunk_id': '3'}]
        results4 = [{'content': 'test4', 'chunk_id': '4'}]

        # Fill cache to max size (3)
        cache.set("query1", results1, 5, [{'rerank_score': 0.9}])
        cache.set("query2", results2, 5, [{'rerank_score': 0.8}])
        cache.set("query3", results3, 5, [{'rerank_score': 0.7}])
        assert len(cache.cache) == 3

        # Add one more (should evict oldest = query1)
        cache.set("query4", results4, 5, [{'rerank_score': 0.6}])
        assert len(cache.cache) == 3

        # query1 should be evicted
        cached1 = cache.get("query1", results1, 5)
        assert cached1 is None

        # query2, query3, query4 should still be present
        assert cache.get("query2", results2, 5) is not None
        assert cache.get("query3", results3, 5) is not None
        assert cache.get("query4", results4, 5) is not None

    def test_cache_key_uniqueness(self, cache):
        """Test that different queries/results create different cache keys"""
        results1 = [{'content': 'test1', 'chunk_id': '1'}]
        results2 = [{'content': 'test2', 'chunk_id': '2'}]

        cache.set("query1", results1, 5, [{'rerank_score': 0.9}])
        cache.set("query2", results1, 5, [{'rerank_score': 0.8}])  # Same results, different query
        cache.set("query1", results2, 5, [{'rerank_score': 0.7}])  # Same query, different results

        assert len(cache.cache) == 3

    def test_cache_get_stats(self, cache):
        """Test cache statistics"""
        stats = cache.get_stats()

        assert stats['size'] == 0
        assert stats['max_size'] == 3
        assert stats['hits'] == 0
        assert stats['misses'] == 0
        assert stats['hit_rate'] == 0.0
        assert stats['ttl_seconds'] == 1

        # Add some hits and misses
        results = [{'content': 'test', 'chunk_id': '1'}]
        cache.get("query1", results, 5)  # Miss
        cache.set("query1", results, 5, [{'score': 0.9}])
        cache.get("query1", results, 5)  # Hit
        cache.get("query2", results, 5)  # Miss

        stats = cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 2
        assert stats['hit_rate'] == 1 / 3

    def test_cache_clear(self, cache):
        """Test cache clearing"""
        results = [{'content': 'test', 'chunk_id': '1'}]
        cache.set("query1", results, 5, [{'score': 0.9}])
        cache.set("query2", results, 5, [{'score': 0.8}])

        assert len(cache.cache) == 2

        cache.clear()

        assert len(cache.cache) == 0
        assert cache.hits == 0
        assert cache.misses == 0


# =============================================================================
# Advanced Reranking Service Tests (Phase 4)
# =============================================================================

class TestAdvancedReranking:
    """Test advanced reranking features: cache integration, batch, multi-stage"""

    @pytest.fixture
    def service_with_cache(self):
        """Create RerankingService with caching enabled"""
        return RerankingService(
            model_name="cross-encoder/ms-marco-MiniLM-L-12-v2",
            enable_cache=True,
            cache_ttl=60
        )

    @pytest.fixture
    def service_no_cache(self):
        """Create RerankingService with caching disabled"""
        return RerankingService(
            model_name="cross-encoder/ms-marco-MiniLM-L-12-v2",
            enable_cache=False
        )

    def test_service_init_with_cache(self, service_with_cache):
        """Test service initialization with caching enabled"""
        assert service_with_cache.enable_cache is True
        assert service_with_cache.cache is not None
        assert isinstance(service_with_cache.cache, RerankingCache)

    def test_service_init_without_cache(self, service_no_cache):
        """Test service initialization with caching disabled"""
        assert service_no_cache.enable_cache is False
        assert service_no_cache.cache is None

    def test_rerank_uses_cache(self, service_with_cache, mock_cross_encoder):
        """Test that rerank uses cache when enabled"""
        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder):
            results = [
                {'content': 'Short text', 'chunk_id': '1'},
                {'content': 'Longer text content here', 'chunk_id': '2'}
            ]
            query = "test query"

            # First call should miss cache and rerank
            reranked1 = service_with_cache.rerank(query, results, top_k=5)
            assert service_with_cache.cache.misses == 1
            assert service_with_cache.cache.hits == 0

            # Second call should hit cache
            reranked2 = service_with_cache.rerank(query, results, top_k=5)
            assert service_with_cache.cache.hits == 1
            assert service_with_cache.cache.misses == 1

            # Results should be identical
            assert reranked1 == reranked2

    def test_rerank_cache_disabled_param(self, service_with_cache, mock_cross_encoder):
        """Test that use_cache=False bypasses cache"""
        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder):
            results = [{'content': 'test', 'chunk_id': '1'}]
            query = "test query"

            # First call with use_cache=False
            service_with_cache.rerank(query, results, use_cache=False)
            assert service_with_cache.cache.misses == 0  # Cache not checked
            assert service_with_cache.cache.hits == 0

    def test_get_cache_stats(self, service_with_cache):
        """Test get_cache_stats method"""
        stats = service_with_cache.get_cache_stats()

        assert stats['enabled'] is True
        assert 'size' in stats
        assert 'max_size' in stats
        assert 'hit_rate' in stats

    def test_get_cache_stats_disabled(self, service_no_cache):
        """Test get_cache_stats when cache is disabled"""
        stats = service_no_cache.get_cache_stats()
        assert stats['enabled'] is False

    def test_clear_cache(self, service_with_cache, mock_cross_encoder):
        """Test clear_cache method"""
        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder):
            results = [{'content': 'test', 'chunk_id': '1'}]

            # Add something to cache
            service_with_cache.rerank("query1", results)
            service_with_cache.rerank("query2", results)

            assert service_with_cache.cache.get_stats()['size'] > 0

            # Clear cache
            service_with_cache.clear_cache()
            assert service_with_cache.cache.get_stats()['size'] == 0


class TestBatchReranking:
    """Test batch reranking functionality"""

    @pytest.fixture
    def service(self):
        return RerankingService(enable_cache=False)

    def test_rerank_batch_empty(self, service):
        """Test batch reranking with empty inputs"""
        result = service.rerank_batch([], [])
        assert result == []

    def test_rerank_batch_length_mismatch(self, service):
        """Test that length mismatch raises ValueError"""
        with pytest.raises(ValueError, match="length mismatch"):
            service.rerank_batch(
                queries=["query1", "query2"],
                results_list=[[{'content': 'test'}]]  # Only 1 result list
            )

    def test_rerank_batch_basic(self, service, mock_cross_encoder):
        """Test basic batch reranking"""
        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder):
            queries = ["query1", "query2", "query3"]
            results_list = [
                [{'content': 'Result 1A', 'chunk_id': '1a'}, {'content': 'Result 1B', 'chunk_id': '1b'}],
                [{'content': 'Result 2A', 'chunk_id': '2a'}],
                [{'content': 'Result 3A', 'chunk_id': '3a'}, {'content': 'Result 3B', 'chunk_id': '3b'}]
            ]

            batch_results = service.rerank_batch(queries, results_list, top_k=5)

            # Should return 3 lists
            assert len(batch_results) == 3

            # Each should have rerank_score
            for result_list in batch_results:
                for result in result_list:
                    assert 'rerank_score' in result

    def test_rerank_batch_with_top_k(self, service, mock_cross_encoder):
        """Test batch reranking with top_k limit"""
        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder):
            queries = ["query1", "query2"]
            results_list = [
                [{'content': f'Result {i}', 'chunk_id': str(i)} for i in range(10)],
                [{'content': f'Result {i}', 'chunk_id': str(i)} for i in range(5)]
            ]

            batch_results = service.rerank_batch(queries, results_list, top_k=3)

            # First list should have 3 results (capped)
            assert len(batch_results[0]) == 3
            # Second list should have 3 results (capped)
            assert len(batch_results[1]) == 3


class TestMultiStageReranking:
    """Test multi-stage reranking (fast filter + precise rerank)"""

    @pytest.fixture
    def service(self):
        return RerankingService(
            model_name="cross-encoder/ms-marco-MiniLM-L-12-v2",
            fast_model_name="cross-encoder/ms-marco-TinyBERT-L-2-v2",
            enable_cache=False
        )

    @pytest.fixture
    def mock_fast_encoder(self):
        """Create mock fast CrossEncoder"""
        mock_model = Mock()
        def mock_predict(pairs):
            return [len(pair[1]) / 50.0 for pair in pairs]  # Different scoring
        mock_model.predict = mock_predict
        return mock_model

    def test_multistage_init(self, service):
        """Test that service has fast model configured"""
        assert service.fast_model_name == "cross-encoder/ms-marco-TinyBERT-L-2-v2"
        assert service.fast_model is None  # Not loaded yet

    def test_multistage_empty_results(self, service):
        """Test multi-stage with empty results"""
        result = service.rerank_multistage("query", [], stage1_top_k=50, stage2_top_k=10)
        assert result == []

    def test_multistage_fallback_to_single_stage(self, service, mock_cross_encoder):
        """Test that multi-stage falls back to single-stage for small result sets"""
        with patch('sentence_transformers.CrossEncoder', return_value=mock_cross_encoder):
            results = [
                {'content': f'Result {i}', 'chunk_id': str(i)}
                for i in range(5)  # Only 5 results
            ]

            # Request stage2_top_k=10, but only 5 results
            # Should use single-stage rerank
            reranked = service.rerank_multistage(
                "query",
                results,
                stage1_top_k=50,
                stage2_top_k=10
            )

            assert len(reranked) == 5
            assert all('rerank_score' in r for r in reranked)

    def test_multistage_two_stage_flow(self, service, mock_cross_encoder, mock_fast_encoder):
        """Test full two-stage reranking flow"""
        with patch('sentence_transformers.CrossEncoder') as mock_constructor:
            # Return different mocks for fast vs primary model
            def side_effect(model_name, max_length):
                if 'Tiny' in model_name:
                    return mock_fast_encoder
                else:
                    return mock_cross_encoder

            mock_constructor.side_effect = side_effect

            results = [
                {'content': f'Result {i}' * 10, 'chunk_id': str(i)}
                for i in range(100)  # Large result set
            ]

            # Stage 1: 100 → 50, Stage 2: 50 → 10
            reranked = service.rerank_multistage(
                "test query",
                results,
                stage1_top_k=50,
                stage2_top_k=10
            )

            # Should return 10 results
            assert len(reranked) == 10

            # Should have rerank_score from stage 2
            assert all('rerank_score' in r for r in reranked)

            # Should have fast_score from stage 1 (preserved in stage1_results)
            # Note: The final results may not have fast_score since they go through stage 2 rerank
            # which creates fresh result_copy objects
