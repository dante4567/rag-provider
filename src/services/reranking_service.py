"""
Reranking Service - Improve retrieval quality with cross-encoder reranking

Uses cross-encoder models to rerank search results based on query-document relevance.
Much more accurate than pure vector similarity.
"""

import logging
from typing import List, Dict, Tuple
from sentence_transformers import CrossEncoder
import numpy as np

logger = logging.getLogger(__name__)


class RerankingService:
    """Rerank search results using cross-encoder models"""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"):
        """
        Initialize reranking service

        Args:
            model_name: Cross-encoder model to use
                - "cross-encoder/ms-marco-MiniLM-L-12-v2" (default, fast, good quality)
                - "cross-encoder/ms-marco-TinyBERT-L-2-v2" (faster, lower quality)
                - "cross-encoder/ms-marco-MiniLM-L-6-v2" (slower, higher quality)
        """
        self.model_name = model_name
        self.model = None
        logger.info(f"🎯 Initializing reranking service with {model_name}")

    def _ensure_model_loaded(self):
        """Lazy load the model on first use"""
        if self.model is None:
            logger.info(f"Loading reranking model: {self.model_name}")
            self.model = CrossEncoder(self.model_name)
            logger.info("✅ Reranking model loaded")

    def rerank(
        self,
        query: str,
        results: List[Dict],
        top_k: int = None
    ) -> List[Dict]:
        """
        Rerank search results based on query relevance

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

        # Prepare query-document pairs
        pairs = [[query, result.get('content', '')] for result in results]

        # Score all pairs
        logger.info(f"🎯 Reranking {len(results)} results for query: {query[:50]}...")
        scores = self.model.predict(pairs)

        # Add scores to results and sort
        for result, score in zip(results, scores):
            result['rerank_score'] = float(score)

        # Sort by rerank score (higher is better)
        ranked_results = sorted(results, key=lambda x: x['rerank_score'], reverse=True)

        # Return top K if specified
        if top_k:
            ranked_results = ranked_results[:top_k]

        logger.info(f"✅ Reranked to top {len(ranked_results)} results")
        logger.info(f"   Top score: {ranked_results[0]['rerank_score']:.4f}")
        logger.info(f"   Bottom score: {ranked_results[-1]['rerank_score']:.4f}")

        return ranked_results

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
