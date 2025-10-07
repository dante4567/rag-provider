"""
Basic unit tests for QualityScoringService

Tests the quality scoring and do_index gate functionality
"""
import pytest
from src.services.quality_scoring_service import (
    QualityScoringService,
    DocumentType,
    QUALITY_GATES
)


class TestQualityScoringService:
    """Test the QualityScoringService class"""

    def test_init(self):
        """Test initialization"""
        service = QualityScoringService()
        assert service.gates == QUALITY_GATES
        assert len(service.gates) > 0

    def test_calculate_quality_score_high_quality(self):
        """Test quality score calculation for high-quality content"""
        service = QualityScoringService()
        content = "A" * 500  # Long content
        score = service.calculate_quality_score(
            content=content,
            ocr_confidence=0.95,
            parse_quality=0.90,
            has_structure=True
        )
        assert 0.8 <= score <= 1.0

    def test_calculate_quality_score_short_content(self):
        """Test quality score penalizes very short content"""
        service = QualityScoringService()
        content = "Short"  # < 100 chars
        score = service.calculate_quality_score(content=content)
        assert score < 0.8  # Should be penalized

    def test_calculate_quality_score_no_structure(self):
        """Test quality score with no structure"""
        service = QualityScoringService()
        content = "A" * 500
        score = service.calculate_quality_score(
            content=content,
            has_structure=False
        )
        assert score < 1.0  # Should be lower than with structure

    def test_quality_gates_exist_for_all_types(self):
        """Test that quality gates are defined for all document types"""
        service = QualityScoringService()
        for doc_type in DocumentType:
            assert doc_type in service.gates
            gate = service.gates[doc_type]
            assert "min_quality" in gate
            assert "min_signal" in gate

    def test_quality_gates_reasonable_thresholds(self):
        """Test that quality gate thresholds are reasonable"""
        service = QualityScoringService()
        for doc_type, gate in service.gates.items():
            # Thresholds should be between 0 and 1
            assert 0 <= gate["min_quality"] <= 1
            assert 0 <= gate["min_signal"] <= 1
            # Quality should generally be higher than signal
            assert gate["min_quality"] >= gate["min_signal"] - 0.2

    def test_legal_docs_have_highest_threshold(self):
        """Test that legal documents have strictest gates"""
        service = QualityScoringService()
        legal_gate = service.gates[DocumentType.LEGAL]
        # Legal should have higher thresholds than most types
        assert legal_gate["min_quality"] >= 0.75
        assert legal_gate["min_signal"] >= 0.65

    def test_notes_have_lowest_threshold(self):
        """Test that notes have most lenient gates"""
        service = QualityScoringService()
        note_gate = service.gates[DocumentType.NOTE]
        # Notes should have lower thresholds
        assert note_gate["min_quality"] <= 0.65
        assert note_gate["min_signal"] <= 0.55
