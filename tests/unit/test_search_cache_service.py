"""
Unit tests for SearchResultCache

Tests search result caching functionality including:
- Cache hit/miss logic
- LRU eviction
- TTL expiration
- Thread safety
- Statistics tracking
"""

import pytest
import time
from unittest.mock import Mock
from src.services.search_cache_service import SearchResultCache, get_search_cache, clear_search_cache


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def cache():
    """Create SearchResultCache instance with small size and TTL for testing"""
    return SearchResultCache(max_size=3, ttl_seconds=1)


@pytest.fixture
def sample_results():
    """Sample search results"""
    return [
        {"chunk_id": "1", "content": "Result 1", "relevance_score": 0.9},
        {"chunk_id": "2", "content": "Result 2", "relevance_score": 0.8},
        {"chunk_id": "3", "content": "Result 3", "relevance_score": 0.7}
    ]


# =============================================================================
# SearchResultCache Tests
# =============================================================================

class TestSearchResultCache:
    """Test the SearchResultCache class"""

    def test_init(self, cache):
        """Test cache initialization"""
        assert cache.max_size == 3
        assert cache.ttl_seconds == 1
        assert len(cache.cache) == 0
        assert cache.hits == 0
        assert cache.misses == 0

    def test_cache_miss(self, cache):
        """Test cache miss"""
        result = cache.get("test query", top_k=5, filter_dict=None, search_type="hybrid")

        assert result is None
        assert cache.misses == 1
        assert cache.hits == 0

    def test_cache_set_and_hit(self, cache, sample_results):
        """Test cache set and hit"""
        query = "test query"
        top_k = 5

        # Set value
        cache.set(query, top_k, sample_results, filter_dict=None, search_type="hybrid")
        assert len(cache.cache) == 1

        # Get value (should hit)
        cached = cache.get(query, top_k, filter_dict=None, search_type="hybrid")
        assert cached == sample_results
        assert cache.hits == 1
        assert cache.misses == 0

    def test_cache_ttl_expiration(self, cache, sample_results):
        """Test that cache entries expire after TTL"""
        query = "test query"
        top_k = 5

        # Set value
        cache.set(query, top_k, sample_results)

        # Immediate get should hit
        cached = cache.get(query, top_k)
        assert cached == sample_results
        assert cache.hits == 1

        # Wait for TTL to expire (1 second + buffer)
        time.sleep(1.1)

        # Get again should miss (expired)
        cached = cache.get(query, top_k)
        assert cached is None
        assert cache.hits == 1
        assert cache.misses == 1

    def test_cache_lru_eviction(self, cache, sample_results):
        """Test LRU eviction when cache is full"""
        # Fill cache to max size (3)
        cache.set("query1", 5, sample_results)
        cache.set("query2", 5, sample_results)
        cache.set("query3", 5, sample_results)
        assert len(cache.cache) == 3

        # Add one more (should evict oldest = query1)
        cache.set("query4", 5, sample_results)
        assert len(cache.cache) == 3

        # query1 should be evicted
        cached1 = cache.get("query1", 5)
        assert cached1 is None

        # query2, query3, query4 should still be present
        assert cache.get("query2", 5) is not None
        assert cache.get("query3", 5) is not None
        assert cache.get("query4", 5) is not None

    def test_cache_key_uniqueness(self, cache, sample_results):
        """Test that different parameters create different cache keys"""
        query = "test"

        # Different top_k
        cache.set(query, top_k=5, results=sample_results)
        cache.set(query, top_k=10, results=sample_results)
        assert len(cache.cache) == 2

        # Different search_type
        cache.set(query, top_k=5, results=sample_results, search_type="dense")
        assert len(cache.cache) == 3

    def test_cache_with_filters(self, cache, sample_results):
        """Test caching with filter dictionaries"""
        query = "test"
        filter1 = {"doc_type": "pdf"}
        filter2 = {"doc_type": "txt"}

        # Same query, different filters
        cache.set(query, 5, sample_results, filter_dict=filter1)
        cache.set(query, 5, sample_results, filter_dict=filter2)
        assert len(cache.cache) == 2

        # Get with correct filter should hit
        cached1 = cache.get(query, 5, filter_dict=filter1)
        assert cached1 == sample_results

        # Get with different filter should miss
        cached2 = cache.get(query, 5, filter_dict={"doc_type": "docx"})
        assert cached2 is None

    def test_get_stats(self, cache, sample_results):
        """Test cache statistics"""
        stats = cache.get_stats()

        assert stats['size'] == 0
        assert stats['max_size'] == 3
        assert stats['hits'] == 0
        assert stats['misses'] == 0
        assert stats['hit_rate'] == 0.0
        assert stats['ttl_seconds'] == 1

        # Add some hits and misses
        cache.get("query1", 5)  # Miss
        cache.set("query1", 5, sample_results)
        cache.get("query1", 5)  # Hit
        cache.get("query2", 5)  # Miss

        stats = cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 2
        assert stats['hit_rate'] == 1 / 3
        assert stats['total_requests'] == 3

    def test_clear_cache(self, cache, sample_results):
        """Test cache clearing"""
        cache.set("query1", 5, sample_results)
        cache.set("query2", 5, sample_results)

        # Force some hits/misses for stats
        cache.get("query1", 5)  # Hit
        cache.get("query3", 5)  # Miss

        assert len(cache.cache) == 2
        assert cache.hits > 0
        assert cache.misses > 0

        cache.clear()

        assert len(cache.cache) == 0
        assert cache.hits == 0
        assert cache.misses == 0


