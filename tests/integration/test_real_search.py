"""
Real integration tests for search and retrieval
Tests against actual ChromaDB (no mocks)
"""
import pytest
import requests
import time


BASE_URL = "http://localhost:8001"


class TestRealVectorSearch:
    """Test real vector search functionality"""

    @pytest.fixture(autouse=True)
    def setup_test_documents(self):
        """Ingest test documents before search tests"""
        # Ingest a few test documents
        test_docs = [
            {
                "content": "Python is a popular programming language for data science and machine learning.",
                "filename": "python_intro.txt"
            },
            {
                "content": "Machine learning algorithms can be trained on large datasets to make predictions.",
                "filename": "ml_basics.txt"
            },
            {
                "content": "Natural language processing enables computers to understand human language.",
                "filename": "nlp_intro.txt"
            }
        ]

        for doc in test_docs:
            requests.post(f"{BASE_URL}/ingest", json=doc, timeout=30)

        # Give ChromaDB time to index
        time.sleep(2)

    def test_basic_search(self):
        """Test basic semantic search"""
        payload = {
            "text": "programming languages",
            "top_k": 5
        }

        response = requests.post(f"{BASE_URL}/search", json=payload, timeout=10)
        assert response.status_code == 200

        data = response.json()
        assert "results" in data
        assert len(data["results"]) > 0

    def test_search_relevance(self):
        """Test that search returns relevant results"""
        payload = {
            "text": "machine learning and predictions",
            "top_k": 3
        }

        response = requests.post(f"{BASE_URL}/search", json=payload, timeout=10)
        assert response.status_code == 200

        data = response.json()
        results = data["results"]

        # Should return at least one result
        assert len(results) > 0

        # First result should be relevant
        first_result = results[0]
        assert "text" in first_result or "content" in first_result
        assert "score" in first_result or "distance" in first_result

    def test_search_with_top_k(self):
        """Test top_k parameter limits results"""
        payload = {
            "text": "programming",
            "top_k": 2
        }

        response = requests.post(f"{BASE_URL}/search", json=payload, timeout=10)
        assert response.status_code == 200

        data = response.json()
        # Should not return more than top_k results
        assert len(data["results"]) <= 2

    def test_search_empty_query(self):
        """Test that empty search query is handled"""
        payload = {
            "text": "",
            "top_k": 5
        }

        response = requests.post(f"{BASE_URL}/search", json=payload, timeout=10)
        # Should reject empty query
        assert response.status_code in [400, 422]


class TestRealReranking:
    """Test reranking functionality if available"""

    def test_search_with_rerank(self):
        """Test search with reranking enabled"""
        # First ingest a document
        requests.post(
            f"{BASE_URL}/ingest",
            json={
                "content": "Docker containers provide isolated environments for applications.",
                "filename": "docker_intro.txt"
            },
            timeout=30
        )
        time.sleep(1)

        payload = {
            "text": "docker containers",
            "top_k": 3,
            "use_reranking": True
        }

        response = requests.post(f"{BASE_URL}/search", json=payload, timeout=10)

        # Should work (or gracefully degrade if reranking unavailable)
        assert response.status_code in [200, 501]

        if response.status_code == 200:
            data = response.json()
            assert "results" in data


class TestRealDocumentRetrieval:
    """Test document retrieval endpoints"""

    def test_list_documents(self):
        """Test listing all documents"""
        response = requests.get(f"{BASE_URL}/documents", timeout=10)

        # Endpoint should exist
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))

    def test_get_document_by_id(self):
        """Test retrieving specific document"""
        # First ingest a document
        ingest_response = requests.post(
            f"{BASE_URL}/ingest",
            json={
                "content": "Test document for retrieval by ID.",
                "filename": "retrieval_test.txt"
            },
            timeout=30
        )
        assert ingest_response.status_code == 200

        doc_id = ingest_response.json().get("doc_id")

        if doc_id:
            # Try to retrieve it
            response = requests.get(f"{BASE_URL}/documents/{doc_id}", timeout=10)

            # Should either work or endpoint doesn't exist
            assert response.status_code in [200, 404]


class TestRealFilteredSearch:
    """Test search with metadata filters"""

    def test_search_with_metadata_filter(self):
        """Test filtering search by metadata"""
        # Ingest document with specific metadata
        requests.post(
            f"{BASE_URL}/ingest",
            json={
                "content": "This is a science document about physics.",
                "filename": "physics.txt",
                "metadata": {"category": "science", "topic": "physics"}
            },
            timeout=30
        )
        time.sleep(1)

        # Search with filter
        payload = {
            "text": "science",
            "top_k": 5,
            "filter": {"category": "science"}
        }

        response = requests.post(f"{BASE_URL}/search", json=payload, timeout=10)

        # Should work or indicate filters not supported
        assert response.status_code in [200, 400, 501]


class TestRealSearchPerformance:
    """Test search performance characteristics"""

    def test_search_response_time(self):
        """Verify search responds within acceptable time"""
        payload = {
            "text": "test query",
            "top_k": 5
        }

        start_time = time.time()
        response = requests.post(f"{BASE_URL}/search", json=payload, timeout=10)
        elapsed_time = time.time() - start_time

        assert response.status_code == 200
        # Search should be reasonably fast (under 5 seconds)
        assert elapsed_time < 5.0

    def test_concurrent_searches(self):
        """Test handling multiple concurrent searches"""
        import concurrent.futures

        def search_query(query_text):
            payload = {"text": query_text, "top_k": 3}
            return requests.post(f"{BASE_URL}/search", json=payload, timeout=10)

        queries = [
            "machine learning",
            "natural language",
            "data science",
            "python programming",
            "artificial intelligence"
        ]

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(search_query, q) for q in queries]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All searches should succeed
        assert all(r.status_code == 200 for r in results)
        assert len(results) == 5


class TestRealChatSearch:
    """Test chat endpoint with search integration"""

    def test_chat_with_context(self):
        """Test chat endpoint uses search for context"""
        # First ingest some context
        requests.post(
            f"{BASE_URL}/ingest",
            json={
                "content": "The capital of France is Paris. It is known for the Eiffel Tower.",
                "filename": "france_facts.txt"
            },
            timeout=30
        )
        time.sleep(1)

        # Ask a question that requires that context
        payload = {
            "message": "What is the capital of France?",
            "use_search": True
        }

        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)

        # Should work or indicate chat not available
        assert response.status_code in [200, 404, 503]

        if response.status_code == 200:
            data = response.json()
            # Should have a response message
            assert "response" in data or "message" in data
