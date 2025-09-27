#!/usr/bin/env python3
"""
Enhanced Retrieval System for RAG Service
==========================================

Adds reranker and hybrid retrieval capabilities to the RAG service.

Features:
- Cross-encoder reranking
- Hybrid retrieval (dense + sparse/BM25)
- Controlled tag hierarchy
- Advanced search strategies

Author: Enhanced RAG Team
Date: 2025-09-27
"""

import logging
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import re
import math
from collections import defaultdict, Counter
import asyncio
import json

# Set up logging
logger = logging.getLogger(__name__)

@dataclass
class RerankedResult:
    """Result with reranking score"""
    content: str
    metadata: Dict[str, Any]
    original_score: float
    rerank_score: float
    final_score: float
    chunk_id: str

@dataclass
class HybridSearchResult:
    """Result from hybrid search"""
    content: str
    metadata: Dict[str, Any]
    dense_score: float
    sparse_score: float
    combined_score: float
    chunk_id: str

class CrossEncoderReranker:
    """Cross-encoder reranker for improving relevance"""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self.model = None
        self._initialize_model()

    def _initialize_model(self):
        """Initialize the cross-encoder model"""
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(self.model_name)
            logger.info(f"Initialized cross-encoder: {self.model_name}")
        except ImportError:
            logger.warning("sentence-transformers not available, using fallback reranker")
            self.model = None

    def rerank(self, query: str, documents: List[Dict], top_k: int = None) -> List[RerankedResult]:
        """Rerank documents using cross-encoder"""
        if not documents:
            return []

        if self.model is None:
            # Fallback to simple keyword-based scoring
            return self._fallback_rerank(query, documents, top_k)

        try:
            # Prepare query-document pairs for cross-encoder
            query_doc_pairs = [(query, doc['content']) for doc in documents]

            # Get reranking scores
            rerank_scores = self.model.predict(query_doc_pairs)

            # Create reranked results
            reranked_results = []
            for i, (doc, rerank_score) in enumerate(zip(documents, rerank_scores)):
                result = RerankedResult(
                    content=doc['content'],
                    metadata=doc['metadata'],
                    original_score=doc.get('relevance_score', 0.0),
                    rerank_score=float(rerank_score),
                    final_score=float(rerank_score),
                    chunk_id=doc.get('chunk_id', f'chunk_{i}')
                )
                reranked_results.append(result)

            # Sort by rerank score
            reranked_results.sort(key=lambda x: x.rerank_score, reverse=True)

            if top_k:
                reranked_results = reranked_results[:top_k]

            logger.info(f"Reranked {len(documents)} documents, returning top {len(reranked_results)}")
            return reranked_results

        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return self._fallback_rerank(query, documents, top_k)

    def _fallback_rerank(self, query: str, documents: List[Dict], top_k: int = None) -> List[RerankedResult]:
        """Fallback keyword-based reranking"""
        query_terms = set(query.lower().split())

        reranked_results = []
        for i, doc in enumerate(documents):
            content_terms = set(doc['content'].lower().split())

            # Simple keyword overlap score
            overlap = len(query_terms.intersection(content_terms))
            total_terms = len(query_terms.union(content_terms))

            # Jaccard similarity
            keyword_score = overlap / total_terms if total_terms > 0 else 0.0

            # Boost score with TF-IDF-like weighting
            content_lower = doc['content'].lower()
            tf_score = sum(content_lower.count(term) for term in query_terms)
            tf_score = tf_score / len(content_terms) if content_terms else 0

            final_score = (keyword_score * 0.7) + (tf_score * 0.3)

            result = RerankedResult(
                content=doc['content'],
                metadata=doc['metadata'],
                original_score=doc.get('relevance_score', 0.0),
                rerank_score=final_score,
                final_score=final_score,
                chunk_id=doc.get('chunk_id', f'chunk_{i}')
            )
            reranked_results.append(result)

        # Sort by final score
        reranked_results.sort(key=lambda x: x.final_score, reverse=True)

        if top_k:
            reranked_results = reranked_results[:top_k]

        logger.info(f"Fallback reranked {len(documents)} documents")
        return reranked_results

