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
        from src.auth import auth

        # Patch module variables directly
        with patch.object(auth, 'REQUIRE_AUTH', False):
            request = Mock(spec=Request)
            request.url = Mock()
            request.url.path = "/api/ingest"
            credentials = Mock(spec=HTTPAuthorizationCredentials)
            credentials.credentials = "any_key"

            result = await auth.verify_token(request, credentials)
            assert result is True

    @pytest.mark.asyncio
    async def test_verify_token_public_endpoint(self):
        """Test public endpoint access without authentication"""
        from src.auth import auth

        # Patch module variables directly
        with patch.object(auth, 'REQUIRE_AUTH', True):
            request = Mock(spec=Request)
            request.url = Mock()
            request.url.path = "/health"
            credentials = None

            result = await auth.verify_token(request, credentials)
            assert result is True

    @pytest.mark.asyncio
    async def test_verify_token_valid_api_key(self):
        """Test successful authentication with valid API key"""
        from src.auth import auth

        # Patch module variables directly
        with patch.object(auth, 'REQUIRE_AUTH', True), \
             patch.object(auth, 'API_KEY', 'test_key'):

            request = Mock(spec=Request)
            request.url = Mock()
            request.url.path = "/api/ingest"

            credentials = Mock(spec=HTTPAuthorizationCredentials)
            credentials.credentials = "test_key"

            result = await auth.verify_token(request, credentials)
            assert result is True

    @pytest.mark.asyncio
    async def test_verify_token_invalid_api_key(self):
        """Test authentication failure with invalid API key"""
        from src.auth import auth

        # Patch module variables directly
        with patch.object(auth, 'REQUIRE_AUTH', True), \
             patch.object(auth, 'API_KEY', 'test_key'):

            request = Mock(spec=Request)
            request.url = Mock()
            request.url.path = "/api/ingest"

            credentials = Mock(spec=HTTPAuthorizationCredentials)
            credentials.credentials = "wrong_key"

            with pytest.raises(HTTPException) as exc_info:
                await auth.verify_token(request, credentials)

            assert exc_info.value.status_code == 401
            assert "Invalid or missing API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_token_no_api_key_configured(self):
        """Test authentication failure when no API key is configured"""
        from src.auth import auth

        # Patch module variables - REQUIRE_AUTH=True but API_KEY=None
        with patch.object(auth, 'REQUIRE_AUTH', True), \
             patch.object(auth, 'API_KEY', None):

            request = Mock(spec=Request)
            request.url = Mock()
            request.url.path = "/api/ingest"
            request.headers = Mock()
            request.headers.get = Mock(return_value=None)
            request.query_params = Mock()
            request.query_params.get = Mock(return_value=None)
            credentials = None

            with pytest.raises(HTTPException) as exc_info:
                await auth.verify_token(request, credentials)

            assert exc_info.value.status_code == 503
            assert "no API key is configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_verify_token_api_key_from_header(self):
        """Test authentication with API key from X-API-Key header"""
        from src.auth import auth

        # Patch module variables directly
        with patch.object(auth, 'REQUIRE_AUTH', True), \
             patch.object(auth, 'API_KEY', 'header_key'):

            request = Mock(spec=Request)
            request.url = Mock()
            request.url.path = "/api/ingest"
            request.headers = Mock()
            request.headers.get = Mock(return_value="header_key")
            request.query_params = Mock()
            request.query_params.get = Mock(return_value=None)

            credentials = None

            result = await auth.verify_token(request, credentials)
            assert result is True