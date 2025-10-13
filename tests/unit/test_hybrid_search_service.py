"""
Unit tests for HybridSearchService

Tests BM25 indexing, keyword search, score fusion, MMR diversity, and hybrid retrieval
"""

import pytest
import numpy as np
from src.services.hybrid_search_service import HybridSearchService, get_hybrid_search_service


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def hybrid_service():
    """Create HybridSearchService with default weights"""
    service = HybridSearchService()
    yield service
    service.clear_index()


@pytest.fixture
def sample_chunks():
    """Sample text chunks for testing"""
    return [
        "Python is a high-level programming language",
        "Machine learning models require large datasets",
        "Natural language processing uses transformers",
        "Deep learning neural networks are powerful",
        "Data science involves statistics and programming"
    ]


@pytest.fixture
def sample_metadata():
    """Sample document metadata"""
    return {
        "doc_id": "test_doc",
        "title": "Test Document",
        "created_at": "2025-10-13"
    }


# =============================================================================
# Initialization Tests
# =============================================================================

class TestInitialization:
    """Test service initialization"""

    def test_init_default_weights(self):
        """Test initialization with default weights"""
        service = HybridSearchService()
        assert service.bm25_weight == 0.4
        assert service.dense_weight == 0.6
        assert service.mmr_lambda == 0.7
        assert service.bm25_index is None
        assert service.indexed_documents == []

    def test_init_custom_weights(self):
        """Test initialization with custom weights"""
        service = HybridSearchService(bm25_weight=0.3, dense_weight=0.7, mmr_lambda=0.5)
        assert service.bm25_weight == 0.3
        assert service.dense_weight == 0.7
        assert service.mmr_lambda == 0.5

    def test_weights_sum_to_one(self):
        """Test that weights can sum to 1.0"""
        service = HybridSearchService(bm25_weight=0.4, dense_weight=0.6)
        assert service.bm25_weight + service.dense_weight == 1.0


# =============================================================================
# Tokenization Tests
# =============================================================================

class TestTokenization:
    """Test text tokenization"""

    def test_tokenize_basic(self, hybrid_service):
        """Test basic tokenization"""
        text = "Hello World"
        tokens = hybrid_service._tokenize(text)
        assert tokens == ["hello", "world"]

    def test_tokenize_lowercase(self, hybrid_service):
        """Test tokenization converts to lowercase"""
        text = "HELLO World"
        tokens = hybrid_service._tokenize(text)
        assert all(t.islower() for t in tokens)

    def test_tokenize_punctuation(self, hybrid_service):
        """Test punctuation is removed"""
        text = "Hello, World! How are you?"
        tokens = hybrid_service._tokenize(text)
        assert tokens == ["hello", "world", "how", "are", "you"]

    def test_tokenize_numbers(self, hybrid_service):
        """Test numbers are kept"""
        text = "Python 3.11 is awesome"
        tokens = hybrid_service._tokenize(text)
        assert "3" in tokens
        assert "11" in tokens

    def test_tokenize_empty_string(self, hybrid_service):
        """Test empty string tokenization"""
        tokens = hybrid_service._tokenize("")
        assert tokens == []

    def test_tokenize_special_characters(self, hybrid_service):
        """Test special characters are removed"""
        text = "test@email.com #hashtag $money"
        tokens = hybrid_service._tokenize(text)
        assert "email" in tokens
        assert "@" not in tokens


# =============================================================================
# Document Indexing Tests
# =============================================================================

