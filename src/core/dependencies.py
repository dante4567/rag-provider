"""
FastAPI dependency injection for services and authentication
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Generator
import chromadb
from chromadb.config import Settings as ChromaSettings
import logging

from src.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

# ===== Security =====
security = HTTPBearer(auto_error=False)

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = {"/health", "/docs", "/redoc", "/openapi.json", "/"}


async def verify_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    settings: Settings = Depends(get_settings)
) -> bool:
    """
    Verify API authentication token

    Args:
        request: FastAPI request object
        credentials: HTTP Bearer credentials (optional)
        settings: Application settings

    Returns:
        bool: True if authenticated or auth not required

    Raises:
        HTTPException: 401 if authentication fails
        HTTPException: 503 if auth required but not configured
    """
    # If authentication is disabled, allow all requests
    if not settings.require_auth:
        return True

    # Check if endpoint is public
    if request.url.path in PUBLIC_ENDPOINTS:
        return True

    # Extract token from various sources
    token = None
    if credentials:
        token = credentials.credentials
    else:
        # Try X-API-Key header
        token = request.headers.get("X-API-Key")
        # Try query parameter (less secure, but convenient for testing)
        if not token:
            token = request.query_params.get("api_key")

    # Check if API key is configured
    if not settings.rag_api_key:
        logger.error("Authentication required but RAG_API_KEY not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is required but no API key is configured. Set RAG_API_KEY environment variable.",
        )

    # Validate token
    if not token or token != settings.rag_api_key:
        logger.warning(f"Authentication failed for request to {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Provide via Authorization header, X-API-Key header, or api_key query parameter.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True


# ===== ChromaDB Dependencies =====

_chroma_client: Optional[chromadb.Client] = None


def get_chroma_client(settings: Settings = Depends(get_settings)) -> chromadb.Client:
    """
    Get or create ChromaDB client (singleton pattern)

    Args:
        settings: Application settings

    Returns:
        chromadb.Client: ChromaDB HTTP client instance

    Raises:
        HTTPException: 503 if ChromaDB is unavailable
    """
    global _chroma_client

    if _chroma_client is None:
        try:
            _chroma_client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=settings.environment != "production"
                )
            )
            # Test connection
            _chroma_client.heartbeat()
            logger.info(f"Connected to ChromaDB at {settings.chroma_host}:{settings.chroma_port}")
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"ChromaDB is unavailable. Ensure it's running at {settings.chroma_host}:{settings.chroma_port}",
            )

    return _chroma_client


def get_collection(
    client: chromadb.Client = Depends(get_chroma_client),
    settings: Settings = Depends(get_settings)
):
    """
    Get or create ChromaDB collection

    Args:
        client: ChromaDB client
        settings: Application settings

    Returns:
        chromadb.Collection: Document collection

    Raises:
        HTTPException: 503 if collection cannot be accessed
    """
    try:
        collection = client.get_or_create_collection(
            name=settings.collection_name,
            metadata={
                "description": "RAG document embeddings and metadata",
                "version": settings.version,
            }
        )
        return collection
    except Exception as e:
        logger.error(f"Failed to access collection '{settings.collection_name}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to access collection: {str(e)}",
        )


def reset_chroma_client():
    """Reset ChromaDB client (for testing or reconnection)"""
    global _chroma_client
    _chroma_client = None


# ===== Service Dependencies =====

def get_document_service(settings: Settings = Depends(get_settings)):
    """Get Document Service instance"""
    from src.services.document_service import DocumentService
    return DocumentService(settings)


def get_llm_service(settings: Settings = Depends(get_settings)):
    """Get LLM Service instance"""
    from src.services.llm_service import LLMService
    return LLMService(settings)


def get_vector_service(
    collection = Depends(get_collection),
    settings: Settings = Depends(get_settings)
):
    """Get Vector Service instance"""
    from src.services.vector_service import VectorService
    return VectorService(collection, settings)


# ===== Validation Dependencies =====

async def validate_file_size(
    file_size_mb: float,
    settings: Settings = Depends(get_settings)
) -> bool:
    """Validate file size is within limits"""
    if file_size_mb > settings.max_file_size_mb:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({file_size_mb:.1f}MB) exceeds maximum ({settings.max_file_size_mb}MB)",
        )
    return True


async def validate_llm_provider(
    provider: str,
    settings: Settings = Depends(get_settings)
) -> bool:
    """Validate LLM provider has API key configured"""
    api_key = settings.get_llm_api_key(provider)
    if not api_key:
        available = settings.get_available_llm_providers()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"LLM provider '{provider}' has no API key configured. Available providers: {', '.join(available)}",
        )
    return True
