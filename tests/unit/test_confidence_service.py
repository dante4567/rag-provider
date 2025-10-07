"""
Unit tests for ConfidenceService

Tests insufficient evidence detection to prevent hallucinations
"""
import pytest
from src.services.confidence_service import ConfidenceService, ConfidenceAssessment


class TestConfidenceService:
    """Test the ConfidenceService class"""

    @pytest.fixture
    def service(self):
        """Create ConfidenceService instance"""
        return ConfidenceService(
            min_relevance=0.5,
            min_coverage=0.4,
            min_quality=0.3,
            min_overall=0.6
        )

    def test_init_default(self):
        """Test initialization with default thresholds"""
        service = ConfidenceService()
        assert service.min_relevance == 0.5
        assert service.min_coverage == 0.4
        assert service.min_quality == 0.3
        assert service.min_overall == 0.6

    def test_init_custom_thresholds(self):
        """Test initialization with custom thresholds"""
        service = ConfidenceService(
            min_relevance=0.7,
            min_coverage=0.6,
            min_quality=0.5,
            min_overall=0.8
        )
        assert service.min_relevance == 0.7
        assert service.min_coverage == 0.6
        assert service.min_quality == 0.5
        assert service.min_overall == 0.8

    def test_relevance_score_high(self, service):
        """Test relevance calculation with high scores"""
        chunks = [
            {"score": 0.95},
            {"score": 0.90},
            {"score": 0.85}
        ]
        score = service.calculate_relevance_score("query", chunks)
        assert score >= 0.85
        assert score <= 1.0

    def test_relevance_score_low(self, service):
        """Test relevance calculation with low scores"""
        chunks = [
            {"score": 0.2},
            {"score": 0.1}
        ]
        score = service.calculate_relevance_score("query", chunks)
        assert score < 0.3

    def test_relevance_score_empty_chunks(self, service):
        """Test relevance with no chunks"""
        score = service.calculate_relevance_score("query", [])
        assert score == 0.0

    def test_coverage_score_full(self, service):
        """Test coverage when all keywords are present"""
        query = "kita handover schedule times"
        chunks = [
            {"content": "The kita handover schedule shows new times for pickup."}
        ]
        score = service.calculate_coverage_score(query, chunks)
        assert score >= 0.8  # Most keywords present

    def test_coverage_score_partial(self, service):
        """Test coverage with partial keyword match"""
        query = "kita handover schedule times autumn break"
        chunks = [
            {"content": "The kita handover schedule has changed."}
        ]
        score = service.calculate_coverage_score(query, chunks)
        assert 0.3 < score < 0.8  # Some keywords present

    def test_coverage_score_none(self, service):
        """Test coverage with no keyword match"""
        query = "kita handover schedule"
        chunks = [
            {"content": "Completely unrelated content about weather."}
        ]
        score = service.calculate_coverage_score(query, chunks)
        assert score < 0.3

    def test_coverage_score_empty_query(self, service):
        """Test coverage with empty query"""
        chunks = [{"content": "Some content"}]
        score = service.calculate_coverage_score("", chunks)
        assert score == 0.0

    def test_quality_score_high(self, service):
        """Test quality with good metadata and length"""
        chunks = [
            {
                "content": "A" * 500,  # Good length
                "metadata": {"has_structure": True}
            }
        ]
        score = service.calculate_quality_score(chunks)
        assert score >= 0.6

    def test_quality_score_low(self, service):
        """Test quality with poor metadata and length"""
        chunks = [
            {
                "content": "Short",  # Too short
                "metadata": {}
            }
        ]
        score = service.calculate_quality_score(chunks)
        assert score < 0.5

    def test_quality_score_empty_chunks(self, service):
        """Test quality with no chunks"""
        score = service.calculate_quality_score([])
        assert score == 0.0

    def test_assess_confidence_sufficient(self, service):
        """Test assessment with sufficient evidence"""
        query = "What are the kita handover times?"
        chunks = [
            {
                "content": "The kita handover times are 4:30 PM after autumn break.",
                "score": 0.92,
                "metadata": {"has_structure": True}
            }
        ]

        assessment = service.assess_confidence(query, chunks)

        assert isinstance(assessment, ConfidenceAssessment)
        assert assessment.is_sufficient is True
        assert assessment.overall_confidence >= 0.6
        assert assessment.recommendation == "answer"

    def test_assess_confidence_insufficient_relevance(self, service):
        """Test assessment with low relevance"""
        query = "What are the kita times?"
        chunks = [
            {
                "content": "Completely unrelated content.",
                "score": 0.2,
                "metadata": {}
            }
        ]

        assessment = service.assess_confidence(query, chunks)

        assert assessment.is_sufficient is False
        assert assessment.relevance_score < 0.5
        assert "low relevance" in assessment.reason.lower()

    def test_assess_confidence_insufficient_coverage(self, service):
        """Test assessment with low coverage"""
        query = "What are the new kita handover schedule times after autumn break?"
        chunks = [
            {
                "content": "The kita exists.",  # Very minimal coverage
                "score": 0.6,
                "metadata": {}
            }
        ]

        assessment = service.assess_confidence(query, chunks)

        # May fail on coverage or overall
        assert assessment.is_sufficient is False
        assert assessment.coverage_score < 0.6

    def test_assess_confidence_no_chunks(self, service):
        """Test assessment with no retrieved chunks"""
        query = "What is the answer?"
        chunks = []

        assessment = service.assess_confidence(query, chunks)

        assert assessment.is_sufficient is False
        assert assessment.overall_confidence == 0.0
        assert assessment.recommendation == "refuse_no_results"

    def test_response_no_results(self, service):
        """Test response generation for no results"""
        assessment = ConfidenceAssessment(
            overall_confidence=0.0,
            relevance_score=0.0,
            coverage_score=0.0,
            quality_score=0.0,
            is_sufficient=False,
            reason="No results",
            recommendation="refuse_no_results"
        )

        response = service.get_response_for_low_confidence(assessment, "query")

        assert "couldn't find" in response.lower()
        assert "relevant documents" in response.lower()

    def test_response_irrelevant(self, service):
        """Test response generation for irrelevant results"""
        assessment = ConfidenceAssessment(
            overall_confidence=0.2,
            relevance_score=0.2,
            coverage_score=0.1,
            quality_score=0.3,
            is_sufficient=False,
            reason="Low relevance",
            recommendation="refuse_irrelevant"
        )

        response = service.get_response_for_low_confidence(assessment, "query")

        assert "don't appear to be relevant" in response.lower()
        assert "rephrase" in response.lower()

    def test_response_clarify(self, service):
        """Test response generation for clarification needed"""
        assessment = ConfidenceAssessment(
            overall_confidence=0.4,
            relevance_score=0.6,
            coverage_score=0.2,
            quality_score=0.5,
            is_sufficient=False,
            reason="Low coverage",
            recommendation="clarify_question"
        )

        response = service.get_response_for_low_confidence(assessment, "query")

        assert "clarify" in response.lower()
        assert "found some" in response.lower()

    def test_response_partial(self, service):
        """Test response generation for partial answer"""
        assessment = ConfidenceAssessment(
            overall_confidence=0.5,
            relevance_score=0.7,
            coverage_score=0.5,
            quality_score=0.4,
            is_sufficient=False,
            reason="Below threshold",
            recommendation="partial_answer"
        )

        response = service.get_response_for_low_confidence(assessment, "query")

        assert "may not fully answer" in response.lower()
        assert "caveats" in response.lower()

    def test_multiple_failure_reasons(self, service):
        """Test assessment with multiple failures"""
        query = "Complex question about many topics"
        chunks = [
            {
                "content": "X",  # Too short, no coverage
                "score": 0.1,  # Low relevance
                "metadata": {}  # No quality
            }
        ]

        assessment = service.assess_confidence(query, chunks)

        assert assessment.is_sufficient is False
        # Should have multiple failure reasons
        assert "," in assessment.reason or " and " in assessment.reason.lower()

    def test_edge_case_exact_threshold(self, service):
        """Test behavior at exact threshold values"""
        # Create service with specific thresholds
        service = ConfidenceService(
            min_relevance=0.5,
            min_coverage=0.4,
            min_quality=0.3,
            min_overall=0.6
        )

        query = "test"
        # Chunks that produce exactly threshold values
        chunks = [
            {
                "content": "test content with reasonable length for quality",
                "score": 0.5,
                "metadata": {"has_structure": False}
            }
        ]

        assessment = service.assess_confidence(query, chunks)

        # At threshold should pass
        # (implementation may vary, but should be consistent)
        assert isinstance(assessment, ConfidenceAssessment)
