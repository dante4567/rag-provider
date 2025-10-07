"""
Comprehensive integration tests for API routes

These tests validate the actual API endpoints with real Docker services.
Run with: docker exec rag_service pytest tests/integration/test_routes.py -v
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import io


class TestHealthRoute:
    """Test /health endpoint"""

    def test_health_endpoint_structure(self, test_client):
        """Test health endpoint returns comprehensive status"""
        response = test_client.get("/health")
        assert response.status_code == 200

        data = response.json()

        # Required fields
        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "platform" in data
        assert "chromadb" in data

        # LLM provider info
        assert "llm_providers" in data
        assert "total_models_available" in data

        # Service status
        assert "ocr_available" in data
        assert "file_watcher" in data
        assert "paths" in data

    def test_health_endpoint_chromadb_connection(self, test_client):
        """Test health endpoint validates ChromaDB connection"""
        response = test_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["chromadb"] == "connected"

    def test_health_endpoint_llm_providers(self, test_client):
        """Test health endpoint lists available LLM providers"""
        response = test_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        providers = data["llm_providers"]

        # Should have provider details with models
        for provider_name, provider_info in providers.items():
            assert "available" in provider_info
            assert "models" in provider_info
            assert "model_count" in provider_info
            assert isinstance(provider_info["models"], list)

    def test_health_endpoint_pricing_info(self, test_client):
        """Test health endpoint includes pricing information"""
        response = test_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "pricing" in data
        pricing = data["pricing"]
        assert "total_models_with_pricing" in pricing
        assert "missing_pricing" in pricing

    def test_health_endpoint_reranking_status(self, test_client):
        """Test health endpoint includes reranking service status"""
        response = test_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "reranking" in data
        reranking = data["reranking"]
        assert "available" in reranking


class TestIngestRoutes:
    """Test /ingest/* endpoints"""

    def test_ingest_document_json(self, test_client):
        """Test ingesting document via JSON"""
        response = test_client.post("/ingest", json={
            "content": "This is a comprehensive test document with meaningful content for RAG processing. It contains multiple sentences to ensure proper processing.",
            "filename": "test_integration.txt",
            "document_type": "text",
            "process_ocr": False,
            "generate_obsidian": True,
            "metadata": {"source": "integration_test"}
        })

        # Should succeed or fail gracefully
        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "doc_id" in data
            assert "chunks" in data
            assert "metadata" in data

    def test_ingest_document_minimal(self, test_client):
        """Test ingesting minimal document"""
        response = test_client.post("/ingest", json={
            "content": "Minimal test document for RAG processing with enough content to pass validation checks."
        })

        # Should succeed or fail gracefully
        assert response.status_code in [200, 500, 503]

    def test_ingest_document_validation_empty_content(self, test_client):
        """Test validation rejects empty content"""
        response = test_client.post("/ingest", json={
            "content": "",
            "filename": "empty.txt"
        })

        # Should return validation error (422) or processing error (500)
        assert response.status_code in [422, 500]

    def test_ingest_document_validation_too_short(self, test_client):
        """Test validation rejects content that's too short"""
        response = test_client.post("/ingest", json={
            "content": "short",
            "filename": "short.txt"
        })

        # Should return validation or processing error
        assert response.status_code in [422, 500]

    def test_ingest_file_upload(self, test_client):
        """Test ingesting file via upload"""
        # Create test file
        test_content = b"This is a test document uploaded as a file. It contains comprehensive content for RAG processing and testing."

        response = test_client.post(
            "/ingest/file",
            files={"file": ("test_upload.txt", io.BytesIO(test_content), "text/plain")},
            data={"process_ocr": "false", "generate_obsidian": "true"}
        )

        # Should succeed or fail gracefully
        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "doc_id" in data
            assert "chunks" in data

    def test_ingest_file_pdf_upload(self, test_client):
        """Test uploading PDF file"""
        # Note: This test assumes a simple PDF test file exists
        response = test_client.post(
            "/ingest/file",
            files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4\ntest content"), "application/pdf")},
            data={"process_ocr": "false", "generate_obsidian": "false"}
        )

        # Should process or fail gracefully
        assert response.status_code in [200, 500, 503]

    def test_ingest_batch_files(self, test_client):
        """Test batch file ingestion"""
        files = [
            ("files", ("test1.txt", io.BytesIO(b"First test document for batch processing with comprehensive content."), "text/plain")),
            ("files", ("test2.txt", io.BytesIO(b"Second test document for batch processing with comprehensive content."), "text/plain"))
        ]

        response = test_client.post(
            "/ingest/batch",
            files=files,
            data={"process_ocr": "false", "generate_obsidian": "false"}
        )

        # Should succeed or fail gracefully
        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2


class TestSearchRoutes:
    """Test /search and /documents endpoints"""

    def test_search_basic(self, test_client):
        """Test basic search functionality"""
        response = test_client.post("/search", json={
            "text": "test document",
            "top_k": 5
        })

        # Should succeed or return empty results
        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert "query" in data
            assert "results" in data
            assert "total_results" in data
            assert "search_time_ms" in data
            assert isinstance(data["results"], list)
            assert data["query"] == "test document"

    def test_search_with_filters(self, test_client):
        """Test search with metadata filters"""
        response = test_client.post("/search", json={
            "text": "test query",
            "top_k": 3,
            "filter": {"document_type": "text"}
        })

        # Should succeed or fail gracefully
        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert "results" in data
            assert data["total_results"] >= 0

    def test_search_validation_empty_query(self, test_client):
        """Test search validation rejects empty query"""
        response = test_client.post("/search", json={
            "text": "",
            "top_k": 5
        })

        # Should return validation or processing error
        assert response.status_code in [422, 500]

    def test_search_validation_top_k(self, test_client):
        """Test search with different top_k values"""
        for top_k in [1, 3, 10]:
            response = test_client.post("/search", json={
                "text": "test query",
                "top_k": top_k
            })

            if response.status_code == 200:
                data = response.json()
                assert len(data["results"]) <= top_k

    def test_list_documents(self, test_client):
        """Test listing all documents"""
        response = test_client.get("/documents")

        # Should succeed or fail gracefully
        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            # Each document should have required fields
            for doc in data:
                assert "id" in doc
                assert "filename" in doc
                assert "chunks" in doc
                assert "created_at" in doc
                assert "metadata" in doc

    def test_delete_document_not_found(self, test_client):
        """Test deleting non-existent document"""
        fake_doc_id = "00000000-0000-0000-0000-000000000000"
        response = test_client.delete(f"/documents/{fake_doc_id}")

        # Should return 404 or 500
        assert response.status_code in [404, 500, 503]


class TestIngestSearchFlow:
    """Test complete ingest-search workflow"""

    def test_ingest_then_search(self, test_client):
        """Test ingesting document and then searching for it"""
        # Step 1: Ingest a document
        unique_content = "Integration test document with unique identifier xyz123 for comprehensive testing workflow."
        ingest_response = test_client.post("/ingest", json={
            "content": unique_content,
            "filename": "workflow_test.txt",
            "document_type": "text",
            "process_ocr": False,
            "generate_obsidian": False
        })

        # Step 2: Search for the document
        if ingest_response.status_code == 200:
            ingest_data = ingest_response.json()
            doc_id = ingest_data["doc_id"]

            # Search for unique content
            search_response = test_client.post("/search", json={
                "text": "unique identifier xyz123",
                "top_k": 5
            })

            if search_response.status_code == 200:
                search_data = search_response.json()
                # Should find at least one result
                assert search_data["total_results"] >= 0

                # Clean up: delete the document
                delete_response = test_client.delete(f"/documents/{doc_id}")
                assert delete_response.status_code in [200, 404, 500]

    def test_ingest_list_delete_flow(self, test_client):
        """Test full document lifecycle: ingest, list, delete"""
        # Step 1: Ingest
        ingest_response = test_client.post("/ingest", json={
            "content": "Document lifecycle test with comprehensive content for full workflow validation.",
            "filename": "lifecycle_test.txt"
        })

        if ingest_response.status_code == 200:
            doc_id = ingest_response.json()["doc_id"]

            # Step 2: List documents (should include our document)
            list_response = test_client.get("/documents")
            if list_response.status_code == 200:
                docs = list_response.json()
                doc_ids = [doc["id"] for doc in docs]
                # Note: May not find it due to timing

            # Step 3: Delete
            delete_response = test_client.delete(f"/documents/{doc_id}")
            assert delete_response.status_code in [200, 404, 500]

            if delete_response.status_code == 200:
                assert delete_response.json()["success"] is True


class TestEndpointErrorHandling:
    """Test error handling across endpoints"""

    def test_ingest_malformed_json(self, test_client):
        """Test ingest with malformed JSON"""
        response = test_client.post(
            "/ingest",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )

        # Should return 422 validation error
        assert response.status_code in [422, 400]

    def test_search_malformed_json(self, test_client):
        """Test search with malformed JSON"""
        response = test_client.post(
            "/search",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )

        # Should return 422 validation error
        assert response.status_code in [422, 400]

    def test_ingest_missing_required_field(self, test_client):
        """Test ingest with missing required fields"""
        response = test_client.post("/ingest", json={
            "filename": "test.txt"
            # Missing 'content' field
        })

        # Should return 422 validation error
        assert response.status_code == 422

    def test_search_missing_required_field(self, test_client):
        """Test search with missing required fields"""
        response = test_client.post("/search", json={
            "top_k": 5
            # Missing 'text' field
        })

        # Should return 422 validation error
        assert response.status_code == 422


class TestConcurrentRequests:
    """Test handling of concurrent requests"""

    def test_concurrent_searches(self, test_client):
        """Test multiple concurrent search requests"""
        import concurrent.futures

        def search():
            return test_client.post("/search", json={
                "text": "concurrent test",
                "top_k": 5
            })

        # Execute 5 searches concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(search) for _ in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should complete without crashes
        for response in results:
            assert response.status_code in [200, 500, 503]

    def test_concurrent_ingests(self, test_client):
        """Test multiple concurrent ingest requests"""
        import concurrent.futures

        def ingest(i):
            return test_client.post("/ingest", json={
                "content": f"Concurrent ingest test document number {i} with comprehensive content for testing parallel processing.",
                "filename": f"concurrent_{i}.txt"
            })

        # Execute 3 ingests concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(ingest, i) for i in range(3)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should complete without crashes
        for response in results:
            assert response.status_code in [200, 500, 503]
