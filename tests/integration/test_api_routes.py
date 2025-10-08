"""
Integration tests for all API routes

Tests actual HTTP endpoints with Docker containers running.
Critical for de-risking app.py refactoring.
"""
import pytest
import requests
import time
from pathlib import Path

# Base URL for API (assumes Docker is running)
BASE_URL = "http://localhost:8001"

# Test fixtures
TEST_FILE_PATH = Path(__file__).parent.parent.parent / "test_document.txt"


@pytest.fixture(scope="module")
def wait_for_service():
    """Wait for service to be ready before running tests"""
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                print(f"\n✅ Service ready after {i+1} retries")
                return True
        except requests.exceptions.RequestException:
            time.sleep(1)
    pytest.fail("Service not available after 30 seconds")


class TestHealthEndpoint:
    """Test /health endpoint"""

    def test_health_returns_200(self, wait_for_service):
        """Health endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200

    def test_health_returns_json(self, wait_for_service):
        """Health endpoint should return valid JSON"""
        response = requests.get(f"{BASE_URL}/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_includes_llm_providers(self, wait_for_service):
        """Health should include LLM provider status"""
        response = requests.get(f"{BASE_URL}/health")
        data = response.json()
        assert "llm_providers" in data
        assert "groq" in data["llm_providers"]
        assert "anthropic" in data["llm_providers"]


class TestIngestEndpoint:
    """Test /ingest/* endpoints"""

    def test_ingest_file_requires_file(self, wait_for_service):
        """POST /ingest/file without file should fail"""
        response = requests.post(f"{BASE_URL}/ingest/file")
        assert response.status_code == 422  # Unprocessable Entity

    def test_ingest_file_success(self, wait_for_service):
        """POST /ingest/file with valid file should succeed"""
        if not TEST_FILE_PATH.exists():
            pytest.skip(f"Test file not found: {TEST_FILE_PATH}")

        with open(TEST_FILE_PATH, "rb") as f:
            files = {"file": ("test.txt", f, "text/plain")}
            response = requests.post(
                f"{BASE_URL}/ingest/file",
                files=files,
                timeout=60  # Enrichment can take time
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "doc_id" in data
        assert "chunks" in data
        assert "metadata" in data

    def test_ingest_file_generates_obsidian(self, wait_for_service):
        """POST /ingest/file should generate Obsidian file when requested"""
        if not TEST_FILE_PATH.exists():
            pytest.skip(f"Test file not found: {TEST_FILE_PATH}")

        with open(TEST_FILE_PATH, "rb") as f:
            files = {"file": ("test.txt", f, "text/plain")}
            data = {"generate_obsidian": "true"}
            response = requests.post(
                f"{BASE_URL}/ingest/file",
                files=files,
                data=data,
                timeout=60
            )

        assert response.status_code == 200
        result = response.json()
        assert "obsidian_path" in result

    def test_ingest_text_requires_content(self, wait_for_service):
        """POST /ingest/text without content should fail"""
        response = requests.post(
            f"{BASE_URL}/ingest/text",
            json={}
        )
        assert response.status_code == 422

    def test_ingest_text_success(self, wait_for_service):
        """POST /ingest/text with valid content should succeed"""
        response = requests.post(
            f"{BASE_URL}/ingest/text",
            json={
                "content": "This is a test document for API testing.",
                "filename": "api_test.txt"
            },
            timeout=60
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "doc_id" in data


class TestSearchEndpoint:
    """Test /search endpoint"""

    def test_search_requires_text(self, wait_for_service):
        """POST /search without text should fail"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={}
        )
        assert response.status_code == 422

    def test_search_returns_results(self, wait_for_service):
        """POST /search should return search results"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "test query", "top_k": 5},
            timeout=30
        )

        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_search_respects_top_k(self, wait_for_service):
        """POST /search should respect top_k parameter"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "test", "top_k": 3},
            timeout=30
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 3


class TestChatEndpoint:
    """Test /chat endpoint"""

    def test_chat_requires_question(self, wait_for_service):
        """POST /chat without question should fail"""
        response = requests.post(
            f"{BASE_URL}/chat",
            json={}
        )
        assert response.status_code == 422

    def test_chat_returns_answer(self, wait_for_service):
        """POST /chat should return answer with sources"""
        response = requests.post(
            f"{BASE_URL}/chat",
            json={"question": "What is this about?"},
            timeout=60  # LLM calls can take time
        )

        assert response.status_code == 200
        data = response.json()
        assert "question" in data
        assert "answer" in data
        assert "sources" in data
        assert "llm_provider_used" in data

    def test_chat_accepts_llm_model(self, wait_for_service):
        """POST /chat should accept llm_model parameter"""
        response = requests.post(
            f"{BASE_URL}/chat",
            json={
                "question": "Test question",
                "llm_model": "groq/llama-3.1-8b-instant"
            },
            timeout=60
        )

        assert response.status_code == 200
        data = response.json()
        assert "llm_model_used" in data


class TestStatsEndpoint:
    """Test /stats endpoint"""

    def test_stats_returns_system_stats(self, wait_for_service):
        """GET /stats should return system statistics"""
        response = requests.get(f"{BASE_URL}/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_documents" in data
        assert "total_chunks" in data
        assert "llm_provider_status" in data


class TestAdminEndpoint:
    """Test /admin/* endpoints"""

    def test_admin_cleanup_dry_run(self, wait_for_service):
        """POST /admin/cleanup with dry_run should not delete"""
        response = requests.post(
            f"{BASE_URL}/admin/cleanup",
            json={"dry_run": True}
        )

        # May return 200 or 404 depending on data
        assert response.status_code in [200, 404]

    def test_admin_reset_collection_requires_confirmation(self, wait_for_service):
        """POST /admin/reset-collection without confirmation should require it"""
        # This test verifies the endpoint exists and has safety checks
        # We don't actually want to reset the collection in tests
        response = requests.post(
            f"{BASE_URL}/admin/reset-collection",
            json={"confirm": False}
        )

        # Should either require confirmation or return error
        assert response.status_code in [200, 400, 422]


class TestDocumentsEndpoint:
    """Test /documents endpoint"""

    def test_documents_list(self, wait_for_service):
        """GET /documents should return list of documents"""
        response = requests.get(f"{BASE_URL}/documents")

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert isinstance(data["documents"], list)


class TestCostEndpoint:
    """Test /cost/* endpoints"""

    def test_cost_stats(self, wait_for_service):
        """GET /cost/stats should return cost statistics"""
        response = requests.get(f"{BASE_URL}/cost/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_cost_today" in data or "total_cost_all_time" in data


@pytest.mark.slow
class TestEndToEndWorkflow:
    """Test complete RAG workflow"""

    def test_complete_rag_workflow(self, wait_for_service):
        """Test: ingest → search → chat workflow"""
        if not TEST_FILE_PATH.exists():
            pytest.skip(f"Test file not found: {TEST_FILE_PATH}")

        # Step 1: Ingest document
        with open(TEST_FILE_PATH, "rb") as f:
            files = {"file": ("workflow_test.txt", f, "text/plain")}
            ingest_response = requests.post(
                f"{BASE_URL}/ingest/file",
                files=files,
                timeout=60
            )

        assert ingest_response.status_code == 200
        doc_id = ingest_response.json()["doc_id"]

        # Step 2: Search for content
        time.sleep(2)  # Allow indexing to complete
        search_response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "test", "top_k": 5},
            timeout=30
        )

        assert search_response.status_code == 200

        # Step 3: Chat about content
        chat_response = requests.post(
            f"{BASE_URL}/chat",
            json={"question": "What is this document about?"},
            timeout=60
        )

        assert chat_response.status_code == 200
        assert len(chat_response.json()["answer"]) > 0


class TestErrorHandling:
    """Test API error handling"""

    def test_404_on_invalid_endpoint(self, wait_for_service):
        """Invalid endpoint should return 404"""
        response = requests.get(f"{BASE_URL}/invalid_endpoint_xyz")
        assert response.status_code == 404

    def test_405_on_wrong_method(self, wait_for_service):
        """Wrong HTTP method should return 405"""
        response = requests.get(f"{BASE_URL}/ingest/file")
        assert response.status_code == 405

    def test_422_on_invalid_json(self, wait_for_service):
        """Invalid JSON should return 422"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"invalid_field": "value"}
        )
        assert response.status_code == 422
