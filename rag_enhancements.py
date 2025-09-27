#!/usr/bin/env python3
"""
RAG Service Enhancements Integration
=====================================

Integrates enhanced retrieval capabilities into the existing RAG service.

This module adds:
1. Cross-encoder reranking
2. Hybrid retrieval (dense + BM25)
3. Controlled tag hierarchy
4. Enhanced Obsidian vault generation

Author: Enhanced RAG Team
Date: 2025-09-27
"""

import logging
import sys
import os
from pathlib import Path
from typing import List, Dict, Any
import asyncio

# Add the current directory to path for imports
sys.path.append('/home/danielt/mygit/rag-provider')

try:
    from enhanced_retrieval import (
        CrossEncoderReranker,
        BM25Retriever,
        HybridRetriever,
        ControlledTagHierarchy,
        HybridSearchResult
    )
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# Set up logging
logger = logging.getLogger(__name__)

class EnhancedRAGService:
    """Enhanced RAG Service with reranking and hybrid retrieval"""

    def __init__(self, rag_service):
        self.rag_service = rag_service
        self.hybrid_retriever = HybridRetriever()
        self.tag_hierarchy = ControlledTagHierarchy()
        self.reranker = CrossEncoderReranker()
        self._indexed = False

    async def initialize_enhanced_search(self):
        """Initialize enhanced search with existing documents"""
        try:
            # Get all existing documents from ChromaDB
            from app import collection

            all_docs = collection.get()

            if not all_docs or not all_docs['documents']:
                logger.info("No documents found for enhanced search initialization")
                return

            # Convert to format expected by hybrid retriever
            documents = []
            for i, (doc_content, metadata) in enumerate(zip(all_docs['documents'], all_docs['metadatas'])):
                doc_dict = {
                    'content': doc_content,
                    'metadata': metadata,
                    'chunk_id': all_docs['ids'][i]
                }
                documents.append(doc_dict)

            # Index documents for BM25
            self.hybrid_retriever.index_documents(documents)
            self._indexed = True

            logger.info(f"Enhanced search initialized with {len(documents)} documents")

        except Exception as e:
            logger.error(f"Failed to initialize enhanced search: {e}")

    async def enhanced_search(self, query: str, top_k: int = 5,
                            filter_dict: Dict[str, Any] = None,
                            use_hybrid: bool = True,
                            use_reranker: bool = True) -> Dict[str, Any]:
        """Enhanced search with hybrid retrieval and reranking"""

        # Ensure enhanced search is initialized
        if not self._indexed:
            await self.initialize_enhanced_search()

        # Get original dense results from the existing RAG service
        try:
            dense_response = await self.rag_service.search_documents(
                query=query,
                top_k=top_k * 2,  # Get more for better hybrid results
                filter_dict=filter_dict
            )
        except Exception as e:
            logger.error(f"Dense search failed: {e}")
            return {"error": str(e), "results": []}

        if not use_hybrid or not dense_response.results:
            # Return original results with tag enhancement
            enhanced_results = []
            for result in dense_response.results[:top_k]:
                enhanced_result = {
                    'content': result.content,
                    'metadata': result.metadata,
                    'relevance_score': result.relevance_score,
                    'chunk_id': result.chunk_id,
                    'search_type': 'dense_only'
                }
                # Add enhanced tags if available
                if 'tags' in result.metadata:
                    tags = result.metadata['tags'].split(',') if result.metadata['tags'] else []
                    enhanced_tags = self._enhance_tags(tags)
                    enhanced_result['enhanced_tags'] = enhanced_tags

                enhanced_results.append(enhanced_result)

            return {
                'query': query,
                'results': enhanced_results,
                'total_results': len(enhanced_results),
                'search_type': 'dense_only',
                'enhanced': True
            }

        # Convert dense results to format expected by hybrid retriever
        dense_results = []
        for result in dense_response.results:
            dense_results.append({
                'content': result.content,
                'metadata': result.metadata,
                'relevance_score': result.relevance_score,
                'chunk_id': result.chunk_id
            })

        # Perform hybrid search
        try:
            hybrid_results = await self.hybrid_retriever.hybrid_search(
                query=query,
                dense_results=dense_results,
                top_k=top_k,
                use_reranker=use_reranker
            )

            # Convert to enhanced response format
            enhanced_results = []
            for result in hybrid_results:
                enhanced_result = {
                    'content': result.content,
                    'metadata': result.metadata,
                    'relevance_score': result.combined_score,
                    'dense_score': result.dense_score,
                    'sparse_score': result.sparse_score,
                    'chunk_id': result.chunk_id,
                    'search_type': 'hybrid_with_reranking' if use_reranker else 'hybrid'
                }

                # Add enhanced tags
                if 'tags' in result.metadata:
                    tags = result.metadata['tags'].split(',') if result.metadata['tags'] else []
                    enhanced_tags = self._enhance_tags(tags)
                    enhanced_result['enhanced_tags'] = enhanced_tags

                enhanced_results.append(enhanced_result)

            return {
                'query': query,
                'results': enhanced_results,
                'total_results': len(enhanced_results),
                'search_type': 'hybrid_with_reranking' if use_reranker else 'hybrid',
                'enhanced': True,
                'dense_weight': self.hybrid_retriever.dense_weight,
                'sparse_weight': self.hybrid_retriever.sparse_weight
            }

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            # Fallback to dense search
            return await self.enhanced_search(query, top_k, filter_dict,
                                            use_hybrid=False, use_reranker=False)

    def _enhance_tags(self, tags: List[str]) -> Dict[str, Any]:
        """Enhance tags with hierarchy and suggestions"""
        enhanced = {
            'original_tags': tags,
            'normalized_tags': [],
            'hierarchical_tags': {},
            'suggested_tags': []
        }

        # Normalize tags
        for tag in tags:
            normalized = self.tag_hierarchy.normalize_tag(tag)
            enhanced['normalized_tags'].append(normalized)

            # Get hierarchy for each tag
            hierarchy = self.tag_hierarchy.get_tag_hierarchy(normalized)
            enhanced['hierarchical_tags'][normalized] = hierarchy

        # Get suggested related tags
        enhanced['suggested_tags'] = self.tag_hierarchy.suggest_related_tags(tags)

        return enhanced

    async def enhanced_chat(self, question: str, max_context_chunks: int = 5,
                          use_hybrid: bool = True, use_reranker: bool = True) -> Dict[str, Any]:
        """Enhanced RAG chat with improved retrieval"""

        # Use enhanced search for context retrieval
        search_response = await self.enhanced_search(
            query=question,
            top_k=max_context_chunks,
            use_hybrid=use_hybrid,
            use_reranker=use_reranker
        )

        if not search_response.get('results'):
            return {
                'question': question,
                'answer': "I don't have relevant information to answer your question.",
                'sources': [],
                'search_type': 'no_results',
                'enhanced': True
            }

        # Prepare context from enhanced results
        context_chunks = []
        sources = []

        for result in search_response['results']:
            # Create context with enhanced metadata
            source_info = result['metadata'].get('filename', 'Unknown')
            context_chunks.append(f"Source: {source_info}\nContent: {result['content']}")

            # Add enhanced source information
            source = {
                'content': result['content'],
                'metadata': result['metadata'],
                'relevance_score': result['relevance_score'],
                'chunk_id': result['chunk_id'],
                'search_type': result['search_type']
            }

            if 'dense_score' in result:
                source['dense_score'] = result['dense_score']
                source['sparse_score'] = result['sparse_score']

            if 'enhanced_tags' in result:
                source['enhanced_tags'] = result['enhanced_tags']

            sources.append(source)

        context = "\n\n---\n\n".join(context_chunks)

        # Create enhanced RAG prompt
        rag_prompt = f"""You are an AI assistant that answers questions based on provided context. Use only the information from the context to answer the question. If the context doesn't contain enough information, say so clearly.

Context:
{context}

Question: {question}

Instructions:
- Answer based solely on the provided context
- Be accurate and specific
- If the context is insufficient, clearly state that
- Cite relevant parts of the context when possible
- Keep your answer concise but complete

Answer:"""

        # Generate answer using the existing LLM service
        try:
            answer = await self.rag_service.llm_service.call_llm(rag_prompt)

            return {
                'question': question,
                'answer': answer,
                'sources': sources,
                'search_type': search_response['search_type'],
                'total_chunks_found': search_response['total_results'],
                'enhanced': True,
                'context_quality': self._assess_context_quality(context_chunks)
            }

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return {
                'question': question,
                'answer': f"I found relevant information but couldn't generate a response: {str(e)}",
                'sources': sources,
                'search_type': search_response['search_type'],
                'enhanced': True,
                'error': str(e)
            }

    def _assess_context_quality(self, context_chunks: List[str]) -> Dict[str, Any]:
        """Assess the quality of retrieved context"""
        total_length = sum(len(chunk) for chunk in context_chunks)
        avg_length = total_length / len(context_chunks) if context_chunks else 0

        # Simple quality metrics
        quality = {
            'total_context_length': total_length,
            'average_chunk_length': avg_length,
            'num_chunks': len(context_chunks),
            'coverage_score': min(1.0, total_length / 2000)  # Rough coverage score
        }

        return quality

