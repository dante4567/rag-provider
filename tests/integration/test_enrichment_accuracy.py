"""
Real enrichment accuracy tests - validates controlled vocabulary compliance

These tests verify:
- LLM enrichment extracts correct entities
- Topics come from controlled vocabulary only
- Entity extraction is accurate (people, places, organizations)
- Enrichment metadata is semantically correct
"""
import pytest
import requests
import time
from typing import Dict, List


BASE_URL = "http://localhost:8001"


class TestControlledVocabularyCompliance:
    """Verify enrichment uses ONLY controlled vocabulary topics"""

    def test_school_document_uses_valid_topics(self):
        """School-related doc should use topics from vocabulary/topics.yaml"""
        content = """
        Enrollment Confirmation - Florianschule Essen

        Dear Parents,

        We are pleased to confirm your child's enrollment for the 2026 school year.
        Please complete the attached registration forms and return them by the end of the month.

        The first parent information day will be held on September 15th.

        Best regards,
        Principal Office
        """

        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "school_enrollment.txt"},
            timeout=30
        )
        assert response.status_code == 200

        result = response.json()
        metadata = result.get("metadata", {})

        # Check for controlled vocabulary topics
        topics = metadata.get("topics", "")
        if topics:
            # Should contain school-related topics from vocabulary
            valid_school_topics = [
                "school/admin/enrollment",
                "school/admin",
                "school/info-day",
                "school/letter"
            ]

            # At least one valid school topic should be present
            has_valid_topic = any(topic in topics for topic in valid_school_topics)
            assert has_valid_topic, f"Expected school topics, got: {topics}"

            # Should NOT contain invented topics
            invalid_topics = ["education/enrollment", "school/registration", "admin/school"]
            has_invalid = any(topic in topics for topic in invalid_topics)
            assert not has_invalid, f"Found invalid (non-vocabulary) topic in: {topics}"

    def test_legal_document_categorization(self):
        """Legal document should be tagged with legal/* topics"""
        content = """
        Court Order - Family Court Essen

        Case Number: 12345/2025

        The court hereby grants the motion for shared custody.
        Both parties shall adhere to the terms outlined in the custody agreement.

        This judgment is final and binding.

        Signed,
        Judge Schmidt
        """

        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "court_order.txt"},
            timeout=30
        )
        assert response.status_code == 200

        result = response.json()
        metadata = result.get("metadata", {})

        topics = metadata.get("topics", "")
        if topics:
            # Should contain legal topics from controlled vocabulary
            valid_legal_topics = [
                "legal/custody",
                "legal/court",
                "legal/judgment",
                "legal/motion",
                "legal/agreement"
            ]

            has_legal_topic = any(topic in topics for topic in valid_legal_topics)
            assert has_legal_topic, f"Expected legal topics, got: {topics}"

    def test_no_invented_topics(self):
        """System should NOT invent topics outside vocabulary"""
        content = """
        Rocket Science and Quantum Computing

        This document discusses advanced rocket propulsion systems
        and their integration with quantum computing algorithms for
        trajectory optimization in deep space missions.
        """

        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "rocket_quantum.txt"},
            timeout=30
        )
        assert response.status_code == 200

        result = response.json()
        metadata = result.get("metadata", {})

        # Invented topics should go to suggested_tags, NOT topics
        topics = metadata.get("topics", "")

        # These topics are NOT in our vocabulary
        invented_topics = [
            "science/rocket",
            "technology/quantum",
            "aerospace",
            "physics/quantum"
        ]

        # Should NOT appear in topics field
        for invented in invented_topics:
            assert invented not in topics, \
                f"Invented topic '{invented}' should not be in topics field"

        # Check if suggested_tags exists (where unknown topics should go)
        suggested_tags = metadata.get("suggested_tags", "")
        # This is where new topics SHOULD appear (if system works correctly)


