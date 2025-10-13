"""
Tests for QualityScoringService - Quality gates and scoring

Tests cover:
- Quality score calculation (OCR, parse, length, structure)
- Novelty score calculation (corpus size)
- Actionability score calculation (watchlist hits)
- Signalness composite scoring
- Index gating decisions per document type
- Document type normalization
- Complete scoring pipeline
"""

import pytest
from src.services.quality_scoring_service import (
    QualityScoringService,
    DocumentType,
    QUALITY_GATES
)


class TestQualityScoringServiceInit:
    """Test service initialization"""

    def test_init(self):
        """Should initialize with quality gates"""
        service = QualityScoringService()
        assert service.gates == QUALITY_GATES
        assert len(service.gates) == 8  # 8 document types


class TestQualityScoreCalculation:
    """Test quality_score calculation"""

    def test_quality_score_long_content_with_structure(self):
        """Long content with structure should score high"""
        service = QualityScoringService()
        content = "# Heading\n\n" + "This is good content. " * 50  # >300 chars
        score = service.calculate_quality_score(content, has_structure=True)
        assert score >= 0.9  # length_score=1.0, structure_score=1.0

    def test_quality_score_short_content(self):
        """Short content should be penalized"""
        service = QualityScoringService()
        content = "Short"  # 5 chars
        score = service.calculate_quality_score(content, has_structure=True)
        assert score < 0.6  # length_score=0.05 (5/100)

    def test_quality_score_medium_content(self):
        """Medium content (100-300 chars) should score moderately"""
        service = QualityScoringService()
        content = "This is medium length content. " * 5  # ~155 chars
        score = service.calculate_quality_score(content, has_structure=True)
        assert 0.7 <= score <= 0.9  # length_score=0.7

    def test_quality_score_with_ocr_confidence(self):
        """OCR confidence should be factored in"""
        service = QualityScoringService()
        content = "Good content " * 50

        # High OCR confidence
        score_high = service.calculate_quality_score(
            content, ocr_confidence=0.95, has_structure=True
        )

        # Low OCR confidence
        score_low = service.calculate_quality_score(
            content, ocr_confidence=0.5, has_structure=True
        )

        assert score_high > score_low

    def test_quality_score_with_parse_quality(self):
        """Parse quality should be factored in"""
        service = QualityScoringService()
        content = "Good content " * 50

        # High parse quality
        score_high = service.calculate_quality_score(
            content, parse_quality=0.9, has_structure=True
        )

        # Low parse quality
        score_low = service.calculate_quality_score(
            content, parse_quality=0.4, has_structure=True
        )

        assert score_high > score_low

    def test_quality_score_no_structure(self):
        """No structure should reduce score"""
        service = QualityScoringService()
        content = "Good content " * 50

        score_with = service.calculate_quality_score(content, has_structure=True)
        score_without = service.calculate_quality_score(content, has_structure=False)

        assert score_with > score_without

    def test_quality_score_all_factors(self):
        """All factors combined should average correctly"""
        service = QualityScoringService()
        content = "Good content " * 50  # >300 chars

        score = service.calculate_quality_score(
            content,
            ocr_confidence=0.8,
            parse_quality=0.9,
            has_structure=True
        )

        # Should be average of: 0.8 (OCR) + 0.9 (parse) + 1.0 (length) + 1.0 (structure) = 3.7/4 = 0.925
        assert 0.9 <= score <= 0.95

    def test_quality_score_empty_content(self):
        """Empty content should score very low"""
        service = QualityScoringService()
        score = service.calculate_quality_score("", has_structure=False)
        assert score < 0.5