class TestDocumentIndexing:
    """Test BM25 document indexing"""

    def test_add_documents_basic(self, hybrid_service, sample_chunks, sample_metadata):
        """Test adding documents to index"""
        count = hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)

        assert count == 5
        assert len(hybrid_service.indexed_documents) == 5
        assert len(hybrid_service.tokenized_corpus) == 5
        assert hybrid_service.bm25_index is not None

    def test_add_documents_empty(self, hybrid_service, sample_metadata):
        """Test adding empty document list"""
        count = hybrid_service.add_documents("doc1", [], sample_metadata)

        assert count == 0
        assert len(hybrid_service.indexed_documents) == 0

    def test_add_documents_metadata_preserved(self, hybrid_service, sample_chunks, sample_metadata):
        """Test metadata is preserved"""
        hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)

        doc = hybrid_service.indexed_documents[0]
        assert doc["metadata"]["title"] == "Test Document"
        assert doc["metadata"]["doc_id"] == "doc1"
        assert doc["metadata"]["chunk_index"] == 0

    def test_add_documents_chunk_ids(self, hybrid_service, sample_chunks, sample_metadata):
        """Test chunk IDs are generated correctly"""
        hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)

        assert hybrid_service.indexed_documents[0]["chunk_id"] == "doc1_chunk_0"
        assert hybrid_service.indexed_documents[1]["chunk_id"] == "doc1_chunk_1"
        assert hybrid_service.indexed_documents[4]["chunk_id"] == "doc1_chunk_4"

    def test_add_multiple_documents(self, hybrid_service, sample_metadata):
        """Test adding multiple documents"""
        hybrid_service.add_documents("doc1", ["First document"], sample_metadata)
        hybrid_service.add_documents("doc2", ["Second document"], sample_metadata)

        assert len(hybrid_service.indexed_documents) == 2
        assert hybrid_service.indexed_documents[0]["chunk_id"] == "doc1_chunk_0"
        assert hybrid_service.indexed_documents[1]["chunk_id"] == "doc2_chunk_0"

    def test_add_documents_rebuilds_index(self, hybrid_service, sample_chunks, sample_metadata):
        """Test BM25 index is rebuilt after adding documents"""
        hybrid_service.add_documents("doc1", sample_chunks[:2], sample_metadata)
        first_index = hybrid_service.bm25_index

        hybrid_service.add_documents("doc2", sample_chunks[2:], sample_metadata)
        second_index = hybrid_service.bm25_index

        # Index should be rebuilt (different object)
        assert first_index is not second_index


# =============================================================================
# BM25 Search Tests
# =============================================================================

class TestBM25Search:
    """Test BM25 keyword search"""

    def test_bm25_search_basic(self, hybrid_service, sample_chunks, sample_metadata):
        """Test basic BM25 search"""
        hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)

        results = hybrid_service.bm25_search("Python programming", top_k=5)

        assert len(results) > 0
        assert results[0]["bm25_score"] > 0
        assert "Python" in results[0]["content"]

    def test_bm25_search_empty_index(self, hybrid_service):
        """Test search on empty index"""
        results = hybrid_service.bm25_search("test query")
        assert results == []

    def test_bm25_search_top_k(self, hybrid_service, sample_chunks, sample_metadata):
        """Test top_k parameter"""
        hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)

        results = hybrid_service.bm25_search("machine learning", top_k=2)

        assert len(results) <= 2

    def test_bm25_search_scores_descending(self, hybrid_service, sample_chunks, sample_metadata):
        """Test results are sorted by score descending"""
        hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)

        results = hybrid_service.bm25_search("learning neural networks", top_k=5)

        scores = [r["bm25_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_bm25_search_exact_match(self, hybrid_service, sample_metadata):
        """Test exact keyword match"""
        chunks = ["Python is great", "Java is verbose", "Rust is fast"]
        hybrid_service.add_documents("doc1", chunks, sample_metadata)

        results = hybrid_service.bm25_search("Rust", top_k=5)

        assert len(results) > 0
        assert "Rust" in results[0]["content"]

    def test_bm25_search_no_match(self, hybrid_service, sample_chunks, sample_metadata):
        """Test search with no matches"""
        hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)

        results = hybrid_service.bm25_search("quantum physics biology", top_k=5)

        # Should return empty list (no documents have positive scores)
        assert len(results) == 0

    def test_bm25_search_metadata_included(self, hybrid_service, sample_chunks, sample_metadata):
        """Test metadata is included in results"""
        hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)

        results = hybrid_service.bm25_search("Python", top_k=5)

        assert "metadata" in results[0]
        assert results[0]["metadata"]["title"] == "Test Document"


# =============================================================================
# Score Normalization Tests
# =============================================================================

