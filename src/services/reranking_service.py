"""
Reranking Service - Improve retrieval quality with Mixedbread AI

Uses Mixedbread mxbai-rerank-large-v2 (self-hosted, SOTA open-source reranker).
Outperforms Cohere Rerank 3.5 (BEIR 57.49 vs 55) with zero API costs.
Supports 100+ languages and handles up to 8K token context (32K compatible).
"""

import logging
from typing import List, Dict, Tuple
import os

logger = logging.getLogger(__name__)


class RerankingService:
    """Rerank search results using Mixedbread mxbai-rerank-large-v2 (self-hosted)"""

    def __init__(self, model_name: str = "mixedbread-ai/mxbai-rerank-large-v2"):
        """
        Initialize reranking service with self-hosted cross-encoder

        Args:
            model_name: Hugging Face model path
                - "mixedbread-ai/mxbai-rerank-large-v2" (BEIR 57.49, 1.5B params, Apache 2.0)
                - "mixedbread-ai/mxbai-rerank-base-v2" (BEIR 55.57, 0.5B params, faster)
        """
        self.model_name = model_name
        self.model = None
        logger.info(f"🎯 Initializing self-hosted reranking with {model_name}")

    def _ensure_model_loaded(self):
        """Lazy load the cross-encoder model on first use"""
        if self.model is None:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"📥 Loading {self.model_name} (first use only, ~3GB download)...")
                self.model = CrossEncoder(self.model_name, max_length=512)
                logger.info("✅ Reranking model loaded successfully")
            except ImportError:
                logger.error("❌ sentence-transformers not installed. Run: pip install sentence-transformers")
                raise
            except Exception as e:
                logger.error(f"❌ Failed to load reranking model: {e}")
                raise

    def rerank(
        self,
        query: str,
        results: List[Dict],
        top_k: int = None
    ) -> List[Dict]:
        """
        Rerank search results using self-hosted cross-encoder

        Args:
            query: User's search query
            results: List of search results (must have 'content' field)
            top_k: Number of top results to return (None = return all, ranked)

        Returns:
            Reranked results with added 'rerank_score' field
        """
        if not results:
            return []

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