class TestNoveltyScoreCalculation:
    """Test novelty_score calculation"""

    def test_novelty_score_new_corpus(self):
        """New corpus (<10 docs) should have high novelty"""
        service = QualityScoringService()
        score = service.calculate_novelty_score("content", existing_docs_count=5)
        assert score == 0.9

    def test_novelty_score_small_corpus(self):
        """Small corpus (10-50 docs) should have good novelty"""
        service = QualityScoringService()
        score = service.calculate_novelty_score("content", existing_docs_count=30)
        assert score == 0.7

    def test_novelty_score_medium_corpus(self):
        """Medium corpus (50-200 docs) should have moderate novelty"""
        service = QualityScoringService()
        score = service.calculate_novelty_score("content", existing_docs_count=100)
        assert score == 0.6

    def test_novelty_score_large_corpus(self):
        """Large corpus (>200 docs) should have lower novelty baseline"""
        service = QualityScoringService()
        score = service.calculate_novelty_score("content", existing_docs_count=500)
        assert score == 0.5

    def test_novelty_score_edge_cases(self):
        """Test boundary conditions"""
        service = QualityScoringService()
        assert service.calculate_novelty_score("content", existing_docs_count=0) == 0.9
        assert service.calculate_novelty_score("content", existing_docs_count=10) == 0.7
        assert service.calculate_novelty_score("content", existing_docs_count=50) == 0.6
        assert service.calculate_novelty_score("content", existing_docs_count=200) == 0.5


class TestActionabilityScoreCalculation:
    """Test actionability_score calculation"""

    def test_actionability_baseline(self):
        """No watchlist hits should give baseline 0.5"""
        service = QualityScoringService()
        metadata = {}
        score = service.calculate_actionability_score(metadata)
        assert score == 0.5

    def test_actionability_people_hit(self):
        """Watchlist people hit should increase score"""
        service = QualityScoringService()
        metadata = {"people_roles": "Alice Smith (lawyer), Bob Jones"}
        score = service.calculate_actionability_score(
            metadata, watchlist_people=["Alice Smith"]
        )
        assert score == 0.7  # 0.5 + 0.2

    def test_actionability_projects_hit(self):
        """Watchlist projects hit should increase score"""
        service = QualityScoringService()
        metadata = {"projects": "school-2026, tax-audit"}
        score = service.calculate_actionability_score(
            metadata, watchlist_projects=["school-2026"]
        )
        assert score == 0.7  # 0.5 + 0.2

    def test_actionability_topics_hit(self):
        """Watchlist topics hit should increase score"""
        service = QualityScoringService()
        metadata = {"topics": "school/admin, legal/contracts"}
        score = service.calculate_actionability_score(
            metadata, watchlist_topics=["school/admin"]
        )
        assert score == 0.6  # 0.5 + 0.1

    def test_actionability_dates_present(self):
        """Presence of dates should increase score"""
        service = QualityScoringService()
        metadata = {"dates": "2025-10-15, 2025-11-20"}
        score = service.calculate_actionability_score(metadata)
        assert score == 0.6  # 0.5 + 0.1

    def test_actionability_all_factors(self):
        """All factors combined should boost score"""
        service = QualityScoringService()
        metadata = {
            "people_roles": "Alice Smith (lawyer)",
            "projects": "school-2026",
            "topics": "legal/contracts",
            "dates": "2025-10-15"
        }
        score = service.calculate_actionability_score(
            metadata,
            watchlist_people=["Alice Smith"],
            watchlist_projects=["school-2026"],
            watchlist_topics=["legal/contracts"]
        )
        # 0.5 + 0.2 (people) + 0.2 (projects) + 0.1 (topics) + 0.1 (dates) = 1.1 → capped at 1.0
        assert score == 1.0

    def test_actionability_case_insensitive(self):
        """Watchlist matching should be case-insensitive"""
        service = QualityScoringService()
        metadata = {"people_roles": "ALICE SMITH (lawyer)"}
        score = service.calculate_actionability_score(
            metadata, watchlist_people=["alice smith"]
        )
        assert score == 0.7

    def test_actionability_missing_fields(self):
        """Missing metadata fields should not crash"""
        service = QualityScoringService()
        metadata = {}  # Empty
        score = service.calculate_actionability_score(
            metadata,
            watchlist_people=["Alice"],
            watchlist_projects=["project"],
            watchlist_topics=["topic"]
        )
        assert score == 0.5  # Baseline


