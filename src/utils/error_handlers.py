"""
Centralized error handling for the RAG Provider API
"""
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
import traceback

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base API error class"""

    def __init__(self, message: str, status_code: int = 500, details: Dict[str, Any] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(APIError):
    """Validation error"""

    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message, 422, details)


class AuthenticationError(APIError):
    """Authentication error"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, 401)


class AuthorizationError(APIError):
    """Authorization error"""

    def __init__(self, message: str = "Access denied"):
        super().__init__(message, 403)


class ResourceNotFoundError(APIError):
    """Resource not found error"""

    def __init__(self, resource: str, identifier: str = None):
        message = f"{resource} not found"
        if identifier:
            message += f": {identifier}"
        super().__init__(message, 404)


class ServiceUnavailableError(APIError):
    """Service unavailable error"""

    def __init__(self, service: str, message: str = None):
        default_message = f"{service} service is currently unavailable"
        super().__init__(message or default_message, 503)


class RateLimitError(APIError):
    """Rate limit exceeded error"""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, 429)


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle custom API errors"""
    logger.error(f"API Error: {exc.message} - Status: {exc.status_code}")

    content = {
        "error": {
            "type": exc.__class__.__name__,
            "message": exc.message,
            "status_code": exc.status_code
        }
    }

    if exc.details:
        content["error"]["details"] = exc.details

    return JSONResponse(
        status_code=exc.status_code,
        content=content
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions"""
    logger.error(f"HTTP Exception: {exc.detail} - Status: {exc.status_code}")

    content = {
        "error": {
            "type": "HTTPException",
            "message": exc.detail,
            "status_code": exc.status_code
        }
    }

    return JSONResponse(
        status_code=exc.status_code,
        content=content
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle Pydantic validation exceptions"""
    logger.error(f"Validation Error: {str(exc)}")

    content = {
        "error": {
            "type": "ValidationError",
            "message": "Invalid request data",
            "status_code": 422,
            "details": str(exc)
        }
    }

    return JSONResponse(
        status_code=422,
        content=content
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions"""
    logger.error(f"Unexpected error: {str(exc)}")
    logger.error(f"Traceback: {traceback.format_exc()}")

    content = {
        "error": {
            "type": "InternalServerError",
            "message": "An unexpected error occurred",
            "status_code": 500
        }
    }

    # Include traceback in development mode
    import os
    if os.getenv("DEBUG", "false").lower() == "true":
        content["error"]["traceback"] = traceback.format_exc()

    return JSONResponse(
        status_code=500,
        content=content
    )


def setup_error_handlers(app: FastAPI) -> None:
    """Set up error handlers for the FastAPI app"""

    # Custom API errors
    app.add_exception_handler(APIError, api_error_handler)

    # FastAPI HTTP exceptions
    app.add_exception_handler(HTTPException, http_exception_handler)

    # Pydantic validation errors
    from pydantic import ValidationError as PydanticValidationError
    app.add_exception_handler(PydanticValidationError, validation_exception_handler)

    # Catch-all for unexpected errors
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("Error handlers configured")