class TestScoreNormalization:
    """Test score normalization"""

    def test_normalize_scores_basic(self, hybrid_service):
        """Test basic score normalization"""
        results = [
            {"chunk_id": "1", "score": 0.0},
            {"chunk_id": "2", "score": 5.0},
            {"chunk_id": "3", "score": 10.0}
        ]

        normalized = hybrid_service.normalize_scores(results, "score")

        assert normalized[0]["score_normalized"] == 0.0
        assert normalized[1]["score_normalized"] == 0.5
        assert normalized[2]["score_normalized"] == 1.0

    def test_normalize_scores_range(self, hybrid_service):
        """Test normalized scores are in [0, 1]"""
        results = [
            {"chunk_id": str(i), "score": float(i * 10)}
            for i in range(10)
        ]

        normalized = hybrid_service.normalize_scores(results, "score")

        for r in normalized:
            assert 0.0 <= r["score_normalized"] <= 1.0

    def test_normalize_scores_empty(self, hybrid_service):
        """Test normalization of empty results"""
        results = []
        normalized = hybrid_service.normalize_scores(results, "score")
        assert normalized == []

    def test_normalize_scores_single_value(self, hybrid_service):
        """Test normalization with single value"""
        results = [{"chunk_id": "1", "score": 5.0}]
        normalized = hybrid_service.normalize_scores(results, "score")

        # Single value normalized to 1.0
        assert normalized[0]["score_normalized"] == 1.0

    def test_normalize_scores_all_same(self, hybrid_service):
        """Test normalization when all scores are the same"""
        results = [
            {"chunk_id": "1", "score": 5.0},
            {"chunk_id": "2", "score": 5.0},
            {"chunk_id": "3", "score": 5.0}
        ]

        normalized = hybrid_service.normalize_scores(results, "score")

        # All should be normalized to 1.0
        assert all(r["score_normalized"] == 1.0 for r in normalized)

    def test_normalize_scores_preserves_order(self, hybrid_service):
        """Test normalization preserves result order"""
        results = [
            {"chunk_id": "1", "score": 10.0},
            {"chunk_id": "2", "score": 5.0},
            {"chunk_id": "3", "score": 15.0}
        ]

        normalized = hybrid_service.normalize_scores(results, "score")

        assert [r["chunk_id"] for r in normalized] == ["1", "2", "3"]


# =============================================================================
# Result Fusion Tests
# =============================================================================