class TestSignalnessCalculation:
    """Test signalness composite scoring"""

    def test_signalness_formula(self):
        """Should calculate weighted average: 0.4*quality + 0.3*novelty + 0.3*actionability"""
        service = QualityScoringService()
        signalness = service.calculate_signalness(
            quality=1.0, novelty=0.8, actionability=0.6
        )
        expected = 0.4 * 1.0 + 0.3 * 0.8 + 0.3 * 0.6
        assert signalness == pytest.approx(expected)  # 0.4 + 0.24 + 0.18 = 0.82

    def test_signalness_all_high(self):
        """All high scores should give high signalness"""
        service = QualityScoringService()
        signalness = service.calculate_signalness(1.0, 1.0, 1.0)
        assert signalness == 1.0

    def test_signalness_all_low(self):
        """All low scores should give low signalness"""
        service = QualityScoringService()
        signalness = service.calculate_signalness(0.3, 0.3, 0.3)
        assert signalness == 0.3

    def test_signalness_quality_weighted_highest(self):
        """Quality should have highest weight (40%)"""
        service = QualityScoringService()

        # High quality, low others
        score1 = service.calculate_signalness(1.0, 0.0, 0.0)

        # Low quality, high others
        score2 = service.calculate_signalness(0.0, 1.0, 1.0)

        assert score1 == 0.4  # 40% of 1.0
        assert score2 == 0.6  # 30% + 30%


class TestDocumentTypeNormalization:
    """Test document type string normalization"""

    def test_normalize_email_thread(self):
        """Should recognize email/thread variations"""
        service = QualityScoringService()
        assert service._normalize_doc_type("email") == DocumentType.EMAIL_THREAD
        assert service._normalize_doc_type("Email Thread") == DocumentType.EMAIL_THREAD
        assert service._normalize_doc_type("thread") == DocumentType.EMAIL_THREAD

    def test_normalize_chat(self):
        """Should recognize chat variations"""
        service = QualityScoringService()
        assert service._normalize_doc_type("chat") == DocumentType.CHAT_DAILY
        assert service._normalize_doc_type("Chat Daily") == DocumentType.CHAT_DAILY

    def test_normalize_pdf_report(self):
        """Should recognize PDF/report variations"""
        service = QualityScoringService()
        assert service._normalize_doc_type("pdf") == DocumentType.PDF_REPORT
        assert service._normalize_doc_type("PDF Report") == DocumentType.PDF_REPORT
        assert service._normalize_doc_type("report") == DocumentType.PDF_REPORT

    def test_normalize_web_article(self):
        """Should recognize web/article variations"""
        service = QualityScoringService()
        assert service._normalize_doc_type("web") == DocumentType.WEB_ARTICLE
        assert service._normalize_doc_type("Web Article") == DocumentType.WEB_ARTICLE
        assert service._normalize_doc_type("article") == DocumentType.WEB_ARTICLE

    def test_normalize_note(self):
        """Should recognize note variations"""
        service = QualityScoringService()
        assert service._normalize_doc_type("note") == DocumentType.NOTE
        assert service._normalize_doc_type("Note") == DocumentType.NOTE

    def test_normalize_text(self):
        """Should recognize text variations"""
        service = QualityScoringService()
        assert service._normalize_doc_type("text") == DocumentType.TEXT
        assert service._normalize_doc_type("Text File") == DocumentType.TEXT

    def test_normalize_legal(self):
        """Should recognize legal/court variations"""
        service = QualityScoringService()
        assert service._normalize_doc_type("legal") == DocumentType.LEGAL
        assert service._normalize_doc_type("court") == DocumentType.LEGAL
        assert service._normalize_doc_type("Legal Document") == DocumentType.LEGAL

    def test_normalize_generic(self):
        """Unknown types should default to GENERIC"""
        service = QualityScoringService()
        assert service._normalize_doc_type("unknown") == DocumentType.GENERIC
        assert service._normalize_doc_type("random") == DocumentType.GENERIC
        assert service._normalize_doc_type("") == DocumentType.GENERIC