class BM25Retriever:
    """BM25 sparse retrieval implementation"""

    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_freqs = defaultdict(int)
        self.idf = {}
        self.doc_len = []
        self.documents = []
        self.avg_doc_len = 0
        self.corpus_size = 0

    def index_documents(self, documents: List[Dict]):
        """Index documents for BM25 retrieval"""
        self.documents = documents
        self.corpus_size = len(documents)

        # Calculate document frequencies
        for doc in documents:
            content = doc.get('content', '')
            tokens = self._tokenize(content)
            doc_len = len(tokens)
            self.doc_len.append(doc_len)

            # Count unique terms in this document
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freqs[token] += 1

        # Calculate average document length
        self.avg_doc_len = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0

        # Calculate IDF scores
        for term, doc_freq in self.doc_freqs.items():
            self.idf[term] = math.log((self.corpus_size - doc_freq + 0.5) / (doc_freq + 0.5))

        logger.info(f"Indexed {self.corpus_size} documents for BM25 retrieval")

    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """Search using BM25 scoring"""
        if not self.documents:
            return []

        query_tokens = self._tokenize(query)
        scores = []

        for i, doc in enumerate(self.documents):
            content = doc.get('content', '')
            doc_tokens = self._tokenize(content)
            score = self._bm25_score(query_tokens, doc_tokens, i)

            scores.append({
                'content': content,
                'metadata': doc.get('metadata', {}),
                'sparse_score': score,
                'chunk_id': doc.get('chunk_id', f'chunk_{i}'),
                'doc_index': i
            })

        # Sort by BM25 score
        scores.sort(key=lambda x: x['sparse_score'], reverse=True)

        return scores[:top_k]

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization"""
        # Convert to lowercase and split on non-alphanumeric characters
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens

    def _bm25_score(self, query_tokens: List[str], doc_tokens: List[str], doc_index: int) -> float:
        """Calculate BM25 score for a document"""
        score = 0.0
        doc_len = self.doc_len[doc_index]
        doc_token_counts = Counter(doc_tokens)

        for token in query_tokens:
            if token in doc_token_counts:
                tf = doc_token_counts[token]
                idf = self.idf.get(token, 0)

                # BM25 formula
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / self.avg_doc_len))

                score += idf * (numerator / denominator)

        return score

class HybridRetriever:
    """Combines dense and sparse retrieval methods"""

    def __init__(self, dense_weight: float = 0.7, sparse_weight: float = 0.3):
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.bm25_retriever = BM25Retriever()
        self.reranker = CrossEncoderReranker()

    def index_documents(self, documents: List[Dict]):
        """Index documents for hybrid retrieval"""
        self.bm25_retriever.index_documents(documents)
        logger.info("Documents indexed for hybrid retrieval")

    async def hybrid_search(self, query: str, dense_results: List[Dict],
                           top_k: int = 10, use_reranker: bool = True) -> List[HybridSearchResult]:
        """Perform hybrid search combining dense and sparse results"""

        # Get sparse (BM25) results
        sparse_results = self.bm25_retriever.search(query, top_k * 2)

        # Create lookup for sparse scores
        sparse_scores = {}
        for result in sparse_results:
            chunk_id = result['chunk_id']
            sparse_scores[chunk_id] = result['sparse_score']

        # Normalize scores to [0, 1] range
        dense_scores = [r.get('relevance_score', 0.0) for r in dense_results]
        sparse_score_values = list(sparse_scores.values())

        # Avoid division by zero
        max_dense = max(dense_scores) if dense_scores else 1.0
        max_sparse = max(sparse_score_values) if sparse_score_values else 1.0

        if max_dense == 0:
            max_dense = 1.0
        if max_sparse == 0:
            max_sparse = 1.0

        # Combine scores
        hybrid_results = []
        seen_chunks = set()

        # Process dense results
        for result in dense_results:
            chunk_id = result.get('chunk_id', '')
            if chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk_id)

            dense_score = result.get('relevance_score', 0.0) / max_dense
            sparse_score = sparse_scores.get(chunk_id, 0.0) / max_sparse

            combined_score = (self.dense_weight * dense_score +
                            self.sparse_weight * sparse_score)

            hybrid_result = HybridSearchResult(
                content=result.get('content', ''),
                metadata=result.get('metadata', {}),
                dense_score=dense_score,
                sparse_score=sparse_score,
                combined_score=combined_score,
                chunk_id=chunk_id
            )
            hybrid_results.append(hybrid_result)

        # Add sparse-only results not in dense results
        for result in sparse_results:
            chunk_id = result['chunk_id']
            if chunk_id not in seen_chunks:
                seen_chunks.add(chunk_id)

                sparse_score = result['sparse_score'] / max_sparse
                combined_score = self.sparse_weight * sparse_score

                hybrid_result = HybridSearchResult(
                    content=result['content'],
                    metadata=result['metadata'],
                    dense_score=0.0,
                    sparse_score=sparse_score,
                    combined_score=combined_score,
                    chunk_id=chunk_id
                )
                hybrid_results.append(hybrid_result)

        # Sort by combined score
        hybrid_results.sort(key=lambda x: x.combined_score, reverse=True)
        hybrid_results = hybrid_results[:top_k * 2]  # Get more for reranking

        # Apply reranking if requested
        if use_reranker and hybrid_results:
            # Convert to format expected by reranker
            rerank_input = []
            for result in hybrid_results:
                rerank_input.append({
                    'content': result.content,
                    'metadata': result.metadata,
                    'relevance_score': result.combined_score,
                    'chunk_id': result.chunk_id
                })

            reranked = self.reranker.rerank(query, rerank_input, top_k)

            # Convert back to HybridSearchResult
            final_results = []
            for rerank_result in reranked:
                # Find original hybrid result
                original = next((r for r in hybrid_results
                               if r.chunk_id == rerank_result.chunk_id), None)
                if original:
                    # Update with reranked score
                    final_result = HybridSearchResult(
                        content=rerank_result.content,
                        metadata=rerank_result.metadata,
                        dense_score=original.dense_score,
                        sparse_score=original.sparse_score,
                        combined_score=rerank_result.final_score,
                        chunk_id=rerank_result.chunk_id
                    )
                    final_results.append(final_result)

            logger.info(f"Hybrid search with reranking returned {len(final_results)} results")
            return final_results

        logger.info(f"Hybrid search returned {len(hybrid_results[:top_k])} results")
        return hybrid_results[:top_k]

class ControlledTagHierarchy:
    """Manages controlled vocabulary and tag hierarchy"""

    def __init__(self):
        self.tag_hierarchy = self._build_default_hierarchy()
        self.controlled_vocab = self._build_controlled_vocabulary()

    def _build_default_hierarchy(self) -> Dict[str, List[str]]:
        """Build default tag hierarchy for AI/ML content"""
        return {
            # Top-level categories
            "AI": ["machine_learning", "deep_learning", "natural_language_processing",
                   "computer_vision", "robotics", "knowledge_representation"],

            "machine_learning": ["supervised_learning", "unsupervised_learning",
                               "reinforcement_learning", "feature_engineering", "model_evaluation"],

            "deep_learning": ["neural_networks", "transformers", "convolutional_networks",
                            "recurrent_networks", "attention_mechanisms", "optimization"],

            "transformers": ["bert", "gpt", "t5", "attention", "positional_encoding"],

            "natural_language_processing": ["text_classification", "named_entity_recognition",
                                          "sentiment_analysis", "language_modeling", "tokenization"],

            "computer_vision": ["image_classification", "object_detection", "segmentation",
                              "ocr", "face_recognition"],

            # Technical concepts
            "algorithms": ["optimization", "search", "sorting", "graph_algorithms"],

            "data_structures": ["arrays", "trees", "graphs", "hash_tables"],

            # Research areas
            "research": ["papers", "experiments", "datasets", "benchmarks", "evaluation"],

            # Applications
            "applications": ["chatbots", "recommendation_systems", "autonomous_vehicles",
                           "medical_ai", "finance"]
        }

    def _build_controlled_vocabulary(self) -> Dict[str, List[str]]:
        """Build controlled vocabulary with synonyms"""
        return {
            # Model names and variations
            "bert": ["bert", "bidirectional encoder representations", "bert-base", "bert-large"],
            "gpt": ["gpt", "generative pre-trained transformer", "gpt-3", "gpt-4", "chatgpt"],
            "transformer": ["transformer", "attention is all you need", "self-attention"],

            # Techniques
            "attention": ["attention", "self-attention", "multi-head attention", "cross-attention"],
            "fine_tuning": ["fine-tuning", "fine tuning", "transfer learning", "adaptation"],
            "embedding": ["embedding", "vector representation", "dense representation"],

            # Concepts
            "neural_network": ["neural network", "artificial neural network", "deep network"],
            "machine_learning": ["machine learning", "ml", "artificial intelligence", "ai"],

            # Data types
            "text": ["text", "natural language", "corpus", "document"],
            "image": ["image", "picture", "visual", "computer vision"],
            "multimodal": ["multimodal", "multi-modal", "vision-language", "cross-modal"]
        }

    def normalize_tag(self, tag: str) -> str:
        """Normalize a tag using controlled vocabulary"""
        tag_lower = tag.lower().strip()

        # Check if tag matches any controlled vocabulary
        for canonical, variants in self.controlled_vocab.items():
            if tag_lower in [v.lower() for v in variants]:
                return canonical

        # Return cleaned version if not in vocabulary
        return re.sub(r'[^a-zA-Z0-9_]', '_', tag_lower)

    def get_tag_hierarchy(self, tag: str) -> List[str]:
        """Get hierarchical path for a tag"""
        normalized_tag = self.normalize_tag(tag)

        # Find parent categories
        hierarchy_path = []
        for parent, children in self.tag_hierarchy.items():
            if normalized_tag in children:
                parent_hierarchy = self.get_tag_hierarchy(parent)
                hierarchy_path = parent_hierarchy + [parent] + [normalized_tag]
                break

        if not hierarchy_path:
            hierarchy_path = [normalized_tag]

        return hierarchy_path

    def suggest_related_tags(self, tags: List[str]) -> List[str]:
        """Suggest related tags based on hierarchy"""
        suggested = set()

        for tag in tags:
            normalized = self.normalize_tag(tag)

            # Add parent tags
            hierarchy = self.get_tag_hierarchy(normalized)
            suggested.update(hierarchy[:-1])  # Exclude the tag itself

            # Add sibling tags
            for parent, children in self.tag_hierarchy.items():
                if normalized in children:
                    suggested.update(children[:3])  # Add up to 3 siblings

        # Remove original tags
        original_normalized = {self.normalize_tag(tag) for tag in tags}
        suggested = suggested - original_normalized

        return list(suggested)[:5]  # Return top 5 suggestions

# Integration functions for the main RAG service
def enhance_search_with_hybrid_retrieval(original_search_func):
    """Decorator to enhance search with hybrid retrieval"""
    hybrid_retriever = HybridRetriever()
    tag_hierarchy = ControlledTagHierarchy()

    async def enhanced_search(query: str, top_k: int = 5, filter_dict: Dict[str, Any] = None,
                            use_hybrid: bool = True, use_reranker: bool = True):
        """Enhanced search with hybrid retrieval and reranking"""

        # Get original dense results
        dense_response = await original_search_func(query, top_k * 2, filter_dict)

        if not use_hybrid:
            return dense_response

        # Convert to format expected by hybrid retriever
        dense_results = []
        for result in dense_response.results:
            dense_results.append({
                'content': result.content,
                'metadata': result.metadata,
                'relevance_score': result.relevance_score,
                'chunk_id': result.chunk_id
            })

        # Index documents for BM25 if not already done
        if not hybrid_retriever.bm25_retriever.documents:
            # This would need to be called once with all documents
            # For now, we'll work with the current results
            hybrid_retriever.bm25_retriever.index_documents(dense_results)

        # Perform hybrid search
        hybrid_results = await hybrid_retriever.hybrid_search(
            query, dense_results, top_k, use_reranker
        )

        # Convert back to SearchResult format
        from app import SearchResult, SearchResponse
        import time

        search_results = []
        for result in hybrid_results:
            search_result = SearchResult(
                content=result.content,
                metadata=result.metadata,
                relevance_score=result.combined_score,
                chunk_id=result.chunk_id
            )
            search_results.append(search_result)

        return SearchResponse(
            query=query,
            results=search_results,
            total_results=len(search_results),
            search_time_ms=0  # Would need to track actual time
        )

    return enhanced_search

# Example usage and testing
if __name__ == "__main__":
    # Test reranker
    reranker = CrossEncoderReranker()

    test_docs = [
        {
            'content': 'Machine learning is a subset of artificial intelligence.',
            'metadata': {'title': 'ML Overview'},
            'relevance_score': 0.8,
            'chunk_id': 'chunk_1'
        },
        {
            'content': 'Deep learning uses neural networks with multiple layers.',
            'metadata': {'title': 'Deep Learning'},
            'relevance_score': 0.7,
            'chunk_id': 'chunk_2'
        }
    ]

    query = "What is deep learning?"
    reranked = reranker.rerank(query, test_docs)

    print("Reranking Results:")
    for result in reranked:
        print(f"Score: {result.final_score:.3f} - {result.content[:50]}...")

    # Test tag hierarchy
    tag_system = ControlledTagHierarchy()

    test_tags = ["BERT", "attention mechanism", "machine learning"]
    print(f"\nTag normalization:")
    for tag in test_tags:
        normalized = tag_system.normalize_tag(tag)
        hierarchy = tag_system.get_tag_hierarchy(normalized)
        print(f"'{tag}' -> '{normalized}' -> {hierarchy}")

    print(f"\nSuggested related tags: {tag_system.suggest_related_tags(test_tags)}")