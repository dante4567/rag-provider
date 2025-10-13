"""
Unit tests for Gradio web UI
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add web-ui to path
sys.path.insert(0, os.path.dirname(__file__))

# Mock gradio before importing app
sys.modules['gradio'] = MagicMock()

import app


class TestHealthCheck:
    """Tests for health check functionality"""

    @patch('app.requests.get')
    def test_check_health_success(self, mock_get):
        """Test successful health check"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy", "chroma": "connected"}
        mock_get.return_value = mock_response

        result = app.check_health()

        assert "✅ Service Healthy" in result
        assert "healthy" in result
        mock_get.assert_called_once_with(f"{app.RAG_URL}/health", timeout=5)

    @patch('app.requests.get')
    def test_check_health_service_down(self, mock_get):
        """Test health check when service returns error"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = app.check_health()

        assert "❌ Service returned 500" in result

    @patch('app.requests.get')
    def test_check_health_connection_error(self, mock_get):
        """Test health check when connection fails"""
        mock_get.side_effect = Exception("Connection refused")

        result = app.check_health()

        assert "❌ Error" in result
        assert "Connection refused" in result


class TestDocumentUpload:
    """Tests for document upload functionality"""

    def test_upload_document_no_file(self):
        """Test upload with no file selected"""
        result = app.upload_document(None)

        assert "❌ No file selected" in result

    @patch('app.requests.post')
    @patch('builtins.open', create=True)
    def test_upload_document_success(self, mock_open, mock_post):
        """Test successful document upload"""
        # Mock file object
        mock_file = Mock()
        mock_file.name = "/tmp/test.pdf"

        # Mock file read
        mock_open.return_value.__enter__.return_value.read.return_value = b"fake pdf content"

        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "metadata": {
                "title": "Test Document",
                "tags": ["test"],
                "enrichment_cost_usd": 0.0001
            }
        }
        mock_post.return_value = mock_response

        result = app.upload_document(mock_file)

        assert "✅" in result
        assert "test.pdf" in result
        mock_post.assert_called_once()

    @patch('app.requests.post')
    @patch('builtins.open', create=True)
    def test_upload_document_api_error(self, mock_open, mock_post):
        """Test upload when API returns error"""
        mock_file = Mock()
        mock_file.name = "/tmp/test.pdf"

        mock_open.return_value.__enter__.return_value.read.return_value = b"content"

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_post.return_value = mock_response

        result = app.upload_document(mock_file)

        assert "❌" in result
        assert "test.pdf" in result

    @patch('app.requests.post')
    @patch('builtins.open', create=True)
    def test_upload_multiple_documents(self, mock_open, mock_post):
        """Test uploading multiple documents"""
        mock_file1 = Mock()
        mock_file1.name = "/tmp/test1.pdf"
        mock_file2 = Mock()
        mock_file2.name = "/tmp/test2.pdf"

        mock_open.return_value.__enter__.return_value.read.return_value = b"content"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "metadata": {}}
        mock_post.return_value = mock_response

        result = app.upload_document([mock_file1, mock_file2])

        assert "test1.pdf" in result
        assert "test2.pdf" in result
        assert mock_post.call_count == 2


class TestSearch:
    """Tests for search functionality"""

    @patch('app.requests.post')
    def test_search_documents_success(self, mock_post):
        """Test successful search"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "content": "Test content",
                    "metadata": {"title": "Test Doc", "tags": ["test"]},
                    "score": 0.95
                }
            ]
        }
        mock_post.return_value = mock_response

        result = app.search_documents("test query", 5)

        assert "Test content" in result
        assert "Test Doc" in result
        mock_post.assert_called_once()

    def test_search_documents_empty_query(self):
        """Test search with empty query"""
        result = app.search_documents("", 5)

        assert "❌" in result or "Please enter" in result

    @patch('app.requests.post')
    def test_search_documents_no_results(self, mock_post):
        """Test search with no results"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_post.return_value = mock_response

        result = app.search_documents("nonexistent", 5)

        assert "No results" in result or "0 results" in result


class TestChat:
    """Tests for chat functionality"""

    @patch('app.requests.post')
    def test_chat_success(self, mock_post):
        """Test successful chat query"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Test answer",
            "sources": [{"title": "Source 1"}],
            "cost_usd": 0.001
        }
        mock_post.return_value = mock_response

        result = app.chat_with_documents("test question", "groq/llama-3.1-8b-instant")

        assert "Test answer" in result
        mock_post.assert_called_once()

    def test_chat_empty_message(self):
        """Test chat with empty message"""
        result = app.chat_with_documents("", "groq/llama-3.1-8b-instant")

        assert "❌" in result or "Please enter" in result


class TestStatistics:
    """Tests for statistics functionality"""

    @patch('app.requests.get')
    def test_get_stats_success(self, mock_get):
        """Test successful stats retrieval"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_documents": 100,
            "total_cost_usd": 1.25,
            "collections": {"main": 100}
        }
        mock_get.return_value = mock_response

        result = app.get_stats()

        assert "100" in result
        assert "1.25" in result or "$1.25" in result
        mock_get.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
