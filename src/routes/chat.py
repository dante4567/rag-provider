"""
RAG chat endpoint
"""
from fastapi import APIRouter, HTTPException, Depends
import logging
import time

from src.models.schemas import ChatRequest, ChatResponse, Query, SearchResult
from src.core.dependencies import get_rag_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_with_rag(
    request: ChatRequest,
    rag_service = Depends(get_rag_service)
):
    """Chat endpoint with RAG functionality - combines search with LLM-powered answer generation"""
    start_time = time.time()

    try:
        from src.services.reranking_service import get_reranking_service
        # Import search_documents from search routes
        from src.routes.search import search_documents

        # Step 1: Search for relevant context (retrieve more for reranking)
        # Retrieve 3x more results for reranking
        initial_results_count = request.max_context_chunks * 3
        search_query = Query(
            text=request.question,
            top_k=initial_results_count
        )

        search_response = await search_documents(search_query, rag_service)

        if not search_response.results:
            # No relevant context found
            return ChatResponse(
                question=request.question,
                answer="I don't have any relevant information in my knowledge base to answer your question. Please try rephrasing your question or ensure relevant documents have been ingested.",
                sources=[],
                llm_provider_used="none",
                total_chunks_found=0,
                response_time_ms=round((time.time() - start_time) * 1000, 2)
            )

        # Step 1.5: Rerank results for better relevance
        reranker = get_reranking_service()

        # Convert SearchResult objects to dicts for reranking
        results_for_reranking = []
        for result in search_response.results:
            results_for_reranking.append({
                'content': result.content,
                'metadata': result.metadata,
                'relevance_score': result.relevance_score,
                'chunk_id': result.chunk_id
            })

        # Rerank and take top K
        reranked_results = reranker.rerank(
            query=request.question,
            results=results_for_reranking,
            top_k=request.max_context_chunks
        )

        logger.info(f"🎯 Reranking: {len(results_for_reranking)} → {len(reranked_results)} results")

        # Step 2: Prepare context from reranked results with chunk IDs
        context_chunks = []
        for idx, result in enumerate(reranked_results, 1):
            filename = result['metadata'].get('filename', 'Unknown')
            context_chunks.append(f"[Chunk {idx}] Source: {filename}\n{result['content']}")

        context = "\n\n---\n\n".join(context_chunks)

        # Step 3: Create RAG prompt with citation requirements
        rag_prompt = f"""You are an AI assistant that answers questions based ONLY on the provided context chunks.

IMPORTANT CITATION RULES:
1. Every factual statement MUST cite its source using [Chunk N] format
2. If information is NOT in the chunks, you MUST say "I don't have enough evidence for that"
3. If chunks contradict each other, highlight the conflict and ask which source is authoritative
4. DO NOT use prior knowledge - ONLY use the provided chunks
5. If a chunk is partially relevant, cite it and explain what's missing

Context Chunks:
{context}

Question: {request.question}

Required Format:
- "The deadline is March 2026." [Chunk 3]
- "Alice agreed to the proposal." [Chunk 1]
- "I don't have enough evidence about the budget approval process."

If chunks conflict:
- "Chunk 2 states the deadline is March 2026, but Chunk 5 mentions April 2026. Which policy version applies?"

Answer:"""

        # Step 4: Generate answer using LLM
        cost = 0.0
        model_used = None

        # Generate answer using LLM service
        logger.info(f"💬 Generating chat response")
        try:
            # Determine which model to use
            model_to_use = request.llm_model.value if request.llm_model else None

            # LLMService.call_llm returns (response, cost, model_used)
            answer, cost, model_used = await rag_service.llm_service.call_llm(
                prompt=rag_prompt,
                model_id=model_to_use
            )
            provider_used = model_used.split('/')[0] if '/' in model_used else "unknown"

        except Exception as e:
            logger.error(f"LLM service failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to generate answer: {str(e)}")

        # Step 5: Prepare response - convert reranked results back to SearchResult objects
        if request.include_sources:
            sources = []
            for reranked in reranked_results:
                # Normalize rerank_score to [0, 1] range if present
                # Rerank scores from cross-encoders can be any value (-10 to +10 typical)
                if 'rerank_score' in reranked:
                    # Use sigmoid to normalize to [0, 1]: sigmoid(x) = 1 / (1 + e^(-x))
                    import math
                    raw_score = reranked['rerank_score']
                    normalized_score = 1 / (1 + math.exp(-raw_score))
                else:
                    normalized_score = reranked.get('relevance_score', 0.0)

                # Ensure score is in [0, 1] range
                normalized_score = max(0.0, min(1.0, normalized_score))

                sources.append(SearchResult(
                    content=reranked['content'],
                    metadata=reranked['metadata'],
                    relevance_score=normalized_score,
                    chunk_id=reranked['chunk_id']
                ))
        else:
            sources = []

        response_time = round((time.time() - start_time) * 1000, 2)

        return ChatResponse(
            question=request.question,
            answer=answer,
            sources=sources,
            llm_provider_used=provider_used,
            llm_model_used=model_used,
            total_chunks_found=search_response.total_results,
            response_time_ms=response_time,
            cost_usd=cost if cost > 0 else None
        )

    except Exception as e:
        logger.error(f"Chat endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")
