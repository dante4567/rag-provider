"""
Health check and stats endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
import logging
import os
from src.core.dependencies import get_rag_service, get_chroma_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(
    rag_service = Depends(get_rag_service),
    chroma_client = Depends(get_chroma_client)
):
    """
    Comprehensive health check

    Validates:
    - ChromaDB connection
    - LLM API availability and models
    - Reranking service
    - Model pricing info
    - OCR and file watching
    """
    try:
        # Import static config (not services)
        from app import PLATFORM, IS_DOCKER, OCR_AVAILABLE, ENABLE_FILE_WATCH, PATHS

        # Test ChromaDB connection (gracefully handle failure)
        try:
            chroma_client.heartbeat()
            chromadb_status = "connected"
        except Exception as chroma_error:
            logger.warning(f"ChromaDB connection failed: {chroma_error}")
            chromadb_status = f"disconnected ({type(chroma_error).__name__})"

        # Get LLM service info
        available_providers = rag_service.llm_service.get_available_providers()
        available_models = rag_service.llm_service.get_available_models()

        # Build provider details with models
        provider_details = {}
        for provider in available_providers:
            provider_models = [m for m in available_models if m.startswith(f"{provider}/")]
            provider_details[provider] = {
                "available": True,
                "models": provider_models,
                "model_count": len(provider_models)
            }

        # Check pricing info completeness
        from src.services.llm_service import MODEL_PRICING
        pricing_status = {
            "total_models_with_pricing": len(MODEL_PRICING),
            "missing_pricing": [m for m in available_models if m not in MODEL_PRICING]
        }

        # Check reranking service
        enable_reranking = os.getenv("ENABLE_RERANKING", "true").lower() == "true"
        if enable_reranking:
            try:
                from src.services.reranking_service import get_reranking_service
                reranker = get_reranking_service()
                reranking_status = {
                    "available": True,
                    "model": reranker.model_name,
                    "loaded": reranker.model is not None
                }
            except Exception as e:
                reranking_status = {
                    "available": False,
                    "error": str(e)
                }
        else:
            reranking_status = {
                "available": False,
                "disabled": True,
                "reason": "ENABLE_RERANKING=false"
            }

        # Determine overall health status
        overall_status = "healthy" if chromadb_status == "connected" else "degraded"

        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "platform": PLATFORM,
            "docker": IS_DOCKER,

            # Database
            "chromadb": chromadb_status,

            # LLM Providers
            "llm_providers": provider_details,
            "total_models_available": len(available_models),

            # Pricing
            "pricing": pricing_status,

            # Services
            "reranking": reranking_status,
            "ocr_available": OCR_AVAILABLE,
            "file_watcher": "enabled" if ENABLE_FILE_WATCH else "disabled",

            # Paths
            "paths": PATHS
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {e}")
