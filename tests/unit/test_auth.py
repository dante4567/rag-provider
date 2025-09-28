"""
Unit tests for authentication module
"""
import pytest
import os
from unittest.mock import Mock, patch
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from src.auth.auth import verify_token, security


class TestAuthentication:
    """Test authentication functionality"""

    @pytest.mark.asyncio
    async def test_verify_token_with_auth_disabled(self):
        """Test authentication bypass when REQUIRE_AUTH=false"""
        with patch.dict(os.environ, {"REQUIRE_AUTH": "false"}):
            from src.auth.auth import verify_token

            request = Mock(spec=Request)
            credentials = Mock(spec=HTTPAuthorizationCredentials)

            result = await verify_token(request, credentials)
            assert result is True

    @pytest.mark.asyncio
    async def test_verify_token_public_endpoint(self):
        """Test public endpoint access without authentication"""
        with patch.dict(os.environ, {"REQUIRE_AUTH": "true"}):
            from src.auth.auth import verify_token

            request = Mock(spec=Request)
            request.url.path = "/health"
            credentials = None

            result = await verify_token(request, credentials)
            assert result is True

    @pytest.mark.asyncio
    async def test_verify_token_valid_api_key(self):
        """Test successful authentication with valid API key"""
        with patch.dict(os.environ, {"REQUIRE_AUTH": "true", "RAG_API_KEY": "test_key"}):
            from src.auth.auth import verify_token

            request = Mock(spec=Request)
            request.url.path = "/api/ingest"

            credentials = Mock(spec=HTTPAuthorizationCredentials)
            credentials.credentials = "test_key"

            result = await verify_token(request, credentials)
            assert result is True

    @pytest.mark.asyncio
    async def test_verify_token_invalid_api_key(self):
        """Test authentication failure with invalid API key"""
        with patch.dict(os.environ, {"REQUIRE_AUTH": "true", "RAG_API_KEY": "test_key"}):
            from src.auth.auth import verify_token

            request = Mock(spec=Request)
            request.url.path = "/api/ingest"

            credentials = Mock(spec=HTTPAuthorizationCredentials)
            credentials.credentials = "wrong_key"

            with pytest.raises(HTTPException) as exc_info:
                await verify_token(request, credentials)

            assert exc_info.value.status_code == 401
            assert "Invalid or missing API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_token_no_api_key_configured(self):
        """Test authentication failure when no API key is configured"""
        with patch.dict(os.environ, {"REQUIRE_AUTH": "true"}, clear=True):
            from src.auth.auth import verify_token

            request = Mock(spec=Request)
            request.url.path = "/api/ingest"
            credentials = None

            with pytest.raises(HTTPException) as exc_info:
                await verify_token(request, credentials)

            assert exc_info.value.status_code == 503
            assert "no API key is configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_token_api_key_from_header(self):
        """Test authentication with API key from X-API-Key header"""
        with patch.dict(os.environ, {"REQUIRE_AUTH": "true", "RAG_API_KEY": "header_key"}):
            from src.auth.auth import verify_token

            request = Mock(spec=Request)
            request.url.path = "/api/ingest"
            request.headers = {"X-API-Key": "header_key"}
            request.query_params = {}

            credentials = None

            result = await verify_token(request, credentials)
            assert result is True