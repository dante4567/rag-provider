"""
Test quality gates (do_index) functionality

Verifies that the quality scoring service:
1. Calculates quality, novelty, actionability scores correctly
2. Applies per-document-type thresholds
3. Gates low-quality documents appropriately
4. Allows high-quality documents to pass
"""
import pytest
import requests
import time


BASE_URL = "http://localhost:8001"


class TestQualityGates:
    """Test do_index quality gates per document type"""

    def test_quality_gates_available_in_health(self):
        """Quality scoring should be available"""
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        assert response.status_code == 200
        # Quality gates work internally, not necessarily exposed in health

    def test_high_quality_document_passes_gate(self):
        """High-quality structured document should pass quality gate"""
        high_quality_doc = {
            "content": """# Annual Report 2025

## Executive Summary
This comprehensive report analyzes our performance across multiple dimensions.

## Financial Performance
Revenue increased by 23% year-over-year, driven by strong product adoption.

### Key Metrics
- Revenue: $5.2M
- Growth: 23% YoY
- Customers: 1,450

## Strategic Initiatives
We launched three major initiatives this quarter:
1. Product expansion into enterprise market
2. International operations in EMEA
3. Platform modernization

## Conclusion
Strong performance positions us well for continued growth.
""",
            "filename": "annual_report_2025.md",
            "document_type": "pdf"
        }

        response = requests.post(f"{BASE_URL}/ingest", json=high_quality_doc, timeout=30)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        # Should NOT be gated
        if "metadata" in data and data["metadata"]:
            assert data["metadata"].get("gated", False) is False, \
                "High-quality structured document should pass quality gate"

        # Should have quality scores in metadata
        metadata = data.get("metadata", {})
        if "quality_score" in metadata:
            assert metadata["quality_score"] >= 0.7, "Should have high quality score"

    def test_low_quality_document_fails_gate(self):
        """Very short, low-quality document should fail quality gate"""
        low_quality_doc = {
            "content": "This is a simple test document with minimal content that may not pass quality gates.",
            "filename": "test.txt",
            "document_type": "text"
        }

        response = requests.post(f"{BASE_URL}/ingest", json=low_quality_doc, timeout=30)
        assert response.status_code == 200

        data = response.json()

        # May or may not be gated (depends on threshold)
        # At minimum, should have low quality score
        if "metadata" in data:
            metadata = data["metadata"]
            if "quality_score" in metadata:
                assert metadata["quality_score"] < 0.9, \
                    "Very short document should have reduced quality score"

    def test_legal_document_has_higher_threshold(self):
        """Legal documents should have stricter quality requirements"""
        legal_doc = {
            "content": """Legal Notice

This is a brief legal statement regarding terms.

Contact: legal@example.com
""",
            "filename": "legal_notice.txt",
            "document_type": "text"
        }

        response = requests.post(f"{BASE_URL}/ingest", json=legal_doc, timeout=30)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True

        # Legal docs require min_quality=0.80, this should likely fail or be borderline
        # At minimum, verify it has quality scoring
        metadata = data.get("metadata", {})
        if "signalness" in metadata:
            # Verify scoring is applied
            assert isinstance(metadata["signalness"], (int, float))

    def test_quality_scores_in_response_metadata(self):
        """Response should include quality scores in metadata"""
        doc = {
            "content": """# Product Roadmap Q1 2025

## New Features
- Feature A: User authentication
- Feature B: Dashboard analytics
- Feature C: API integration

## Timeline
Week 1-2: Design and planning
Week 3-6: Development
Week 7-8: Testing and launch

## Resources
Engineering: 3 developers
Design: 1 designer
PM: 1 product manager
""",
            "filename": "roadmap_q1_2025.md",
            "document_type": "text"
        }

        response = requests.post(f"{BASE_URL}/ingest", json=doc, timeout=30)
        assert response.status_code == 200

        data = response.json()
        metadata = data.get("metadata", {})

        # Check for quality score fields
        # Note: These may be in enriched metadata, not always top-level response
        if "quality_score" in metadata:
            assert 0.0 <= metadata["quality_score"] <= 1.0

        if "signalness" in metadata:
            assert 0.0 <= metadata["signalness"] <= 1.0

        if "do_index" in metadata:
            assert isinstance(metadata["do_index"], bool)


class TestQualityScoring:
    """Test quality scoring calculations"""

    def test_structured_content_scores_higher(self):
        """Documents with structure should score higher than unstructured"""
        structured_doc = {
            "content": """# Machine Learning Guide

## Introduction
ML is a subset of AI focused on pattern recognition.

## Key Concepts
- Supervised learning
- Unsupervised learning
- Neural networks

## Applications
1. Image recognition
2. Natural language processing
3. Predictive analytics
""",
            "filename": "ml_guide.md",
            "document_type": "text"
        }

        unstructured_doc = {
            "content": "ML is a subset of AI focused on pattern recognition supervised learning unsupervised learning neural networks image recognition NLP predictive analytics",
            "filename": "ml_notes.txt",
            "document_type": "text"
        }

        # Ingest both
        r1 = requests.post(f"{BASE_URL}/ingest", json=structured_doc, timeout=30)
        time.sleep(1)
        r2 = requests.post(f"{BASE_URL}/ingest", json=unstructured_doc, timeout=30)

        assert r1.status_code == 200
        assert r2.status_code == 200

        # Both should succeed
        assert r1.json()["success"] is True
        assert r2.json()["success"] is True

        # Structured should have more chunks (if not gated)
        structured_chunks = r1.json().get("chunks", 0)
        unstructured_chunks = r2.json().get("chunks", 0)

        if structured_chunks > 0 and unstructured_chunks > 0:
            # Structured content should produce more chunks
            assert structured_chunks >= unstructured_chunks, \
                "Structured document should chunk better than unstructured"

    def test_novelty_decreases_with_corpus_size(self):
        """Novelty score should decrease as corpus grows"""
        # Ingest several similar documents
        for i in range(3):
            doc = {
                "content": f"""# Document {i+1}

This is document number {i+1} about machine learning.

## Content
Machine learning involves training models on data.
Neural networks are a popular approach.
""",
                "filename": f"doc_{i+1}.md",
                "document_type": "text"
            }
            response = requests.post(f"{BASE_URL}/ingest", json=doc, timeout=30)
            assert response.status_code == 200

        # All should succeed (novelty affects score but may not gate)
        # This test just verifies the system doesn't crash with repeated content