class TestEntityExtraction:
    """Verify accurate entity extraction"""

    def test_person_extraction_accuracy(self):
        """Should extract people mentioned in document"""
        content = """
        Meeting Minutes

        Attendees: Dr. Maria Schmidt, Prof. Thomas Weber, Jane Johnson

        Dr. Schmidt presented the quarterly results.
        Prof. Weber discussed the new curriculum.
        Jane Johnson took notes.
        """

        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "meeting_minutes.txt"},
            timeout=30
        )
        assert response.status_code == 200

        result = response.json()
        metadata = result.get("metadata", {})

        # Check for people extraction
        people = metadata.get("people_roles", metadata.get("people", ""))

        if people:
            people_lower = people.lower()
            # Should extract at least some of the mentioned people
            mentioned_people = ["schmidt", "weber", "johnson"]
            found = sum(1 for person in mentioned_people if person in people_lower)

            assert found >= 2, f"Should extract at least 2 people, found {found}: {people}"

    def test_location_extraction_accuracy(self):
        """Should extract locations from controlled vocabulary"""
        content = """
        Conference Report

        The annual education conference was held in Berlin on October 15th.
        Participants traveled from Essen, Köln, and München to attend.

        The Florianschule Essen presented their innovative teaching methods.
        """

        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "conference_report.txt"},
            timeout=30
        )
        assert response.status_code == 200

        result = response.json()
        metadata = result.get("metadata", {})

        # Check for places extraction
        places = metadata.get("places", "")

        if places:
            # These cities are in vocabulary/places.yaml
            valid_cities = ["berlin", "essen", "köln", "münchen"]
            found_cities = sum(1 for city in valid_cities if city in places.lower())

            assert found_cities >= 2, \
                f"Should extract at least 2 cities from vocabulary, found {found_cities}: {places}"

            # Institution should also be recognized
            if "florianschule" in places.lower():
                assert True  # Bonus if institution is extracted

    def test_organization_extraction(self):
        """Should extract organizations and institutions"""
        content = """
        Partnership Agreement

        The Jugendamt Essen and Grundschule XY have agreed to collaborate
        on educational support programs for children with special needs.
        """

        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "partnership.txt"},
            timeout=30
        )
        assert response.status_code == 200

        result = response.json()
        metadata = result.get("metadata", {})

        # Check for organizations
        organizations = metadata.get("organizations", "")

        if organizations:
            orgs_lower = organizations.lower()
            # Should extract mentioned institutions
            assert "jugendamt" in orgs_lower or "grundschule" in orgs_lower, \
                f"Should extract organizations, got: {organizations}"