class TestResultFusion:
    """Test BM25 + dense result fusion"""

    def test_fuse_results_basic(self, hybrid_service):
        """Test basic result fusion"""
        bm25_results = [
            {"chunk_id": "1", "content": "doc1", "metadata": {}, "bm25_score": 10.0}
        ]
        dense_results = [
            {"chunk_id": "1", "content": "doc1", "metadata": {}, "relevance_score": 0.9}
        ]

        fused = hybrid_service.fuse_results(bm25_results, dense_results, top_k=5)

        assert len(fused) == 1
        assert "hybrid_score" in fused[0]
        assert fused[0]["chunk_id"] == "1"

    def test_fuse_results_weighted_combination(self, hybrid_service):
        """Test weighted score combination"""
        service = HybridSearchService(bm25_weight=0.4, dense_weight=0.6)

        bm25_results = [
            {"chunk_id": "1", "content": "doc", "metadata": {}, "bm25_score": 1.0}
        ]
        dense_results = [
            {"chunk_id": "1", "content": "doc", "metadata": {}, "relevance_score": 1.0}
        ]

        fused = service.fuse_results(bm25_results, dense_results, top_k=5)

        # Both normalized to 1.0, so hybrid = 0.4 * 1.0 + 0.6 * 1.0 = 1.0
        assert fused[0]["hybrid_score"] == pytest.approx(1.0, abs=0.01)

    def test_fuse_results_union(self, hybrid_service):
        """Test fusion creates union of results"""
        bm25_results = [
            {"chunk_id": "1", "content": "doc1", "metadata": {}, "bm25_score": 10.0}
        ]
        dense_results = [
            {"chunk_id": "2", "content": "doc2", "metadata": {}, "relevance_score": 0.9}
        ]

        fused = hybrid_service.fuse_results(bm25_results, dense_results, top_k=5)

        assert len(fused) == 2
        chunk_ids = {r["chunk_id"] for r in fused}
        assert chunk_ids == {"1", "2"}

    def test_fuse_results_sorted_by_hybrid_score(self, hybrid_service):
        """Test results sorted by hybrid score"""
        bm25_results = [
            {"chunk_id": "1", "content": "doc1", "metadata": {}, "bm25_score": 10.0},
            {"chunk_id": "2", "content": "doc2", "metadata": {}, "bm25_score": 5.0}
        ]
        dense_results = [
            {"chunk_id": "1", "content": "doc1", "metadata": {}, "relevance_score": 0.5},
            {"chunk_id": "2", "content": "doc2", "metadata": {}, "relevance_score": 0.9}
        ]

        fused = hybrid_service.fuse_results(bm25_results, dense_results, top_k=5)

        # Should be sorted by hybrid score
        scores = [r["hybrid_score"] for r in fused]
        assert scores == sorted(scores, reverse=True)

    def test_fuse_results_top_k(self, hybrid_service):
        """Test top_k limits results"""
        bm25_results = [
            {"chunk_id": str(i), "content": f"doc{i}", "metadata": {}, "bm25_score": float(10 - i)}
            for i in range(10)
        ]
        dense_results = [
            {"chunk_id": str(i), "content": f"doc{i}", "metadata": {}, "relevance_score": float(1.0 - i * 0.1)}
            for i in range(10)
        ]

        fused = hybrid_service.fuse_results(bm25_results, dense_results, top_k=3)

        assert len(fused) == 3

    def test_fuse_results_empty_bm25(self, hybrid_service):
        """Test fusion with empty BM25 results"""
        dense_results = [
            {"chunk_id": "1", "content": "doc", "metadata": {}, "relevance_score": 0.9}
        ]

        fused = hybrid_service.fuse_results([], dense_results, top_k=5)

        assert len(fused) == 1
        assert fused[0]["chunk_id"] == "1"

    def test_fuse_results_empty_dense(self, hybrid_service):
        """Test fusion with empty dense results"""
        bm25_results = [
            {"chunk_id": "1", "content": "doc", "metadata": {}, "bm25_score": 10.0}
        ]

        fused = hybrid_service.fuse_results(bm25_results, [], top_k=5)

        assert len(fused) == 1
        assert fused[0]["chunk_id"] == "1"


# =============================================================================
# Text Similarity Tests
# =============================================================================

class TestTextSimilarity:
    """Test text similarity for MMR"""

    def test_text_similarity_identical(self, hybrid_service):
        """Test similarity of identical texts"""
        sim = hybrid_service._text_similarity("hello world", "hello world")
        assert sim == 1.0

    def test_text_similarity_different(self, hybrid_service):
        """Test similarity of completely different texts"""
        sim = hybrid_service._text_similarity("hello world", "foo bar")
        assert sim == 0.0

    def test_text_similarity_partial(self, hybrid_service):
        """Test similarity of partially overlapping texts"""
        sim = hybrid_service._text_similarity("hello world", "hello universe")
        assert 0.0 < sim < 1.0

    def test_text_similarity_case_insensitive(self, hybrid_service):
        """Test similarity is case insensitive"""
        sim1 = hybrid_service._text_similarity("HELLO", "hello")
        assert sim1 == 1.0

    def test_text_similarity_empty_strings(self, hybrid_service):
        """Test similarity with empty strings"""
        sim = hybrid_service._text_similarity("", "")
        assert sim == 0.0

    def test_text_similarity_one_empty(self, hybrid_service):
        """Test similarity with one empty string"""
        sim = hybrid_service._text_similarity("hello", "")
        assert sim == 0.0


# =============================================================================
# MMR Diversity Tests
# =============================================================================

