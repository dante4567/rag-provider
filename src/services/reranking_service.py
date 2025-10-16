"""
Reranking Service - Improve retrieval quality

Supports multiple reranking providers:
- Self-hosted: Mixedbread mxbai-rerank-large-v2 (BEIR 57.49, free after download)
- Voyage Rerank: Cloud API ($0.05/1000, fast, no cold start)
- Cohere Rerank: Cloud API ($2/1000, SOTA quality)
"""

import logging
from typing import List, Dict, Tuple
import os

logger = logging.getLogger(__name__)


class RerankingService:
    """Rerank search results using self-hosted or cloud providers"""

    def __init__(self, provider: str = None, model_name: str = "mixedbread-ai/mxbai-rerank-large-v2"):
        """
        Initialize reranking service

        Args:
            provider: "self-hosted", "voyage", or "cohere" (defaults to RERANKER_PROVIDER env or "self-hosted")
            model_name: Model to use for self-hosted reranking
        """
        self.provider = provider or os.getenv("RERANKER_PROVIDER", "self-hosted")
        self.model_name = model_name
        self.model = None

        if self.provider == "self-hosted":
            logger.info(f"🎯 Initializing self-hosted reranking with {model_name}")
        elif self.provider == "voyage":
            logger.info("🎯 Initializing Voyage reranking (cloud)")
        elif self.provider == "cohere":
            logger.info("🎯 Initializing Cohere reranking (cloud)")
        else:
            logger.warning(f"Unknown provider {self.provider}, falling back to self-hosted")
            self.provider = "self-hosted"

    def _ensure_model_loaded(self):
        """Lazy load the cross-encoder model on first use"""
        if self.model is None:
            try:
                import torch
                from sentence_transformers import CrossEncoder
                logger.info(f"📥 Loading {self.model_name} (first use only, ~3GB download)...")

                # Determine device (CPU or CUDA)
                device = "cuda" if torch.cuda.is_available() else "cpu"
                logger.info(f"🖥️  Using device: {device}")

                # Load model with explicit device handling for PyTorch 2.x
                # Use default_device context to avoid meta tensor issues
                with torch.device(device):
                    self.model = CrossEncoder(
                        self.model_name,
                        max_length=512,
                        device=device
                    )

                logger.info("✅ Reranking model loaded successfully")
            except ImportError as e:
                logger.error(f"❌ Import error: {e}")
                logger.error("❌ sentence-transformers not installed. Run: pip install sentence-transformers")
                raise
            except Exception as e:
                logger.error(f"❌ Failed to load reranking model: {e}")
                logger.error(f"   Error type: {type(e).__name__}")
                logger.error(f"   PyTorch version: {torch.__version__ if 'torch' in locals() else 'unknown'}")
                raise

    def _rerank_with_voyage(self, query: str, results: List[Dict], top_k: int = None) -> List[Dict]:
        """Rerank using Voyage AI API"""
        try:
            import voyageai
            vo = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))

            # Prepare documents
            documents = [result.get('content', '') for result in results]

            # Call Voyage reranking API
            reranking = vo.rerank(query=query, documents=documents, model="rerank-2", top_k=top_k)

            # Map back to results with scores
            scored_results = []
            for item in reranking.results:
                result_copy = results[item.index].copy()
                result_copy['rerank_score'] = item.relevance_score
                scored_results.append(result_copy)

            logger.info(f"✅ Voyage reranked {len(results)} → {len(scored_results)} results")
            return scored_results

        except Exception as e:
            logger.error(f"❌ Voyage reranking failed: {e}")
            logger.warning("⚠️ Falling back to original ranking")
            return results[:top_k] if top_k else results

    def rerank(
        self,
        query: str,
        results: List[Dict],
        top_k: int = None
    ) -> List[Dict]:
        """
        Rerank search results using configured provider

        Args:
            query: User's search query
            results: List of search results (must have 'content' field)
            top_k: Number of top results to return (None = return all, ranked)

        Returns:
            Reranked results with added 'rerank_score' field
        """
        if not results:
            return []

        # Route to appropriate provider
        if self.provider == "voyage":
            return self._rerank_with_voyage(query, results, top_k)
        elif self.provider == "cohere":
            # TODO: Add Cohere support
            logger.warning("Cohere reranking not yet implemented, falling back to self-hosted")

        # Self-hosted reranking
        self._ensure_model_loaded()

        # Create query-document pairs for cross-encoder
        pairs = [[query, result.get('content', '')] for result in results]

        # Score with cross-encoder
        logger.info(f"🎯 Reranking {len(results)} results with mxbai for query: {query[:50]}...")

        try:
            # Predict relevance scores
            scores = self.model.predict(pairs)

            # Combine results with scores and sort by score (descending)
            scored_results = []
            for idx, (result, score) in enumerate(zip(results, scores)):
                result_copy = result.copy()
                result_copy['rerank_score'] = float(score)
                scored_results.append(result_copy)

            # Sort by rerank score (higher is better)
            ranked_results = sorted(scored_results, key=lambda x: x['rerank_score'], reverse=True)

            # Return top_k if specified
            if top_k:
                ranked_results = ranked_results[:top_k]

            logger.info(f"✅ Reranked to top {len(ranked_results)} results")
            if ranked_results:
                logger.info(f"   Top score: {ranked_results[0]['rerank_score']:.4f}")
                logger.info(f"   Bottom score: {ranked_results[-1]['rerank_score']:.4f}")
            return ranked_results

        except Exception as e:
            logger.error(f"❌ Reranking failed: {e}")
            # Fallback: return original results without reranking
            logger.warning("⚠️ Falling back to original ranking")
            return results[:top_k] if top_k else results

    def rerank_with_metadata(
        self,
        query: str,
        results: List[Dict],
        top_k: int = None
    ) -> Tuple[List[Dict], Dict]:
        """
        Rerank and return metadata about the reranking

        Returns:
            (reranked_results, metadata)
        """
        if not results:
            return [], {"total_results": 0, "reranked": False}

        original_count = len(results)
        reranked = self.rerank(query, results, top_k)

        metadata = {
            "total_results": original_count,
            "returned_results": len(reranked),
            "reranked": True,
            "model": self.model_name,
            "score_range": {
                "max": float(reranked[0]['rerank_score']) if reranked else 0.0,
                "min": float(reranked[-1]['rerank_score']) if reranked else 0.0
            }
        }

        return reranked, metadata


# Singleton instance
_reranking_service = None


def get_reranking_service() -> RerankingService:
    """Get or create singleton reranking service"""
    global _reranking_service
    if _reranking_service is None:
        _reranking_service = RerankingService()
    return _reranking_service
