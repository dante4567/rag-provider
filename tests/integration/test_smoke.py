"""
Smoke tests for CI/CD - Fast critical path tests only

These tests verify core functionality without making expensive LLM API calls.
Target: < 5 seconds total execution time
"""
import pytest
import requests

# Base URL for API (assumes Docker is running)
BASE_URL = "http://localhost:8001"


@pytest.fixture(scope="module")
def wait_for_service():
    """Wait for service to be ready before running tests"""
    import time
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


@pytest.mark.smoke
class TestHealthCheck:
    """Critical: Service must be healthy"""

    def test_health_endpoint(self, wait_for_service):
        """Health endpoint must return 200 OK"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "llm_providers" in data


@pytest.mark.smoke
class TestAPIValidation:
    """Critical: API must validate requests properly"""

    def test_ingest_requires_content(self, wait_for_service):
        """POST /ingest must reject empty requests"""
        response = requests.post(f"{BASE_URL}/ingest", json={})
        assert response.status_code == 422

    def test_search_requires_text(self, wait_for_service):
        """POST /search must reject empty requests"""
        response = requests.post(f"{BASE_URL}/search", json={})
        assert response.status_code == 422

    def test_chat_requires_question(self, wait_for_service):
        """POST /chat must reject empty requests"""
        response = requests.post(f"{BASE_URL}/chat", json={})
        assert response.status_code == 422


@pytest.mark.smoke
class TestSearchEndpoint:
    """Critical: Search must work (even with no results)"""

    def test_search_returns_response(self, wait_for_service):
        """POST /search must return valid response structure"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "nonexistent query that wont match anything", "top_k": 5},
            timeout=10
        )

        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "results" in data
        assert isinstance(data["results"], list)


@pytest.mark.smoke
class TestStatsEndpoint:
    """Important: Stats must be accessible"""

    def test_stats_available(self, wait_for_service):
        """GET /stats must return statistics"""
        response = requests.get(f"{BASE_URL}/stats", timeout=5)
        assert response.status_code == 200

        data = response.json()
        assert "total_documents" in data or "total_chunks" in data


@pytest.mark.smoke
class TestCoreEndpointsExist:
    """Critical: All documented endpoints must exist"""

    def test_ingest_endpoint_exists(self, wait_for_service):
        """POST /ingest must exist (not 404)"""
        response = requests.post(f"{BASE_URL}/ingest", json={})
        assert response.status_code != 404

    def test_search_endpoint_exists(self, wait_for_service):
        """POST /search must exist (not 404)"""
        response = requests.post(f"{BASE_URL}/search", json={})
        assert response.status_code != 404

    def test_chat_endpoint_exists(self, wait_for_service):
        """POST /chat must exist (not 404)"""
        response = requests.post(f"{BASE_URL}/chat", json={})
        assert response.status_code != 404

    def test_docs_endpoint_exists(self, wait_for_service):
        """GET /docs must exist"""
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        assert response.status_code == 200

    def test_openapi_endpoint_exists(self, wait_for_service):
        """GET /openapi.json must exist"""
        response = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
        assert response.status_code == 200

        # Must be valid JSON
        data = response.json()
        assert "openapi" in data or "swagger" in data