class TestShouldIndexDecisions:
    """Test index gating decisions"""

    def test_should_index_passes_both_gates(self):
        """Document passing both quality and signal gates should be indexed"""
        service = QualityScoringService()
        # Legal docs require quality>=0.80, signal>=0.70
        should_index = service.should_index("legal", quality_score=0.85, signalness=0.75)
        assert should_index is True

    def test_should_index_fails_quality_gate(self):
        """Document failing quality gate should NOT be indexed"""
        service = QualityScoringService()
        # Legal docs require quality>=0.80
        should_index = service.should_index("legal", quality_score=0.75, signalness=0.75)
        assert should_index is False

    def test_should_index_fails_signal_gate(self):
        """Document failing signal gate should NOT be indexed"""
        service = QualityScoringService()
        # Legal docs require signal>=0.70
        should_index = service.should_index("legal", quality_score=0.85, signalness=0.65)
        assert should_index is False

    def test_should_index_fails_both_gates(self):
        """Document failing both gates should NOT be indexed"""
        service = QualityScoringService()
        should_index = service.should_index("legal", quality_score=0.70, signalness=0.60)
        assert should_index is False

    def test_should_index_note_lower_thresholds(self):
        """Note type should have lower thresholds (quality>=0.60, signal>=0.50)"""
        service = QualityScoringService()
        # Would fail legal gates but passes note gates
        should_index = service.should_index("note", quality_score=0.65, signalness=0.55)
        assert should_index is True

    def test_should_index_generic_fallback(self):
        """Unknown doc types should use GENERIC gates (quality>=0.65, signal>=0.55)"""
        service = QualityScoringService()
        should_index = service.should_index("unknown", quality_score=0.70, signalness=0.60)
        assert should_index is True

    def test_should_index_exact_threshold(self):
        """Document exactly at threshold should pass"""
        service = QualityScoringService()
        # Legal gates: quality>=0.80, signal>=0.70
        should_index = service.should_index("legal", quality_score=0.80, signalness=0.70)
        assert should_index is True


class TestCompleteDocumentScoring:
    """Test complete score_document pipeline"""

    def test_score_document_high_quality(self):
        """High-quality document should score well and be indexed"""
        service = QualityScoringService()
        content = "# Important Report\n\n" + "This is excellent content. " * 50
        metadata = {
            "people_roles": "Alice Smith (lawyer)",
            "projects": "school-2026",
            "topics": "legal/contracts",
            "dates": "2025-10-15"
        }

        result = service.score_document(
            content=content,
            document_type="legal",
            metadata=metadata,
            ocr_confidence=0.95,
            existing_docs_count=5,
            watchlist_people=["Alice Smith"],
            watchlist_projects=["school-2026"]
        )

        assert result["quality_score"] > 0.8
        assert result["novelty_score"] == 0.9  # New corpus
        assert result["actionability_score"] > 0.7
        assert result["signalness"] > 0.7
        assert result["do_index"] is True
        assert result["gate_reason"] is None

    def test_score_document_low_quality(self):
        """Low-quality document should not be indexed"""
        service = QualityScoringService()
        content = "Short"  # Very short
        metadata = {}

        result = service.score_document(
            content=content,
            document_type="legal",
            metadata=metadata,
            existing_docs_count=500
        )

        assert result["do_index"] is False
        assert result["gate_reason"] is not None
        assert "Quality" in result["gate_reason"] or "Signal" in result["gate_reason"]

    def test_score_document_structure_detection(self):
        """Should detect structure from markdown headings"""
        service = QualityScoringService()
        content_with = "# Heading\n\nContent " * 50
        content_without = "Content " * 50

        result_with = service.score_document(
            content_with, "note", {}, existing_docs_count=50
        )
        result_without = service.score_document(
            content_without, "note", {}, existing_docs_count=50
        )

        # Document with structure should score slightly higher
        assert result_with["quality_score"] >= result_without["quality_score"]

    def test_score_document_returns_rounded_scores(self):
        """Should return scores rounded to 3 decimals"""
        service = QualityScoringService()
        content = "Good content " * 50
        metadata = {}

        result = service.score_document(content, "note", metadata)

        # Check all scores are rounded to 3 decimals
        assert len(str(result["quality_score"]).split(".")[-1]) <= 3
        assert len(str(result["novelty_score"]).split(".")[-1]) <= 3
        assert len(str(result["actionability_score"]).split(".")[-1]) <= 3
        assert len(str(result["signalness"]).split(".")[-1]) <= 3

    def test_score_document_gate_reason_quality(self):
        """Should provide gate reason when quality fails"""
        service = QualityScoringService()
        content = "Short"
        metadata = {}

        result = service.score_document(
            content, "legal", metadata, existing_docs_count=5
        )

        assert result["do_index"] is False
        assert "Quality" in result["gate_reason"]

    def test_score_document_gate_reason_signal(self):
        """Should provide gate reason when signal fails"""
        service = QualityScoringService()
        content = "Good content " * 50  # Long enough for quality
        metadata = {}  # No actionability

        result = service.score_document(
            content, "legal", metadata, existing_docs_count=500  # Low novelty
        )

        # May fail on signal gate
        if not result["do_index"]:
            assert result["gate_reason"] is not None

    def test_score_document_complete_pipeline(self):
        """Complete pipeline should return all expected fields"""
        service = QualityScoringService()
        content = "Content " * 50
        metadata = {"topics": "general"}

        result = service.score_document(content, "text", metadata)

        # Verify all fields present
        assert "quality_score" in result
        assert "novelty_score" in result
        assert "actionability_score" in result
        assert "signalness" in result
        assert "do_index" in result
        assert "gate_reason" in result


