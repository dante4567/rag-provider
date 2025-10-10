"""
Statistics and monitoring endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import logging

from src.models.schemas import Stats, CostStats, TestLLMRequest, LLMProvider

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=Stats)
async def get_stats():
    """Get enhanced system statistics"""
    try:
        from app import collection, LLM_PROVIDERS, llm_clients, OCR_AVAILABLE

        results = collection.get()

        doc_ids = set()
        last_ingestion = None

        for metadata in results['metadatas']:
            doc_id = metadata.get('doc_id')
            if doc_id:
                doc_ids.add(doc_id)

            created_at = metadata.get('created_at')
            if created_at:
                if not last_ingestion or created_at > last_ingestion:
                    last_ingestion = created_at

        # Calculate storage
        total_chars = sum(len(doc) for doc in results['documents'])
        storage_mb = total_chars / (1024 * 1024)

        # LLM provider status
        llm_status = {}
        for provider in LLM_PROVIDERS.keys():
            llm_status[provider] = provider in llm_clients

        return Stats(
            total_documents=len(doc_ids),
            total_chunks=len(results['ids']),
            storage_used_mb=round(storage_mb, 2),
            last_ingestion=last_ingestion,
            llm_provider_status=llm_status,
            ocr_available=OCR_AVAILABLE
        )

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost/stats", response_model=CostStats)
async def get_cost_stats():
    """Get cost tracking statistics"""
    try:
        from src.services.rag_service import cost_tracking

        return {
            "total_cost_usd": cost_tracking["total_cost"],
            "daily_budget": 10.0,  # From config
            "budget_remaining": 10.0 - cost_tracking["total_cost"],
            "operations_count": len(cost_tracking["operations"]),
            "cost_by_provider": cost_tracking.get("cost_by_provider", {}),
            "daily_totals": cost_tracking["daily_totals"],
            "most_expensive_operation": max(cost_tracking["operations"], key=lambda x: x.get("cost", 0)) if cost_tracking["operations"] else None
        }
    except Exception as e:
        logger.error(f"Failed to get cost stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_available_models():
    """List all available LLM models with their pricing"""
    from app import LLM_PROVIDERS, llm_clients, MODEL_PRICING

    available_models = []

    for provider, config in LLM_PROVIDERS.items():
        if config["api_key"] and provider in llm_clients:
            for model_id, model_config in config.get("models", {}).items():
                pricing = MODEL_PRICING.get(model_id, {"input": 0, "output": 0})
                available_models.append({
                    "model_id": model_id,
                    "provider": provider,
                    "model_name": model_config["model_name"],
                    "max_tokens": model_config["max_tokens"],
                    "pricing_per_1m_tokens": pricing,
                    "available": True
                })

    return {
        "available_models": available_models,
        "total_models": len(available_models),
        "providers": list(llm_clients.keys())
    }


@router.post("/test-llm")
async def test_llm_provider(request: TestLLMRequest, _: bool = Depends(lambda: True)):
    """Test LLM provider or specific model

    Note: Authentication temporarily disabled for this endpoint.
    In production, use proper verify_token dependency.
    """
    try:
        from app import llm_clients
        from src.services.llm_service import LLMService
        from src.core.config import get_settings

        # Check if any LLM providers are available
        if not llm_clients:
            raise HTTPException(
                status_code=503,
                detail="No LLM providers are configured with valid API keys. Please set your API keys in the .env file."
            )

        settings = get_settings()
        llm_service = LLMService(settings)

        if request.model:
            # Test specific model
            response, cost = await llm_service.call_llm_with_model(request.prompt, request.model.value)
            return {
                "model": request.model.value,
                "prompt": request.prompt,
                "response": response,
                "cost_usd": cost,
                "success": True
            }
        elif request.provider:
            # Test provider with default model
            response = await llm_service.call_llm(request.prompt, request.provider.value)
            return {
                "provider": request.provider.value,
                "prompt": request.prompt,
                "response": response,
                "success": True
            }
        else:
            # Test default fallback chain
            response = await llm_service.call_llm(request.prompt)
            return {
                "provider": "fallback_chain",
                "prompt": request.prompt,
                "response": response,
                "success": True
            }
    except Exception as e:
        return {
            "provider": request.provider.value if request.provider else "unknown",
            "model": request.model.value if request.model else None,
            "prompt": request.prompt,
            "error": str(e),
            "success": False
        }
