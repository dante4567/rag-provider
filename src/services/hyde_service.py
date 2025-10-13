"""
HyDE Service - Hypothetical Document Embeddings

Improves retrieval by generating hypothetical answers and using them for search.
Blueprint requirement: HyDE query rewrite for better retrieval.

Reference: https://arxiv.org/abs/2212.10496
"""

import logging
from typing import List, Dict, Optional
import asyncio

logger = logging.getLogger(__name__)


class HyDEService:
    """
    Hypothetical Document Embeddings for improved retrieval

    Workflow:
    1. User asks question
    2. LLM generates hypothetical answer(s)
    3. Search using embeddings of hypothetical answer
    4. Results are more relevant than searching the question directly
    """

    def __init__(self, llm_service):
        """
        Initialize HyDE service

        Args:
            llm_service: LLM service for generating hypothetical documents
        """
        self.llm_service = llm_service

    async def generate_hypothetical_document(
        self,
        query: str,
        num_variants: int = 1,
        document_style: str = "informative"
    ) -> List[str]:
        """
        Generate hypothetical documents that would answer the query

        Args:
            query: User's question or search query
            num_variants: Number of hypothetical documents to generate
            document_style: Style hint (informative, technical, conversational)

        Returns:
            List of hypothetical document texts
        """
        hypothetical_docs = []

        # Generate system prompt based on style
        style_prompts = {
            "informative": "You are writing clear, factual documentation.",
            "technical": "You are writing technical documentation with precise details.",
            "conversational": "You are writing in a natural, conversational tone.",
            "email": "You are writing an email response.",
            "report": "You are writing a formal report."
        }

        system_prompt = style_prompts.get(document_style, style_prompts["informative"])

        # Prompt for generating hypothetical document
        hyde_prompt = f"""Given this question: "{query}"

Write a short, direct answer (2-3 paragraphs) as if you found the perfect document that answers this question.

Do not say "the answer is..." or "based on...". Just write the document content directly.
Be specific and factual. Include relevant details, names, dates, or numbers if appropriate for the question."""

        try:
            for i in range(num_variants):
                # Generate hypothetical answer
                response = await self.llm_service.generate_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": hyde_prompt}
                    ],
                    max_tokens=300,
                    temperature=0.7 + (i * 0.1)  # Slight variation for multiple variants
                )

                hypothetical_doc = response.strip()

                if hypothetical_doc:
                    hypothetical_docs.append(hypothetical_doc)
                    logger.info(f"Generated hypothetical document variant {i+1}: {len(hypothetical_doc)} chars")

            return hypothetical_docs

        except Exception as e:
            logger.error(f"HyDE generation failed: {e}")
            # Fallback: return original query
            return [query]

    async def expand_query_with_hyde(
        self,
        query: str,
        num_variants: int = 2,
        include_original: bool = True
    ) -> List[str]:
        """
        Expand query with hypothetical documents

        Args:
            query: Original user query
            num_variants: Number of HyDE variants to generate
            include_original: Whether to include original query in results

        Returns:
            List of queries to search with (original + hypothetical docs)
        """
        queries = []

        # Optionally include original query
        if include_original:
            queries.append(query)

        # Generate hypothetical documents
        hypothetical_docs = await self.generate_hypothetical_document(
            query=query,
            num_variants=num_variants
        )

        queries.extend(hypothetical_docs)

        logger.info(f"Expanded query into {len(queries)} variants (original: {include_original})")
        return queries

    async def multi_query_search(
        self,
        queries: List[str],
        search_function,
        top_k_per_query: int = 5,
        final_top_k: int = 10,
        dedup_by_id: bool = True
    ) -> List[Dict]:
        """
        Search with multiple queries and merge results

        Args:
            queries: List of query strings to search
            search_function: Async function that takes (query, top_k) and returns results
            top_k_per_query: Top K results per query
            final_top_k: Final top K after merging
            dedup_by_id: Remove duplicate results by doc ID

        Returns:
            Merged and ranked search results
        """
        all_results = []
        seen_ids = set()

        # Search with each query
        for idx, query in enumerate(queries):
            try:
                results = await search_function(query, top_k_per_query)

                # Add results with provenance
                for result in results:
                    doc_id = result.get('id', result.get('doc_id'))

                    # Deduplicate if enabled
                    if dedup_by_id and doc_id in seen_ids:
                        continue

                    # Track seen IDs
                    if doc_id:
                        seen_ids.add(doc_id)

                    # Add query provenance
                    result['from_query_variant'] = idx
                    result['original_score'] = result.get('score', 0.0)

                    all_results.append(result)

                logger.info(f"Query variant {idx}: {len(results)} results")

            except Exception as e:
                logger.error(f"Search failed for query variant {idx}: {e}")
                continue

        # Re-rank by score and return top K
        all_results.sort(key=lambda x: x.get('original_score', 0.0), reverse=True)
        final_results = all_results[:final_top_k]

        logger.info(f"Multi-query search: {len(all_results)} total → {len(final_results)} final")
        return final_results


# Mock LLM service for testing
class MockLLMService:
    """Mock LLM service for testing HyDE"""

    async def generate_completion(self, messages, max_tokens=300, temperature=0.7):
        # Extract query from messages
        user_msg = next((m['content'] for m in messages if m['role'] == 'user'), '')

        # Simple mock response
        if 'kita' in user_msg.lower() or 'handover' in user_msg.lower():
            return """The kita handover schedule has been updated for autumn break.
Parents should pick up children at the new times starting October 15th.
Late pickups on October 2nd have been approved by the administration."""
        else:
            return """This document provides comprehensive information about the topic.
It includes relevant details, context, and answers to common questions.
The information is current and factually accurate."""


# Test
if __name__ == "__main__":
    async def test_hyde():
        # Create mock LLM service
        mock_llm = MockLLMService()

        # Create HyDE service
        hyde = HyDEService(llm_service=mock_llm)

        # Test query
        query = "What are the kita handover times after autumn break?"

        logging.basicConfig(level=logging.INFO)
        logger.info(f"Original query: {query}\n")

        # Generate hypothetical documents
        hypothetical_docs = await hyde.generate_hypothetical_document(query, num_variants=2)

        logger.info(f"✅ Generated {len(hypothetical_docs)} hypothetical documents:\n")
        for idx, doc in enumerate(hypothetical_docs, 1):
            logger.info(f"Variant {idx}:")
            logger.info(doc)
            logger.info(f"\n{'-'*60}\n")

        # Test query expansion
        expanded_queries = await hyde.expand_query_with_hyde(query, num_variants=2)
        logger.info(f"✅ Expanded into {len(expanded_queries)} queries")

    # Run test
    asyncio.run(test_hyde())