# Integration functions for FastAPI endpoints
def create_enhanced_endpoints(app, rag_service):
    """Add enhanced endpoints to the FastAPI app"""

    enhanced_rag = EnhancedRAGService(rag_service)

    @app.post("/search/enhanced")
    async def enhanced_search_endpoint(request: dict):
        """Enhanced search endpoint with hybrid retrieval and reranking"""
        query = request.get('text', '')
        top_k = request.get('top_k', 5)
        use_hybrid = request.get('use_hybrid', True)
        use_reranker = request.get('use_reranker', True)
        filter_dict = request.get('filter')

        if not query or not query.strip():
            return {"error": "Search query cannot be empty"}

        try:
            result = await enhanced_rag.enhanced_search(
                query=query,
                top_k=top_k,
                filter_dict=filter_dict,
                use_hybrid=use_hybrid,
                use_reranker=use_reranker
            )
            return result
        except Exception as e:
            logger.error(f"Enhanced search failed: {e}")
            return {"error": str(e)}

    @app.post("/chat/enhanced")
    async def enhanced_chat_endpoint(request: dict):
        """Enhanced RAG chat endpoint"""
        question = request.get('question', '')
        max_context_chunks = request.get('max_context_chunks', 5)
        use_hybrid = request.get('use_hybrid', True)
        use_reranker = request.get('use_reranker', True)

        if not question or not question.strip():
            return {"error": "Question cannot be empty"}

        try:
            result = await enhanced_rag.enhanced_chat(
                question=question,
                max_context_chunks=max_context_chunks,
                use_hybrid=use_hybrid,
                use_reranker=use_reranker
            )
            return result
        except Exception as e:
            logger.error(f"Enhanced chat failed: {e}")
            return {"error": str(e)}

    @app.get("/search/config")
    async def get_search_config():
        """Get current search configuration"""
        return {
            'hybrid_retrieval': {
                'dense_weight': enhanced_rag.hybrid_retriever.dense_weight,
                'sparse_weight': enhanced_rag.hybrid_retriever.sparse_weight,
                'indexed': enhanced_rag._indexed
            },
            'reranker': {
                'model': enhanced_rag.reranker.model_name,
                'available': enhanced_rag.reranker.model is not None
            },
            'tag_hierarchy': {
                'categories': list(enhanced_rag.tag_hierarchy.tag_hierarchy.keys()),
                'vocab_size': len(enhanced_rag.tag_hierarchy.controlled_vocab)
            }
        }

    @app.post("/admin/initialize-enhanced-search")
    async def initialize_enhanced_search():
        """Initialize enhanced search with current documents"""
        try:
            await enhanced_rag.initialize_enhanced_search()
            return {
                "success": True,
                "message": "Enhanced search initialized successfully",
                "indexed": enhanced_rag._indexed
            }
        except Exception as e:
            logger.error(f"Enhanced search initialization failed: {e}")
            return {"error": str(e)}

    return enhanced_rag

