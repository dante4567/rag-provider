"""
Unit tests for EnrichmentService

Tests controlled vocabulary enrichment including:
- Content hashing for deduplication
- Recency score calculation
- Title extraction strategies
- Title sanitization
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import date, timedelta
import hashlib
from src.services.enrichment_service import EnrichmentService
from src.services.llm_service import LLMService
from src.services.vocabulary_service import VocabularyService
from src.models.schemas import DocumentType


# =============================================================================
# EnrichmentService Tests
# =============================================================================

class TestEnrichmentService:
    """Test the EnrichmentService class"""

    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service"""
        return Mock(spec=LLMService)

    @pytest.fixture
    def mock_vocab_service(self):
        """Create mock vocabulary service"""
        vocab = Mock(spec=VocabularyService)
        vocab.get_all_topics.return_value = [
            "school/admin",
            "school/enrollment",
            "work/meetings"
        ]
        vocab.get_active_projects.return_value = [
            "school-2026",
            "work-q4"
        ]
        vocab.get_all_places.return_value = [
            "Florianschule Essen",
            "Office Downtown"
        ]
        vocab.is_valid_topic.return_value = True
        vocab.is_valid_project.return_value = True
        vocab.is_valid_place.return_value = True
        return vocab

    @pytest.fixture
    def service(self, mock_llm_service, mock_vocab_service):
        """Create EnrichmentService instance"""
        return EnrichmentService(mock_llm_service, mock_vocab_service)

    def test_init_with_vocab(self, mock_llm_service, mock_vocab_service):
        """Test initialization with vocabulary service"""
        service = EnrichmentService(mock_llm_service, mock_vocab_service)
        assert service.llm_service == mock_llm_service
        assert service.vocab == mock_vocab_service

    def test_init_without_vocab(self, mock_llm_service):
        """Test initialization without vocabulary service"""
        with patch('src.services.enrichment_service.VocabularyService') as mock_vocab_class:
            mock_vocab_class.side_effect = Exception("Vocab not found")

            service = EnrichmentService(mock_llm_service, None)
            assert service.vocab is None

    def test_generate_content_hash(self, service):
        """Test content hash generation for deduplication"""
        content1 = "This is test content for hashing"
        content2 = "This is test content for hashing"
        content3 = "Different content"

        hash1 = service.generate_content_hash(content1)
        hash2 = service.generate_content_hash(content2)
        hash3 = service.generate_content_hash(content3)

        # Same content = same hash
        assert hash1 == hash2

        # Different content = different hash
        assert hash1 != hash3

        # Hash should be SHA-256 (64 hex chars)
        assert len(hash1) == 64
        assert all(c in '0123456789abcdef' for c in hash1)

    def test_generate_content_hash_deterministic(self, service):
        """Test that hashing is deterministic"""
        content = "Test content"

        # Generate hash multiple times
        hashes = [service.generate_content_hash(content) for _ in range(5)]

        # All should be identical
        assert len(set(hashes)) == 1

    def test_calculate_recency_score_today(self, service):
        """Test recency score for today's document"""
        today = date.today()
        score = service.calculate_recency_score(today)

        # Today should have score very close to 1.0
        assert 0.99 <= score <= 1.0

    def test_calculate_recency_score_old_document(self, service):
        """Test recency score for old documents"""
        # 1 year ago
        one_year_ago = date.today() - timedelta(days=365)
        score = service.calculate_recency_score(one_year_ago)

        # Should be significantly lower but not zero
        assert 0.1 < score < 0.6

    def test_calculate_recency_score_very_old(self, service):
        """Test recency score for very old documents (5+ years)"""
        five_years_ago = date.today() - timedelta(days=365 * 5)
        score = service.calculate_recency_score(five_years_ago)

        # Should hit minimum threshold
        assert score >= 0.05
        assert score <= 0.2

    def test_calculate_recency_score_no_date(self, service):
        """Test recency score with no date defaults to today"""
        score = service.calculate_recency_score(None)

        # No date = today = max score
        assert 0.99 <= score <= 1.0

    def test_calculate_recency_score_decay(self, service):
        """Test that recency score decays over time"""
        today = date.today()
        one_month = today - timedelta(days=30)
        six_months = today - timedelta(days=180)
        one_year = today - timedelta(days=365)

        score_today = service.calculate_recency_score(today)
        score_month = service.calculate_recency_score(one_month)
        score_six = service.calculate_recency_score(six_months)
        score_year = service.calculate_recency_score(one_year)

        # Scores should decrease with age
        assert score_today > score_month
        assert score_month > score_six
        assert score_six > score_year

    def test_extract_title_from_markdown_heading(self, service):
        """Test title extraction from markdown heading"""
        content = """# Important Meeting Notes

This is the meeting content."""

        title = service.extract_title_from_content(content, "meeting.md")

        assert title == "Important Meeting Notes"

    def test_extract_title_from_title_field(self, service):
        """Test title extraction from Title: field"""
        content = """Title: Project Status Report

Content follows here."""

        title = service.extract_title_from_content(content, "report.txt")

        assert "Project Status Report" in title

    def test_extract_title_from_first_sentence(self, service):
        """Test title extraction from first meaningful sentence"""
        content = "The quarterly review meeting discussed several key topics. More details follow."

        title = service.extract_title_from_content(content, "meeting.txt")

        # Should extract first sentence
        assert "quarterly review meeting" in title.lower()

    def test_extract_title_fallback_to_filename(self, service):
        """Test title falls back to filename if no good title found"""
        content = "a b c d e"  # Too short
        filename = "important-document-2025.pdf"

        title = service.extract_title_from_content(content, filename)

        # Should use cleaned filename
        assert "important" in title.lower() or "document" in title.lower()

    def test_extract_title_ignores_too_long(self, service):
        """Test that overly long titles are skipped"""
        # Very long heading (> 15 words)
        content = """# This is an extremely long title that goes on and on with way too many words to be useful as a title for any document

Content here."""

        filename = "doc.md"
        title = service.extract_title_from_content(content, filename)

        # Should not use the long heading, should fall back
        assert len(title.split()) < 20

    def test_extract_title_ignores_too_short(self, service):
        """Test that overly short titles are skipped"""
        content = """# Hi

This is content."""

        filename = "document.md"
        title = service.extract_title_from_content(content, filename)

        # "Hi" is too short (< 5 words), should fall back
        assert title != "Hi"

    def test_sanitize_title_basic(self, service):
        """Test basic title sanitization"""
        # Remove special characters
        result = service.sanitize_title("Title: [DRAFT] - (Version 2)")
        assert "[" not in result
        assert "]" not in result
        assert "DRAFT" in result

    def test_sanitize_title_length_limit(self, service):
        """Test title length limiting"""
        long_title = "A" * 200

        result = service.sanitize_title(long_title, max_length=100)

        assert len(result) <= 100

    def test_sanitize_title_whitespace(self, service):
        """Test title whitespace normalization"""
        title = "Title   with    extra    spaces"

        result = service.sanitize_title(title)

        # Should collapse multiple spaces
        assert "    " not in result
        assert "Title with extra spaces" == result or "Title  with  extra  spaces" in result