# =============================================================================
# Singleton Pattern Tests
# =============================================================================

class TestSingletonPattern:
    """Test singleton pattern for search cache"""

    def test_get_search_cache_singleton(self):
        """Test that get_search_cache returns singleton"""
        cache1 = get_search_cache()
        cache2 = get_search_cache()

        assert cache1 is cache2  # Same instance

    def test_clear_search_cache(self, sample_results):
        """Test global cache clearing"""
        cache = get_search_cache()
        cache.set("query", 5, sample_results)

        assert len(cache.cache) > 0

        clear_search_cache()
        assert len(cache.cache) == 0


# =============================================================================
# Thread Safety Tests
# =============================================================================

class TestThreadSafety:
    """Test thread safety of cache operations"""

    def test_concurrent_access(self, cache, sample_results):
        """Test that cache is thread-safe for concurrent access"""
        import threading

        errors = []

        def write_thread():
            try:
                for i in range(10):
                    cache.set(f"query{i}", 5, sample_results)
            except Exception as e:
                errors.append(e)

        def read_thread():
            try:
                for i in range(10):
                    cache.get(f"query{i}", 5)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=write_thread))
            threads.append(threading.Thread(target=read_thread))

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_results(self, cache):
        """Test caching empty results"""
        cache.set("query", 5, [])
        cached = cache.get("query", 5)

        assert cached == []

    def test_none_filter(self, cache, sample_results):
        """Test that None filter is handled correctly"""
        cache.set("query", 5, sample_results, filter_dict=None)
        cached = cache.get("query", 5, filter_dict=None)

        assert cached == sample_results

    def test_large_results(self, cache):
        """Test caching large result sets"""
        large_results = [
            {"chunk_id": str(i), "content": f"Content {i}", "score": 0.9}
            for i in range(100)
        ]

        cache.set("query", 100, large_results)
        cached = cache.get("query", 100)

        assert cached == large_results
        assert len(cached) == 100

    def test_special_characters_in_query(self, cache, sample_results):
        """Test queries with special characters"""
        special_queries = [
            "query with spaces",
            "query@with#special$chars",
            "query\nwith\nnewlines",
            "query\twith\ttabs",
            "中文查询",  # Chinese characters
            "🔍 emoji query"
        ]

        for query in special_queries:
            cache.set(query, 5, sample_results)
            cached = cache.get(query, 5)
            assert cached == sample_results

    def test_zero_top_k(self, cache, sample_results):
        """Test with top_k=0"""
        cache.set("query", 0, [])
        cached = cache.get("query", 0)

        assert cached == []

    def test_negative_top_k(self, cache, sample_results):
        """Test with negative top_k (edge case)"""
        # Should still work, just unusual
        cache.set("query", -1, sample_results)
        cached = cache.get("query", -1)

        assert cached == sample_results