# Utility function to test enhanced features
async def test_enhanced_features():
    """Test the enhanced RAG features"""
    print("🧪 Testing Enhanced RAG Features")
    print("================================")

    # This would be called with an actual RAG service instance
    # For testing, we'll create a mock
    class MockRAGService:
        def __init__(self):
            self.llm_service = None

        async def search_documents(self, query, top_k, filter_dict=None):
            # Mock response
            from collections import namedtuple
            SearchResult = namedtuple('SearchResult', ['content', 'metadata', 'relevance_score', 'chunk_id'])
            SearchResponse = namedtuple('SearchResponse', ['results', 'total_results'])

            results = [
                SearchResult(
                    content="Machine learning is a subset of artificial intelligence.",
                    metadata={'filename': 'ml_intro.txt', 'tags': 'machine_learning,ai'},
                    relevance_score=0.8,
                    chunk_id='chunk_1'
                )
            ]
            return SearchResponse(results=results, total_results=1)

    # Test tag hierarchy
    tag_system = ControlledTagHierarchy()
    test_tags = ["BERT", "attention mechanism", "machine learning"]

    print("🏷️  Tag Enhancement:")
    for tag in test_tags:
        normalized = tag_system.normalize_tag(tag)
        hierarchy = tag_system.get_tag_hierarchy(normalized)
        print(f"  '{tag}' -> '{normalized}' -> {hierarchy}")

    suggested = tag_system.suggest_related_tags(test_tags)
    print(f"  Suggested related: {suggested}")

    print("\n✅ Enhanced RAG features loaded successfully!")

if __name__ == "__main__":
    asyncio.run(test_enhanced_features())