# =============================================================================
# Integration-style Tests
# =============================================================================

class TestEnrichmentServiceIntegration:
    """Integration-style tests for enrichment workflow"""

    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service with async call_llm"""
        llm = Mock(spec=LLMService)
        llm.call_llm = AsyncMock(return_value=(
            '{"summary": "Test summary", "topics": ["school/admin"], "people": ["Teacher"], "places": ["School"]}',
            0.001
        ))
        return llm

    @pytest.fixture
    def mock_vocab_service(self):
        """Create mock vocabulary service"""
        vocab = Mock(spec=VocabularyService)
        vocab.get_all_topics.return_value = ["school/admin", "work/meetings"]
        vocab.get_active_projects.return_value = ["school-2026"]
        vocab.get_all_places.return_value = ["Florianschule Essen"]
        vocab.is_valid_topic.return_value = True
        vocab.is_valid_project.return_value = True
        vocab.is_valid_place.return_value = True
        return vocab

    @pytest.mark.asyncio
    async def test_enrich_document_basic(self, mock_llm_service, mock_vocab_service):
        """Test basic document enrichment workflow"""
        service = EnrichmentService(mock_llm_service, mock_vocab_service)

        result = await service.enrich_document(
            content="Test document about school enrollment.",
            filename="enrollment.pdf",
            document_type=DocumentType.pdf,
            created_at=date.today()
        )

        # Should return metadata
        assert isinstance(result, dict)
        assert "content_hash" in result
        assert "recency_score" in result
        assert "enrichment_version" in result

    def test_content_hash_for_deduplication(self, mock_llm_service, mock_vocab_service):
        """Test that identical content produces same hash"""
        service = EnrichmentService(mock_llm_service, mock_vocab_service)

        content = "Exact same content for testing"

        hash1 = service.generate_content_hash(content)
        hash2 = service.generate_content_hash(content)

        assert hash1 == hash2  # Deduplication should work
