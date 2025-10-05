"""
RAG Provider API - Refactored Version

This is the NEW version using the service layer.
Testing integration before replacing old app.py
"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

# Import our new modules
from src.core.config import Settings, get_settings
from src.core.dependencies import verify_token

# Create app
app = FastAPI(
    title="RAG Provider",
    version="2.1.0",
    description="Refactored RAG service with clean architecture"
)

# CORS - using new config
@app.on_event("startup")
async def startup():
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    )


# Simple health check using new config
@app.get("/health")
async def health_check(settings: Settings = Depends(get_settings)):
    """Health check endpoint - TESTING NEW ARCHITECTURE"""
    return {
        "status": "healthy",
        "version": settings.version,
        "app_name": settings.app_name,
        "environment": settings.environment,
        "test": "NEW ARCHITECTURE WORKING"
    }


# Test endpoint to verify services can be loaded
@app.get("/test/services")
async def test_services(settings: Settings = Depends(get_settings)):
    """Test if all services can be imported and initialized"""
    try:
        from src.services import DocumentService, LLMService, VectorService

        # Try to instantiate (without ChromaDB for now)
        doc_service = DocumentService(settings)
        llm_service = LLMService(settings)

        return {
            "status": "success",
            "services_loaded": {
                "DocumentService": True,
                "LLMService": True,
                "VectorService": "Requires ChromaDB connection"
            },
            "llm_providers_available": llm_service.get_available_providers(),
            "test": "Services can be imported and instantiated!"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "test": "INTEGRATION FAILED"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