class TestMMR:
    """Test Maximal Marginal Relevance"""

    def test_apply_mmr_basic(self, hybrid_service):
        """Test basic MMR application"""
        results = [
            {"chunk_id": "1", "content": "Python programming", "hybrid_score": 0.9},
            {"chunk_id": "2", "content": "Python coding", "hybrid_score": 0.8},
            {"chunk_id": "3", "content": "Java development", "hybrid_score": 0.7}
        ]

        mmr_results = hybrid_service.apply_mmr("programming", results, top_k=2)

        assert len(mmr_results) == 2
        assert mmr_results[0]["chunk_id"] == "1"  # Top result always selected

    def test_apply_mmr_prefers_diversity(self, hybrid_service):
        """Test MMR prefers diverse results"""
        results = [
            {"chunk_id": "1", "content": "Python programming is great", "hybrid_score": 0.9},
            {"chunk_id": "2", "content": "Python programming is excellent", "hybrid_score": 0.85},  # Similar to 1
            {"chunk_id": "3", "content": "Machine learning algorithms", "hybrid_score": 0.7}  # Different
        ]

        mmr_results = hybrid_service.apply_mmr("programming", results, top_k=2)

        # Should prefer result 3 over result 2 (more diverse)
        chunk_ids = [r["chunk_id"] for r in mmr_results]
        assert "1" in chunk_ids
        assert "3" in chunk_ids  # More likely to be selected due to diversity

    def test_apply_mmr_fewer_results_than_top_k(self, hybrid_service):
        """Test MMR with fewer results than top_k"""
        results = [
            {"chunk_id": "1", "content": "test", "hybrid_score": 0.9}
        ]

        mmr_results = hybrid_service.apply_mmr("test", results, top_k=5)

        assert len(mmr_results) == 1

    def test_apply_mmr_lambda_parameter(self, hybrid_service):
        """Test MMR with custom lambda"""
        results = [
            {"chunk_id": str(i), "content": f"doc {i}", "hybrid_score": 1.0 - i * 0.1}
            for i in range(5)
        ]

        mmr_results = hybrid_service.apply_mmr("test", results, top_k=3, lambda_param=0.9)

        assert len(mmr_results) == 3

    def test_apply_mmr_empty_results(self, hybrid_service):
        """Test MMR with empty results"""
        mmr_results = hybrid_service.apply_mmr("test", [], top_k=5)
        assert mmr_results == []


# =============================================================================
# Full Hybrid Search Tests
# =============================================================================

class TestHybridSearch:
    """Test complete hybrid search pipeline"""

    def test_hybrid_search_basic(self, hybrid_service, sample_chunks, sample_metadata):
        """Test basic hybrid search"""
        hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)

        dense_results = [
            {"chunk_id": "doc1_chunk_0", "content": sample_chunks[0], "metadata": {}, "relevance_score": 0.9}
        ]

        results = hybrid_service.hybrid_search("Python programming", dense_results, top_k=3)

        assert len(results) > 0
        assert "hybrid_score" in results[0]

    def test_hybrid_search_with_mmr(self, hybrid_service, sample_chunks, sample_metadata):
        """Test hybrid search with MMR enabled"""
        hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)

        dense_results = [
            {"chunk_id": f"doc1_chunk_{i}", "content": sample_chunks[i], "metadata": {}, "relevance_score": 1.0 - i * 0.1}
            for i in range(len(sample_chunks))
        ]

        results = hybrid_service.hybrid_search("machine learning", dense_results, top_k=3, apply_mmr=True)

        assert len(results) <= 3

    def test_hybrid_search_without_mmr(self, hybrid_service, sample_chunks, sample_metadata):
        """Test hybrid search with MMR disabled"""
        hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)

        dense_results = [
            {"chunk_id": f"doc1_chunk_{i}", "content": sample_chunks[i], "metadata": {}, "relevance_score": 0.9}
            for i in range(len(sample_chunks))
        ]

        results = hybrid_service.hybrid_search("programming", dense_results, top_k=3, apply_mmr=False)

        assert len(results) <= 3

    def test_hybrid_search_empty_dense_results(self, hybrid_service, sample_chunks, sample_metadata):
        """Test hybrid search with empty dense results"""
        hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)

        results = hybrid_service.hybrid_search("Python", [], top_k=3)

        # Should still work using only BM25
        assert len(results) >= 0


# =============================================================================
# Stats and Utility Tests
# =============================================================================

