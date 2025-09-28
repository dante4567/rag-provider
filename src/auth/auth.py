"""
Authentication module for RAG Provider API
Handles API key validation and endpoint protection
"""
import os
from fastapi import HTTPException, Request, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Security Configuration
API_KEY = os.getenv("RAG_API_KEY")
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "true").lower() == "true"
PUBLIC_ENDPOINTS = {"/health", "/docs", "/redoc", "/openapi.json"}

# Authentication setup
security = HTTPBearer(auto_error=False)


async def verify_token(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify API key for protected endpoints

    Args:
        request: FastAPI request object
        credentials: HTTP Bearer credentials

    Returns:
        bool: True if authentication successful

    Raises:
        HTTPException: If authentication fails
    """
    if not REQUIRE_AUTH:
        return True

    # Check if endpoint is public
    if request.url.path in PUBLIC_ENDPOINTS:
        return True

    # Check for API key in header or query parameter
    token = None
    if credentials:
        token = credentials.credentials
    else:
        token = request.headers.get("X-API-Key") or request.query_params.get("api_key")

    if not API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is required but no API key is configured"
        )

    if not token or token != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True