class TestEnrichmentQuality:
    """Test semantic quality of enrichment metadata"""

    def test_title_extraction_quality(self):
        """Title should be semantically meaningful, not generic"""
        content = """
# Annual School Report 2025

## Academic Performance

Student achievement has improved significantly across all grade levels.
Mathematics scores increased by 15% and reading comprehension by 12%.

## Extracurricular Activities

The school introduced new programs in robotics and creative writing.
Student participation increased by 30% compared to last year.
"""

        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "annual_report_2025.md"},
            timeout=30
        )
        assert response.status_code == 200

        result = response.json()
        metadata = result.get("metadata", {})

        title = metadata.get("title", "")

        # Title should NOT be generic
        assert title != "Untitled", "Should extract meaningful title"
        assert title != "Document", "Should not use generic 'Document'"
        assert title != "", "Title should not be empty"

        # Should be related to content
        title_lower = title.lower()
        relevant_terms = ["school", "report", "2025", "annual"]
        has_relevant = any(term in title_lower for term in relevant_terms)

        assert has_relevant, f"Title should be relevant to content, got: {title}"

    def test_abstract_quality(self):
        """Abstract should summarize key content"""
        content = """
        Enrollment Process Changes for 2026

        Starting next year, the school enrollment process will be fully digitalized.
        Parents can submit applications online through the new portal.

        Key deadlines:
        - Application opens: January 15, 2026
        - Application closes: March 1, 2026
        - Acceptance letters: April 15, 2026

        Please ensure all required documents are uploaded before the deadline.
        """

        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "enrollment_changes.txt"},
            timeout=30
        )
        assert response.status_code == 200

        result = response.json()
        metadata = result.get("metadata", {})

        abstract = metadata.get("abstract", "")

        if abstract:
            abstract_lower = abstract.lower()

            # Abstract should mention key concepts
            key_concepts = ["enrollment", "digital", "2026", "application"]
            mentions = sum(1 for concept in key_concepts if concept in abstract_lower)

            assert mentions >= 2, \
                f"Abstract should mention key concepts, found {mentions}/4: {abstract[:100]}"

            # Should be concise (not just copying full content)
            assert len(abstract) < len(content) * 0.8, \
                "Abstract should be shorter than original content"

    def test_date_extraction(self):
        """Should extract dates mentioned in content"""
        content = """
        Important Dates for School Year 2025/2026

        First day of school: September 1, 2025
        Fall break: October 15-20, 2025
        Winter holidays: December 20, 2025 - January 6, 2026
        Spring break: April 10-17, 2026
        Last day of school: July 15, 2026
        """

        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "school_calendar.txt"},
            timeout=30
        )
        assert response.status_code == 200

        result = response.json()
        metadata = result.get("metadata", {})

        dates = metadata.get("dates", "")

        if dates:
            # Should extract some of the mentioned dates
            date_indicators = ["2025", "2026", "september", "july"]
            found = sum(1 for indicator in date_indicators if indicator in dates.lower())

            assert found >= 2, f"Should extract dates from content, got: {dates}"


class TestEnrichmentVersioning:
    """Verify enrichment system version tracking"""

    def test_enrichment_version_present(self):
        """All enriched docs should have version metadata"""
        import time
        unique_id = str(int(time.time() * 1000))
        content = f"""This is a test document {unique_id} for verifying enrichment version tracking.

The enrichment system should add version metadata to all processed documents.
This helps track which version of enrichment was used for each document.
Version 2.0 includes controlled vocabulary and improved entity extraction."""

        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": f"version_test_{unique_id}.txt"},
            timeout=30
        )
        assert response.status_code == 200

        result = response.json()
        metadata = result.get("metadata", {})

        # Debug: print what we got
        print(f"\n=== DEBUG ===")
        print(f"Response success: {result.get('success')}")
        print(f"Chunks: {result.get('chunks')}")
        print(f"Metadata keys: {list(metadata.keys())[:15]}")
        print(f"Enrichment version: '{metadata.get('enrichment_version', 'NOT_FOUND')}'")
        print(f"Gated: {metadata.get('gated', False)}")
        print(f"=============\n")

        # Should have enrichment version
        version = metadata.get("enrichment_version", "")

        # Version should exist and be current (2.0+)
        assert version != "", f"Enrichment version should be present. Got metadata keys: {list(metadata.keys())[:10]}"

        if version:
            # Should be version 2.0 or higher
            version_num = float(version) if version.replace(".", "").isdigit() else 0
            assert version_num >= 2.0, f"Should use enrichment v2.0+, got: {version}"


class TestProjectMatching:
    """Test automatic project tag assignment"""

    def test_temporal_project_matching(self):
        """Documents with dates should match appropriate project tags"""
        content = """
        School Planning for 2026

        This document outlines our preparations for the 2026 school year.
        Enrollment planning and curriculum updates for next year.
        """

        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "planning_2026.txt"},
            timeout=30
        )
        assert response.status_code == 200

        result = response.json()
        metadata = result.get("metadata", {})

        # Check if project tags are assigned
        projects = metadata.get("projects", "")

        # If project matching works, should include "school-2026" or similar
        if projects and "2026" in content:
            # System should recognize 2026 timeframe
            assert "2026" in projects or "school-2026" in projects, \
                f"Should match project tag for 2026, got: {projects}"