class TestQualityGatesConfig:
    """Test quality gates configuration"""

    def test_quality_gates_all_doc_types(self):
        """Should have gates for all document types"""
        assert len(QUALITY_GATES) == 8
        assert DocumentType.EMAIL_THREAD in QUALITY_GATES
        assert DocumentType.CHAT_DAILY in QUALITY_GATES
        assert DocumentType.PDF_REPORT in QUALITY_GATES
        assert DocumentType.WEB_ARTICLE in QUALITY_GATES
        assert DocumentType.NOTE in QUALITY_GATES
        assert DocumentType.TEXT in QUALITY_GATES
        assert DocumentType.LEGAL in QUALITY_GATES
        assert DocumentType.GENERIC in QUALITY_GATES

    def test_quality_gates_structure(self):
        """Each gate should have min_quality and min_signal"""
        for doc_type, gates in QUALITY_GATES.items():
            assert "min_quality" in gates
            assert "min_signal" in gates
            assert 0.0 <= gates["min_quality"] <= 1.0
            assert 0.0 <= gates["min_signal"] <= 1.0

    def test_quality_gates_legal_strictest(self):
        """Legal documents should have highest thresholds"""
        legal_gates = QUALITY_GATES[DocumentType.LEGAL]
        assert legal_gates["min_quality"] == 0.80
        assert legal_gates["min_signal"] == 0.70

        # Should be higher than most other types
        note_gates = QUALITY_GATES[DocumentType.NOTE]
        assert legal_gates["min_quality"] > note_gates["min_quality"]
        assert legal_gates["min_signal"] > note_gates["min_signal"]


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_content_complete_pipeline(self):
        """Empty content should not crash"""
        service = QualityScoringService()
        result = service.score_document("", "text", {})
        assert result["do_index"] is False

    def test_none_metadata_values(self):
        """None values in metadata should not crash"""
        service = QualityScoringService()
        metadata = {
            "people_roles": None,
            "projects": None,
            "topics": None
        }
        score = service.calculate_actionability_score(metadata)
        assert score == 0.5  # Baseline

    def test_very_long_content(self):
        """Very long content should not cause issues"""
        service = QualityScoringService()
        content = "Word " * 10000  # 50k+ chars
        score = service.calculate_quality_score(content)
        assert score > 0.8  # Should score high

    def test_unicode_content(self):
        """Unicode content should be handled correctly"""
        service = QualityScoringService()
        content = "Café über München 日本語 " * 50
        result = service.score_document(content, "note", {})
        assert result["quality_score"] > 0.0

    def test_special_characters_in_metadata(self):
        """Special characters in metadata should not crash"""
        service = QualityScoringService()
        metadata = {
            "people_roles": "Dr. O'Brien (lawyer) & Co.",
            "topics": "legal/contracts & agreements"
        }
        score = service.calculate_actionability_score(
            metadata, watchlist_people=["O'Brien"]
        )
        assert score > 0.5