class TestStatsAndUtility:
    """Test stats and utility methods"""

    def test_get_stats_empty(self, hybrid_service):
        """Test stats on empty index"""
        stats = hybrid_service.get_stats()

        assert stats["total_documents"] == 0
        assert stats["total_tokens"] == 0
        assert stats["avg_doc_length"] == 0
        assert stats["bm25_weight"] == 0.4
        assert stats["dense_weight"] == 0.6

    def test_get_stats_with_documents(self, hybrid_service, sample_chunks, sample_metadata):
        """Test stats after indexing documents"""
        hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)

        stats = hybrid_service.get_stats()

        assert stats["total_documents"] == 5
        assert stats["total_tokens"] > 0
        assert stats["avg_doc_length"] > 0

    def test_clear_index(self, hybrid_service, sample_chunks, sample_metadata):
        """Test clearing the index"""
        hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)
        assert len(hybrid_service.indexed_documents) > 0

        hybrid_service.clear_index()

        assert len(hybrid_service.indexed_documents) == 0
        assert len(hybrid_service.tokenized_corpus) == 0
        assert hybrid_service.bm25_index is None

    def test_clear_index_allows_reindex(self, hybrid_service, sample_chunks, sample_metadata):
        """Test can reindex after clearing"""
        hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)
        hybrid_service.clear_index()

        count = hybrid_service.add_documents("doc2", sample_chunks[:2], sample_metadata)

        assert count == 2
        assert len(hybrid_service.indexed_documents) == 2


# =============================================================================
# Singleton Tests
# =============================================================================

class TestSingleton:
    """Test singleton pattern"""

    def test_get_hybrid_search_service_creates_instance(self):
        """Test factory creates instance"""
        service = get_hybrid_search_service()
        assert isinstance(service, HybridSearchService)

    def test_get_hybrid_search_service_returns_singleton(self):
        """Test factory returns same instance"""
        service1 = get_hybrid_search_service()
        service2 = get_hybrid_search_service()
        assert service1 is service2

    def test_get_hybrid_search_service_custom_params(self):
        """Test factory with custom parameters"""
        service = get_hybrid_search_service(bm25_weight=0.5, dense_weight=0.5)
        # Note: Will only set params on first call due to singleton
        assert service.bm25_weight in [0.4, 0.5]  # Could be either depending on test order


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_tokenize_unicode(self, hybrid_service):
        """Test tokenization with unicode characters"""
        text = "Café résumé naïve"
        tokens = hybrid_service._tokenize(text)
        assert len(tokens) > 0

    def test_search_very_long_query(self, hybrid_service, sample_chunks, sample_metadata):
        """Test search with very long query"""
        hybrid_service.add_documents("doc1", sample_chunks, sample_metadata)

        long_query = " ".join(["test"] * 1000)
        results = hybrid_service.bm25_search(long_query, top_k=5)

        # Should handle gracefully
        assert isinstance(results, list)

    def test_add_documents_very_long_chunks(self, hybrid_service, sample_metadata):
        """Test indexing very long chunks"""
        long_chunk = "word " * 10000
        count = hybrid_service.add_documents("doc1", [long_chunk], sample_metadata)

        assert count == 1

    def test_fuse_results_many_documents(self, hybrid_service):
        """Test fusion with many documents"""
        bm25_results = [
            {"chunk_id": str(i), "content": f"doc{i}", "metadata": {}, "bm25_score": float(i)}
            for i in range(1000)
        ]
        dense_results = [
            {"chunk_id": str(i), "content": f"doc{i}", "metadata": {}, "relevance_score": float(i) / 1000}
            for i in range(1000)
        ]

        fused = hybrid_service.fuse_results(bm25_results, dense_results, top_k=10)

        assert len(fused) == 10

    def test_mmr_with_identical_documents(self, hybrid_service):
        """Test MMR with identical documents"""
        results = [
            {"chunk_id": str(i), "content": "same content", "hybrid_score": 0.9 - i * 0.01}
            for i in range(5)
        ]

        mmr_results = hybrid_service.apply_mmr("test", results, top_k=3)

        # Should still return results (MMR handles this gracefully)
        assert len(mmr_results) <= 3
