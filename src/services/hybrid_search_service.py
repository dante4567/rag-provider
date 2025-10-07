"""
Hybrid Search Service - Combines BM25 (sparse) + Dense (semantic) retrieval

Implements:
- BM25 keyword search (exact term matching)
- Dense vector search (semantic similarity)
- Score normalization and weighted fusion
- MMR (Maximal Marginal Relevance) for diversity
- Integration with cross-encoder reranking

Blueprint compliance: HIGH priority feature for 10-20% improvement
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from rank_bm25 import BM25Okapi
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


class HybridSearchService:
    """
    Hybrid retrieval combining BM25 + dense embeddings

    BM25: Excellent for exact keyword matching, proper names, technical terms
    Dense: Excellent for semantic similarity, paraphrasing, concept matching
    Hybrid: Best of both worlds!
    """

    def __init__(
        self,
        bm25_weight: float = 0.3,
        dense_weight: float = 0.7,
        mmr_lambda: float = 0.7
    ):
        """
        Initialize hybrid search service

        Args:
            bm25_weight: Weight for BM25 scores (default 0.3)
            dense_weight: Weight for dense scores (default 0.7)
            mmr_lambda: MMR diversity parameter (0=max diversity, 1=max relevance)
        """
        self.bm25_weight = bm25_weight
        self.dense_weight = dense_weight
        self.mmr_lambda = mmr_lambda

        # BM25 index storage
        self.bm25_index = None
        self.indexed_documents = []  # List of {chunk_id, content, metadata}
        self.tokenized_corpus = []   # Tokenized documents for BM25

        logger.info(f"🔀 Hybrid Search initialized (BM25: {bm25_weight}, Dense: {dense_weight}, MMR λ: {mmr_lambda})")

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text for BM25

        Simple tokenization: lowercase + split on non-alphanumeric
        BM25 works best with simple tokens
        """
        # Lowercase and split on non-alphanumeric
        tokens = re.findall(r'\w+', text.lower())
        return tokens

    def add_documents(
        self,
        doc_id: str,
        chunks: List[str],
        metadata: Dict[str, Any]
    ) -> int:
        """
        Add documents to BM25 index

        Should be called whenever documents are added to vector DB

        Args:
            doc_id: Document identifier
            chunks: List of text chunks
            metadata: Document metadata

        Returns:
            Number of chunks indexed
        """
        if not chunks:
            return 0

        start_idx = len(self.indexed_documents)

        # Add each chunk to index
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"

            # Store document data
            self.indexed_documents.append({
                "chunk_id": chunk_id,
                "content": chunk,
                "metadata": {**metadata, "chunk_index": i, "doc_id": doc_id}
            })

            # Tokenize for BM25
            tokens = self._tokenize(chunk)
            self.tokenized_corpus.append(tokens)

        # Rebuild BM25 index (fast even for 10k+ docs)
        self.bm25_index = BM25Okapi(self.tokenized_corpus)

        logger.info(f"📚 Added {len(chunks)} chunks to BM25 index (total: {len(self.indexed_documents)} chunks)")
        return len(chunks)

    def bm25_search(
        self,
        query: str,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        BM25 keyword search

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of results with BM25 scores
        """
        if not self.bm25_index or not self.indexed_documents:
            logger.warning("⚠️ BM25 index is empty")
            return []

        # Tokenize query
        query_tokens = self._tokenize(query)

        # Get BM25 scores for all documents
        scores = self.bm25_index.get_scores(query_tokens)

        # Get top K indices
        top_indices = np.argsort(scores)[::-1][:top_k]

        # Format results
        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only include non-zero scores
                doc = self.indexed_documents[idx]
                results.append({
                    "chunk_id": doc["chunk_id"],
                    "content": doc["content"],
                    "metadata": doc["metadata"],
                    "bm25_score": float(scores[idx])
                })

        logger.info(f"🔍 BM25 search for '{query[:50]}...' returned {len(results)} results")
        return results

    def normalize_scores(
        self,
        results: List[Dict[str, Any]],
        score_field: str
    ) -> List[Dict[str, Any]]:
        """
        Normalize scores to [0, 1] range using min-max normalization

        Args:
            results: List of results with scores
            score_field: Name of score field to normalize

        Returns:
            Results with normalized scores
        """
        if not results:
            return results

        scores = [r[score_field] for r in results]
        min_score = min(scores)
        max_score = max(scores)

        # Avoid division by zero
        if max_score == min_score:
            for r in results:
                r[f"{score_field}_normalized"] = 1.0
        else:
            for r in results:
                normalized = (r[score_field] - min_score) / (max_score - min_score)
                r[f"{score_field}_normalized"] = normalized

        return results

    def fuse_results(
        self,
        bm25_results: List[Dict[str, Any]],
        dense_results: List[Dict[str, Any]],
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Fuse BM25 and dense results using weighted score combination

        Args:
            bm25_results: Results from BM25 search (with bm25_score)
            dense_results: Results from dense search (with relevance_score)
            top_k: Number of results to return

        Returns:
            Fused results sorted by combined score
        """
        # Normalize BM25 scores
        bm25_results = self.normalize_scores(bm25_results, "bm25_score")

        # Dense scores are already 0-1, but normalize for consistency
        dense_results = self.normalize_scores(dense_results, "relevance_score")

        # Create lookup maps
        bm25_map = {r["chunk_id"]: r for r in bm25_results}
        dense_map = {r["chunk_id"]: r for r in dense_results}

        # Get all unique chunk IDs
        all_chunk_ids = set(bm25_map.keys()) | set(dense_map.keys())

        # Fuse scores
        fused_results = []
        for chunk_id in all_chunk_ids:
            # Get normalized scores (default to 0 if not in one retriever)
            bm25_score = bm25_map.get(chunk_id, {}).get("bm25_score_normalized", 0.0)
            dense_score = dense_map.get(chunk_id, {}).get("relevance_score_normalized", 0.0)

            # Weighted combination
            hybrid_score = (
                self.bm25_weight * bm25_score +
                self.dense_weight * dense_score
            )

            # Use document from either source (prefer dense for metadata)
            doc = dense_map.get(chunk_id) or bm25_map.get(chunk_id)

            fused_results.append({
                **doc,
                "bm25_score": bm25_score,
                "dense_score": dense_score,
                "hybrid_score": hybrid_score
            })

        # Sort by hybrid score
        fused_results.sort(key=lambda x: x["hybrid_score"], reverse=True)

        # Return top K
        fused_results = fused_results[:top_k]

        logger.info(f"🔀 Fused {len(bm25_results)} BM25 + {len(dense_results)} dense → {len(fused_results)} hybrid results")
        if fused_results:
            logger.info(f"   Top hybrid score: {fused_results[0]['hybrid_score']:.4f}")

        return fused_results

    def apply_mmr(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 10,
        lambda_param: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Apply Maximal Marginal Relevance (MMR) for diversity

        MMR = λ * relevance - (1-λ) * max_similarity_to_selected

        Args:
            query: Original search query
            results: Ranked search results
            top_k: Number of diverse results to return
            lambda_param: Diversity parameter (None = use default)

        Returns:
            Diverse subset of results
        """
        if not results or len(results) <= top_k:
            return results

        lambda_val = lambda_param if lambda_param is not None else self.mmr_lambda

        # Selected results
        selected = []
        remaining = results.copy()

        # Always pick the top result first
        selected.append(remaining.pop(0))

        # Iteratively select diverse results
        while len(selected) < top_k and remaining:
            best_score = -float('inf')
            best_idx = 0

            for i, candidate in enumerate(remaining):
                # Relevance score (use hybrid_score if available, else relevance_score)
                relevance = candidate.get("hybrid_score", candidate.get("relevance_score", 0))

                # Max similarity to already selected documents
                # Simple text similarity (could use embeddings for better quality)
                max_similarity = 0.0
                for selected_doc in selected:
                    similarity = self._text_similarity(
                        candidate["content"],
                        selected_doc["content"]
                    )
                    max_similarity = max(max_similarity, similarity)

                # MMR score
                mmr_score = lambda_val * relevance - (1 - lambda_val) * max_similarity

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            # Add best candidate
            selected.append(remaining.pop(best_idx))

        logger.info(f"🎨 MMR diversified {len(results)} results → {len(selected)} (λ={lambda_val})")
        return selected

    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Compute text similarity using token overlap (Jaccard similarity)

        Fast approximation for MMR. Could use embeddings for better quality.
        """
        tokens1 = set(self._tokenize(text1))
        tokens2 = set(self._tokenize(text2))

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0

    def hybrid_search(
        self,
        query: str,
        dense_results: List[Dict[str, Any]],
        top_k: int = 10,
        apply_mmr: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Complete hybrid search pipeline

        1. BM25 search (keyword matching)
        2. Dense search (already done, passed in)
        3. Score fusion
        4. MMR for diversity (optional)

        Args:
            query: Search query
            dense_results: Results from dense vector search
            top_k: Number of results to return
            apply_mmr: Whether to apply MMR for diversity

        Returns:
            Hybrid search results
        """
        # Get BM25 results (fetch more for better fusion)
        bm25_results = self.bm25_search(query, top_k=top_k * 3)

        # Fuse BM25 + dense
        fused_results = self.fuse_results(
            bm25_results,
            dense_results,
            top_k=top_k * 2  # Get more for MMR to choose from
        )

        # Apply MMR for diversity
        if apply_mmr and len(fused_results) > top_k:
            final_results = self.apply_mmr(query, fused_results, top_k=top_k)
        else:
            final_results = fused_results[:top_k]

        return final_results

    def get_stats(self) -> Dict[str, Any]:
        """Get BM25 index statistics"""
        return {
            "total_documents": len(self.indexed_documents),
            "total_tokens": sum(len(tokens) for tokens in self.tokenized_corpus),
            "avg_doc_length": np.mean([len(tokens) for tokens in self.tokenized_corpus]) if self.tokenized_corpus else 0,
            "bm25_weight": self.bm25_weight,
            "dense_weight": self.dense_weight,
            "mmr_lambda": self.mmr_lambda
        }

    def clear_index(self):
        """Clear BM25 index (useful for testing)"""
        self.bm25_index = None
        self.indexed_documents = []
        self.tokenized_corpus = []
        logger.info("🗑️ BM25 index cleared")


# Singleton instance
_hybrid_search_service = None


def get_hybrid_search_service(
    bm25_weight: float = 0.3,
    dense_weight: float = 0.7,
    mmr_lambda: float = 0.7
) -> HybridSearchService:
    """Get or create singleton hybrid search service"""
    global _hybrid_search_service
    if _hybrid_search_service is None:
        _hybrid_search_service = HybridSearchService(
            bm25_weight=bm25_weight,
            dense_weight=dense_weight,
            mmr_lambda=mmr_lambda
        )
    return _hybrid_search_service
