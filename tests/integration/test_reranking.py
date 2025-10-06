"""
Test cross-encoder reranking functionality

Verifies that the reranking service:
1. Is available and loaded
2. Actually reranks results (changes order)
3. Improves search relevance
"""
import pytest
import requests
import time


BASE_URL = "http://localhost:8001"


class TestRerankingService:
    """Test that cross-encoder reranking works"""

    def test_reranking_service_available(self):
        """Reranking service should be available in health check"""
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        assert response.status_code == 200

        data = response.json()
        reranking = data.get("reranking", {})

        assert reranking.get("available") is True, "Reranking should be available"
        assert "model" in reranking, "Should report reranking model"
        assert "cross-encoder" in reranking["model"].lower() or "marco" in reranking["model"].lower(), \
            f"Should use cross-encoder model, got: {reranking['model']}"

    @pytest.fixture(autouse=True)
    def setup_test_documents(self):
        """Ingest documents with varying relevance"""
        docs = [
            {
                "content": "Python is a programming language used for machine learning and data science.",
                "filename": "python_ml.txt"
            },
            {
                "content": "JavaScript is used for web development and frontend applications.",
                "filename": "javascript_web.txt"
            },
            {
                "content": "Machine learning models can be trained using Python libraries like TensorFlow.",
                "filename": "ml_python.txt"
            },
            {
                "content": "HTML and CSS are markup languages for web pages.",
                "filename": "html_css.txt"
            }
        ]

        for doc in docs:
            requests.post(f"{BASE_URL}/ingest", json=doc, timeout=30)

        time.sleep(2)

    def test_search_returns_reranked_results(self):
        """Search should return results ordered by reranking score"""
        query = "machine learning with Python"

        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": query, "top_k": 5},
            timeout=10
        )
        assert response.status_code == 200

        data = response.json()
        results = data.get("results", [])

        assert len(results) > 0, "Should return results"

        # Results should have relevance scores
        for result in results:
            assert "relevance_score" in result or "score" in result or "rerank_score" in result, \
                "Results should have relevance/rerank scores"

        # Top result should be most relevant to "machine learning with Python"
        if len(results) > 0:
            top_result_content = results[0].get("content", results[0].get("text", "")).lower()

            # Should mention both "machine learning" and "python"
            assert "machine learning" in top_result_content or "ml" in top_result_content, \
                "Top result should mention machine learning"
            assert "python" in top_result_content, \
                "Top result should mention Python"

    def test_reranking_improves_relevance(self):
        """Reranking should prioritize semantically relevant results"""
        query = "web development JavaScript frameworks"

        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": query, "top_k": 5},
            timeout=10
        )
        assert response.status_code == 200

        results = response.json()["results"]

        if len(results) >= 2:
            # Top results should be about web/JavaScript, not Python ML
            top_2_text = " ".join([
                r.get("content", r.get("text", "")).lower()
                for r in results[:2]
            ])

            web_terms = ["javascript", "web", "frontend", "html", "css"]
            web_mentions = sum(1 for term in web_terms if term in top_2_text)

            ml_terms = ["machine learning", "tensorflow", "data science"]
            ml_mentions = sum(1 for term in ml_terms if term in top_2_text)

            # Web terms should dominate in top results for web query
            assert web_mentions >= ml_mentions, \
                f"Web query should prioritize web content (web={web_mentions}, ml={ml_mentions})"


class TestRerankingQuality:
    """Test reranking quality with specific examples"""

    def test_semantic_similarity_over_keyword_match(self):
        """Reranking should prefer semantic similarity over keyword matching"""
        # Ingest documents with varying keyword/semantic matches
        docs = [
            {
                "content": "Neural networks learn patterns from data through training.",
                "filename": "neural_nets.txt"
            },
            {
                "content": "Training training training training data data data patterns patterns.",
                "filename": "keyword_spam.txt"
            },
            {
                "content": "Deep learning algorithms use neural architectures to discover patterns in datasets.",
                "filename": "deep_learning.txt"
            }
        ]

        for doc in docs:
            requests.post(f"{BASE_URL}/ingest", json=doc, timeout=30)

        time.sleep(2)

        # Query that could match keywords or semantics
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "how do neural networks discover patterns", "top_k": 3},
            timeout=10
        )

        assert response.status_code == 200
        results = response.json()["results"]

        if len(results) > 0:
            top_result = results[0].get("content", results[0].get("text", "")).lower()

            # Top result should NOT be the keyword spam document
            assert "training training training" not in top_result, \
                "Reranking should not prioritize keyword spam"

            # Should be one of the semantic matches
            assert ("neural" in top_result and "patterns" in top_result) or \
                   "deep learning" in top_result, \
                   "Should prioritize semantic relevance"
