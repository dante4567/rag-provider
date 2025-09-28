#!/usr/bin/env python3
"""
Advanced Reranking Service with Cross-Encoders and Hybrid Approaches

This module provides sophisticated reranking capabilities using sentence-transformers
cross-encoders combined with LLM-based reranking for optimal retrieval quality.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import numpy as np

try:
    from sentence_transformers import CrossEncoder
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    CrossEncoder = None

from enhanced_llm_service import EnhancedLLMService

logger = logging.getLogger(__name__)

@dataclass
class RerankResult:
    """Result of a reranking operation"""
    document_id: str
    content: str
    original_score: float
    rerank_score: float
    final_score: float
    metadata: Dict[str, Any]

class AdvancedReranker:
    """
    Advanced reranking service with multiple strategies:
    1. Cross-encoder reranking (fast, accurate)
    2. LLM-based reranking (high quality, slower)
    3. Hybrid approach (best of both)
    """

    def __init__(self, llm_service: Optional[EnhancedLLMService] = None):
        self.llm_service = llm_service or EnhancedLLMService()
        self.cross_encoder = None
        self.model_loaded = False

        # Reranking models by speed/quality trade-off
        self.available_models = {
            "fast": "cross-encoder/ms-marco-TinyBERT-L-2-v2",          # Very fast
            "balanced": "cross-encoder/ms-marco-MiniLM-L-12-v2",       # Good balance
            "accurate": "cross-encoder/ms-marco-electra-base",         # Higher accuracy
        }

        self.stats = {
            "total_reranks": 0,
            "cross_encoder_time": 0,
            "llm_rerank_time": 0,
            "hybrid_time": 0
        }

    async def initialize(self, model_type: str = "balanced"):
        """Initialize the cross-encoder model"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("Sentence-transformers not available - LLM-only reranking")
            return False

        try:
            model_name = self.available_models.get(model_type, self.available_models["balanced"])
            logger.info(f"Loading cross-encoder model: {model_name}")

            self.cross_encoder = CrossEncoder(model_name)
            self.model_loaded = True
            logger.info(f"Cross-encoder model loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load cross-encoder: {e}")
            return False

    async def rerank_cross_encoder(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[RerankResult]:
        """
        Rerank documents using cross-encoder models (fast, accurate)
        """
        if not self.model_loaded:
            await self.initialize()

        if not self.model_loaded:
            logger.warning("Cross-encoder not available, falling back to original scores")
            return self._create_results_from_original(documents, top_k)

        start_time = time.time()

        try:
            # Prepare query-document pairs for cross-encoder
            pairs = []
            for doc in documents:
                content = doc.get('content', '')[:512]  # Limit length for speed
                pairs.append([query, content])

            # Get cross-encoder scores
            scores = self.cross_encoder.predict(pairs)

            # Create rerank results
            results = []
            for i, (doc, score) in enumerate(zip(documents, scores)):
                result = RerankResult(
                    document_id=doc.get('id', f'doc_{i}'),
                    content=doc.get('content', ''),
                    original_score=doc.get('score', 0.0),
                    rerank_score=float(score),
                    final_score=float(score),
                    metadata=doc.get('metadata', {})
                )
                results.append(result)

            # Sort by rerank score
            results.sort(key=lambda x: x.rerank_score, reverse=True)

            # Limit results if requested
            if top_k:
                results = results[:top_k]

            elapsed = time.time() - start_time
            self.stats["cross_encoder_time"] += elapsed
            self.stats["total_reranks"] += 1

            logger.info(f"Cross-encoder reranking: {len(results)} docs in {elapsed:.3f}s")
            return results

        except Exception as e:
            logger.error(f"Cross-encoder reranking failed: {e}")
            return self._create_results_from_original(documents, top_k)

    async def rerank_llm(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None,
        model: str = "groq/llama-3.1-8b-instant"
    ) -> List[RerankResult]:
        """
        Rerank documents using LLM (high quality, slower)
        """
        start_time = time.time()

        try:
            # Limit to reasonable number for LLM processing
            limited_docs = documents[:10] if len(documents) > 10 else documents

            # Prepare documents for LLM
            doc_list = []
            for i, doc in enumerate(limited_docs):
                content = doc.get('content', '')[:300]  # Limit for context
                doc_list.append(f"{i+1}. {content}")

            prompt = f"""
Rank these documents by relevance to the query: "{query}"

Documents:
{chr(10).join(doc_list)}

Return ONLY a comma-separated list of numbers in order of relevance (most relevant first).
Example: 3,1,5,2,4

Ranking:"""

            response = await self.llm_service.call_llm(prompt, model=model, max_tokens=100)

            # Parse ranking
            try:
                ranking_str = response.strip().split('\n')[0]  # Take first line
                ranking = [int(x.strip()) - 1 for x in ranking_str.split(',') if x.strip().isdigit()]
            except:
                # Fallback to original order if parsing fails
                ranking = list(range(len(limited_docs)))

            # Create reranked results
            results = []
            for rank_pos, doc_idx in enumerate(ranking):
                if doc_idx < len(limited_docs):
                    doc = limited_docs[doc_idx]
                    rerank_score = 1.0 - (rank_pos / len(ranking))  # Higher score for better rank

                    result = RerankResult(
                        document_id=doc.get('id', f'doc_{doc_idx}'),
                        content=doc.get('content', ''),
                        original_score=doc.get('score', 0.0),
                        rerank_score=rerank_score,
                        final_score=rerank_score,
                        metadata=doc.get('metadata', {})
                    )
                    results.append(result)

            # Add remaining documents if ranking was incomplete
            ranked_indices = set(ranking)
            for i, doc in enumerate(limited_docs):
                if i not in ranked_indices:
                    result = RerankResult(
                        document_id=doc.get('id', f'doc_{i}'),
                        content=doc.get('content', ''),
                        original_score=doc.get('score', 0.0),
                        rerank_score=0.1,  # Low score for unranked
                        final_score=0.1,
                        metadata=doc.get('metadata', {})
                    )
                    results.append(result)

            if top_k:
                results = results[:top_k]

            elapsed = time.time() - start_time
            self.stats["llm_rerank_time"] += elapsed

            logger.info(f"LLM reranking: {len(results)} docs in {elapsed:.3f}s")
            return results

        except Exception as e:
            logger.error(f"LLM reranking failed: {e}")
            return self._create_results_from_original(documents, top_k)

    async def rerank_hybrid(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        cross_encoder_k: int = 10
    ) -> List[RerankResult]:
        """
        Hybrid reranking: Cross-encoder for initial filtering + LLM for final ranking

        This provides the best of both worlds:
        - Cross-encoder quickly filters top candidates
        - LLM provides nuanced final ranking
        """
        start_time = time.time()

        try:
            # Stage 1: Cross-encoder filtering (fast)
            if len(documents) > cross_encoder_k:
                logger.info(f"Stage 1: Cross-encoder filtering {len(documents)} → {cross_encoder_k}")
                stage1_results = await self.rerank_cross_encoder(query, documents, cross_encoder_k)
                stage1_docs = [
                    {
                        'id': r.document_id,
                        'content': r.content,
                        'score': r.rerank_score,
                        'metadata': r.metadata
                    }
                    for r in stage1_results
                ]
            else:
                stage1_docs = documents

            # Stage 2: LLM final ranking (high quality)
            if len(stage1_docs) > top_k:
                logger.info(f"Stage 2: LLM final ranking {len(stage1_docs)} → {top_k}")
                final_results = await self.rerank_llm(query, stage1_docs, top_k)
            else:
                final_results = await self.rerank_llm(query, stage1_docs, top_k)

            # Update final scores to reflect hybrid approach
            for result in final_results:
                result.final_score = (result.original_score * 0.2 + result.rerank_score * 0.8)

            elapsed = time.time() - start_time
            self.stats["hybrid_time"] += elapsed

            logger.info(f"Hybrid reranking: {len(final_results)} docs in {elapsed:.3f}s")
            return final_results

        except Exception as e:
            logger.error(f"Hybrid reranking failed: {e}")
            return self._create_results_from_original(documents, top_k)

    def _create_results_from_original(self, documents: List[Dict[str, Any]], top_k: Optional[int] = None) -> List[RerankResult]:
        """Create rerank results using original scores (fallback)"""
        results = []
        for i, doc in enumerate(documents):
            result = RerankResult(
                document_id=doc.get('id', f'doc_{i}'),
                content=doc.get('content', ''),
                original_score=doc.get('score', 0.0),
                rerank_score=doc.get('score', 0.0),
                final_score=doc.get('score', 0.0),
                metadata=doc.get('metadata', {})
            )
            results.append(result)

        results.sort(key=lambda x: x.original_score, reverse=True)

        if top_k:
            results = results[:top_k]

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get reranking performance statistics"""
        return {
            "model_loaded": self.model_loaded,
            "sentence_transformers_available": SENTENCE_TRANSFORMERS_AVAILABLE,
            "available_models": list(self.available_models.keys()),
            "stats": self.stats.copy()
        }

    async def benchmark_reranking_methods(
        self,
        query: str,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Benchmark all reranking methods for comparison
        """
        logger.info(f"Benchmarking reranking methods with {len(documents)} documents")

        results = {}

        # Test cross-encoder
        if self.model_loaded:
            start = time.time()
            cross_results = await self.rerank_cross_encoder(query, documents, 5)
            cross_time = time.time() - start
            results["cross_encoder"] = {
                "time": cross_time,
                "results": len(cross_results),
                "top_score": cross_results[0].rerank_score if cross_results else 0
            }

        # Test LLM reranking
        start = time.time()
        llm_results = await self.rerank_llm(query, documents, 5)
        llm_time = time.time() - start
        results["llm"] = {
            "time": llm_time,
            "results": len(llm_results),
            "top_score": llm_results[0].rerank_score if llm_results else 0
        }

        # Test hybrid
        start = time.time()
        hybrid_results = await self.rerank_hybrid(query, documents, 5)
        hybrid_time = time.time() - start
        results["hybrid"] = {
            "time": hybrid_time,
            "results": len(hybrid_results),
            "top_score": hybrid_results[0].final_score if hybrid_results else 0
        }

        return results

# Example usage
async def main():
    """Example usage of the advanced reranker"""
    reranker = AdvancedReranker()
    await reranker.initialize("balanced")

    # Example documents
    query = "machine learning applications"
    documents = [
        {"id": "1", "content": "Deep learning is a subset of machine learning...", "score": 0.8},
        {"id": "2", "content": "Weather prediction using statistical models...", "score": 0.6},
        {"id": "3", "content": "Neural networks for image recognition tasks...", "score": 0.9},
    ]

    # Test different reranking methods
    print("Cross-encoder reranking:")
    cross_results = await reranker.rerank_cross_encoder(query, documents)
    for r in cross_results:
        print(f"  {r.document_id}: {r.rerank_score:.3f}")

    print("\nLLM reranking:")
    llm_results = await reranker.rerank_llm(query, documents)
    for r in llm_results:
        print(f"  {r.document_id}: {r.rerank_score:.3f}")

    print("\nHybrid reranking:")
    hybrid_results = await reranker.rerank_hybrid(query, documents)
    for r in hybrid_results:
        print(f"  {r.document_id}: {r.final_score:.3f}")

if __name__ == "__main__":
    asyncio.run(main())