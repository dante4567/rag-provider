"""
Confidence Service - Insufficient Evidence Detection

Prevents hallucinations by detecting when retrieved chunks don't contain
sufficient evidence to answer the user's question.

Blueprint requirement: Confidence gates to detect insufficient evidence.
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceAssessment:
    """Results of confidence assessment"""
    overall_confidence: float  # 0.0-1.0
    relevance_score: float     # How relevant are chunks to question?
    coverage_score: float      # How much of question is covered?
    quality_score: float       # Quality of retrieved chunks
    is_sufficient: bool        # Pass/fail gate
    reason: str                # Why insufficient if False
    recommendation: str        # What to do (answer/refuse/clarify)


class ConfidenceService:
    """
    Assess confidence in RAG retrieval results

    Prevents hallucinations by detecting insufficient evidence
    """

    def __init__(
        self,
        min_relevance: float = 0.5,
        min_coverage: float = 0.4,
        min_quality: float = 0.3,
        min_overall: float = 0.6
    ):
        """
        Initialize confidence service

        Args:
            min_relevance: Minimum relevance score to pass
            min_coverage: Minimum coverage score to pass
            min_quality: Minimum quality score to pass
            min_overall: Minimum overall confidence to pass
        """
        self.min_relevance = min_relevance
        self.min_coverage = min_coverage
        self.min_quality = min_quality
        self.min_overall = min_overall

    def calculate_relevance_score(
        self,
        query: str,
        chunks: List[Dict],
        score_field: str = "score"
    ) -> float:
        """
        Calculate relevance score based on retrieval scores

        Args:
            query: User's question
            chunks: Retrieved chunks with scores
            score_field: Field name containing relevance score

        Returns:
            Relevance score (0.0-1.0)
        """
        if not chunks:
            return 0.0

        # Get retrieval scores
        scores = [chunk.get(score_field, 0.0) for chunk in chunks]
        valid_scores = [s for s in scores if s > 0]

        if not valid_scores:
            return 0.0

        # Average of top 3 scores (or all if fewer)
        top_scores = sorted(valid_scores, reverse=True)[:3]
        relevance = sum(top_scores) / len(top_scores)

        return min(relevance, 1.0)

    def calculate_coverage_score(
        self,
        query: str,
        chunks: List[Dict],
        content_field: str = "content"
    ) -> float:
        """
        Calculate how much of the query is covered by chunks

        Args:
            query: User's question
            chunks: Retrieved chunks
            content_field: Field containing chunk text

        Returns:
            Coverage score (0.0-1.0)
        """
        if not chunks or not query.strip():
            return 0.0

        # Extract query keywords (simple tokenization)
        query_words = set(
            word.lower().strip('.,!?;:')
            for word in query.split()
            if len(word) > 3  # Skip short words
        )

        if not query_words:
            return 0.5  # No meaningful keywords

        # Combine all chunk content
        all_content = " ".join(
            chunk.get(content_field, "") for chunk in chunks
        ).lower()

        # Count how many query words appear in chunks
        covered_words = sum(1 for word in query_words if word in all_content)
        coverage = covered_words / len(query_words)

        return coverage

    def calculate_quality_score(
        self,
        chunks: List[Dict]
    ) -> float:
        """
        Calculate quality score based on chunk metadata

        Args:
            chunks: Retrieved chunks with metadata

        Returns:
            Quality score (0.0-1.0)
        """
        if not chunks:
            return 0.0

        quality_scores = []

        for chunk in chunks:
            # Check for quality metadata
            metadata = chunk.get('metadata', {})

            # Quality indicators
            has_structure = bool(metadata.get('has_structure', False))
            chunk_length = len(chunk.get('content', ''))
            has_metadata = len(metadata) > 0

            # Calculate chunk quality
            chunk_quality = 0.0

            # Length indicator (not too short, not too long)
            if 100 <= chunk_length <= 2000:
                chunk_quality += 0.4
            elif 50 <= chunk_length < 100:
                chunk_quality += 0.2

            # Structure indicator
            if has_structure:
                chunk_quality += 0.3

            # Metadata richness
            if has_metadata:
                chunk_quality += 0.3

            quality_scores.append(chunk_quality)

        # Average quality
        avg_quality = sum(quality_scores) / len(quality_scores)
        return min(avg_quality, 1.0)

    def assess_confidence(
        self,
        query: str,
        chunks: List[Dict],
        score_field: str = "score",
        content_field: str = "content"
    ) -> ConfidenceAssessment:
        """
        Assess overall confidence in retrieval results

        Args:
            query: User's question
            chunks: Retrieved chunks
            score_field: Field name for relevance scores
            content_field: Field name for chunk content

        Returns:
            ConfidenceAssessment with decision and reasoning
        """
        # Calculate component scores
        relevance = self.calculate_relevance_score(query, chunks, score_field)
        coverage = self.calculate_coverage_score(query, chunks, content_field)
        quality = self.calculate_quality_score(chunks)

        # Overall confidence (weighted average)
        overall = (
            relevance * 0.5 +  # Relevance is most important
            coverage * 0.3 +   # Coverage matters
            quality * 0.2      # Quality is least critical
        )

        # Check against thresholds
        failures = []

        if relevance < self.min_relevance:
            failures.append(f"low relevance ({relevance:.2f} < {self.min_relevance})")

        if coverage < self.min_coverage:
            failures.append(f"low coverage ({coverage:.2f} < {self.min_coverage})")

        if quality < self.min_quality:
            failures.append(f"low quality ({quality:.2f} < {self.min_quality})")

        if overall < self.min_overall:
            failures.append(f"low overall confidence ({overall:.2f} < {self.min_overall})")

        # Determine pass/fail
        is_sufficient = len(failures) == 0

        # Generate reason and recommendation
        if is_sufficient:
            reason = "Sufficient evidence to answer question"
            recommendation = "answer"
        else:
            reason = "Insufficient evidence: " + ", ".join(failures)

            if not chunks:
                recommendation = "refuse_no_results"
            elif relevance < 0.3:
                recommendation = "refuse_irrelevant"
            elif coverage < 0.3:
                recommendation = "clarify_question"
            else:
                recommendation = "partial_answer"

        logger.info(
            f"Confidence assessment: overall={overall:.2f}, "
            f"relevance={relevance:.2f}, coverage={coverage:.2f}, quality={quality:.2f}, "
            f"sufficient={is_sufficient}"
        )

        return ConfidenceAssessment(
            overall_confidence=overall,
            relevance_score=relevance,
            coverage_score=coverage,
            quality_score=quality,
            is_sufficient=is_sufficient,
            reason=reason,
            recommendation=recommendation
        )

    def get_response_for_low_confidence(
        self,
        assessment: ConfidenceAssessment,
        query: str
    ) -> str:
        """
        Generate appropriate response for low confidence scenarios

        Args:
            assessment: Confidence assessment results
            query: Original user query

        Returns:
            Response text to show user
        """
        if assessment.recommendation == "refuse_no_results":
            return (
                "I couldn't find any relevant documents to answer your question. "
                "The knowledge base may not contain information about this topic."
            )

        elif assessment.recommendation == "refuse_irrelevant":
            return (
                "I found some documents, but they don't appear to be relevant to your question. "
                "Could you rephrase your question or provide more context?"
            )

        elif assessment.recommendation == "clarify_question":
            return (
                "I found some related information, but I'm not confident I can fully answer your question. "
                "Could you clarify what specific aspect you're interested in?"
            )

        elif assessment.recommendation == "partial_answer":
            return (
                "I found some relevant information, but it may not fully answer your question. "
                "Here's what I found (with caveats):"
            )

        else:
            return "Insufficient evidence to answer this question confidently."


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    service = ConfidenceService()

    # Test case 1: Good retrieval
    good_chunks = [
        {
            "content": "The kita handover schedule has been updated for autumn break. "
                      "New pickup times start October 15th at 4:30 PM.",
            "score": 0.92,
            "metadata": {"has_structure": True}
        },
        {
            "content": "Late pickups on October 2nd have been approved by administration.",
            "score": 0.85,
            "metadata": {"has_structure": False}
        }
    ]

    query = "What are the new kita handover times after autumn break?"

    assessment = service.assess_confidence(query, good_chunks)

    logger.info("=" * 60)
    logger.info("Test 1: Good Retrieval")
    logger.info("=" * 60)
    logger.info(f"Query: {query}")
    logger.info(f"\nOverall Confidence: {assessment.overall_confidence:.2f}")
    logger.info(f"Relevance: {assessment.relevance_score:.2f}")
    logger.info(f"Coverage: {assessment.coverage_score:.2f}")
    logger.info(f"Quality: {assessment.quality_score:.2f}")
    logger.info(f"Sufficient? {assessment.is_sufficient}")
    logger.info(f"Reason: {assessment.reason}")
    logger.info(f"Recommendation: {assessment.recommendation}")

    # Test case 2: Poor retrieval
    poor_chunks = [
        {
            "content": "Random unrelated content about weather.",
            "score": 0.25,
            "metadata": {}
        }
    ]

    assessment2 = service.assess_confidence(query, poor_chunks)

    logger.info("\n" + "=" * 60)
    logger.info("Test 2: Poor Retrieval")
    logger.info("=" * 60)
    logger.info(f"Query: {query}")
    logger.info(f"\nOverall Confidence: {assessment2.overall_confidence:.2f}")
    logger.info(f"Relevance: {assessment2.relevance_score:.2f}")
    logger.info(f"Coverage: {assessment2.coverage_score:.2f}")
    logger.info(f"Quality: {assessment2.quality_score:.2f}")
    logger.info(f"Sufficient? {assessment2.is_sufficient}")
    logger.info(f"Reason: {assessment2.reason}")
    logger.info(f"Recommendation: {assessment2.recommendation}")
    logger.info(f"\nResponse: {service.get_response_for_low_confidence(assessment2, query)}")
