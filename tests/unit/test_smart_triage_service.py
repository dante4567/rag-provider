"""
Unit tests for SmartTriageService

Tests smart document triage including:
- Duplicate detection via fingerprinting
- Entity alias resolution
- Document categorization (junk/duplicate/actionable/archival)
- Event extraction
- Knowledge base updates
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from src.services.smart_triage_service import (
    SmartTriageService,
    DocumentFingerprint,
    TriageDecision,
    EntityAlias
)


# =============================================================================
# SmartTriageService Tests
# =============================================================================

class TestSmartTriageService:
    """Test the SmartTriageService class"""

    @pytest.fixture
    def service(self):
        """Create SmartTriageService instance"""
        return SmartTriageService(collection=None)

    @pytest.fixture
    def service_with_mock_collection(self):
        """Create service with mock collection"""
        mock_collection = Mock()
        return SmartTriageService(collection=mock_collection)

    def test_init(self, service):
        """Test SmartTriageService initialization"""
        assert service.personal_kb is not None
        assert "people" in service.personal_kb
        assert "organizations" in service.personal_kb
        assert service.fingerprint_cache == {}

    def test_generate_fingerprint_basic(self, service):
        """Test fingerprint generation"""
        content = "This is a test document with some content for fingerprinting"
        metadata = {"title": "Test Document", "domain": "test", "created_at": "2025-10-06"}
        entities = {"people": ["Alice"], "organizations": ["ACME"]}

        fingerprint = service.generate_fingerprint(content, metadata, entities)

        # Check all fingerprint components exist
        assert fingerprint.content_hash is not None
        assert len(fingerprint.content_hash) == 64  # SHA-256
        assert fingerprint.fuzzy_hash is not None
        assert fingerprint.metadata_hash is not None
        assert fingerprint.title_normalized is not None
        assert fingerprint.word_count > 0

    def test_generate_fingerprint_deterministic(self, service):
        """Test that same content produces same fingerprint"""
        content = "Same content for testing"
        metadata = {"title": "Same Title"}
        entities = {}

        fp1 = service.generate_fingerprint(content, metadata, entities)
        fp2 = service.generate_fingerprint(content, metadata, entities)

        assert fp1.content_hash == fp2.content_hash
        assert fp1.fuzzy_hash == fp2.fuzzy_hash
        assert fp1.metadata_hash == fp2.metadata_hash

    def test_generate_fingerprint_different_content(self, service):
        """Test that different content produces different fingerprints"""
        content1 = "Content one"
        content2 = "Content two"
        metadata = {"title": "Test"}
        entities = {}

        fp1 = service.generate_fingerprint(content1, metadata, entities)
        fp2 = service.generate_fingerprint(content2, metadata, entities)

        assert fp1.content_hash != fp2.content_hash

    def test_generate_fingerprint_title_normalization(self, service):
        """Test title normalization in fingerprint"""
        content = "Content"
        metadata1 = {"title": "Test-Document (2025)"}
        metadata2 = {"title": "Test Document 2025"}
        entities = {}

        fp1 = service.generate_fingerprint(content, metadata1, entities)
        fp2 = service.generate_fingerprint(content, metadata2, entities)

        # Normalized titles should be similar (only alphanumeric)
        assert fp1.title_normalized == "testdocument2025"
        assert fp2.title_normalized == "testdocument2025"

    def test_generate_fingerprint_entity_signature(self, service):
        """Test entity signature generation"""
        content = "Content"
        metadata = {"title": "Test"}
        entities1 = {"people": ["Alice", "Bob"]}
        entities2 = {"people": ["Alice", "Bob"]}
        entities3 = {"people": ["Alice", "Charlie"]}

        fp1 = service.generate_fingerprint(content, metadata, entities1)
        fp2 = service.generate_fingerprint(content, metadata, entities2)
        fp3 = service.generate_fingerprint(content, metadata, entities3)

        # Same entities = same signature
        assert fp1.entity_signature == fp2.entity_signature

        # Different entities = different signature
        assert fp1.entity_signature != fp3.entity_signature

    def test_find_duplicates_no_collection(self, service):
        """Test duplicate finding with no collection returns empty"""
        fingerprint = DocumentFingerprint(
            content_hash="abc123",
            fuzzy_hash="def456",
            metadata_hash="ghi789",
            title_normalized="test",
            first_100_chars="content",
            word_count=100,
            entity_signature="ent123"
        )

        duplicates = service.find_duplicates(fingerprint)
        assert duplicates == []

    def test_find_duplicates_exact_match(self, service_with_mock_collection):
        """Test finding exact duplicate by content hash"""
        service = service_with_mock_collection

        # Mock exact match
        service.collection.get.return_value = {
            'ids': ['doc_123'],
            'metadatas': [{'content_hash': 'abc123'}]
        }

        fingerprint = DocumentFingerprint(
            content_hash="abc123",
            fuzzy_hash="def456",
            metadata_hash="ghi789",
            title_normalized="test",
            first_100_chars="content",
            word_count=100,
            entity_signature="ent123"
        )

        duplicates = service.find_duplicates(fingerprint)

        # Should find exact match
        assert len(duplicates) > 0
        assert duplicates[0][0] == 'doc_123'
        assert duplicates[0][1] == 1.0  # 100% match
        assert duplicates[0][2] == 'exact_content_hash'

    def test_resolve_entity_aliases_basic(self, service):
        """Test entity alias resolution"""
        entities = {
            "people": ["Anika Kreuzer"],  # Known alias
            "organizations": ["ACME"],
            "locations": ["Berlin"]
        }

        resolved = service.resolve_entity_aliases(entities)

        # Should resolve alias to canonical name
        assert "people" in resolved
        people = resolved["people"]
        assert len(people) > 0

        # Check if resolved to Anika Teckentrup
        person = people[0]
        assert person["name"] == "Anika Teckentrup"
        assert person["original"] == "Anika Kreuzer"
        assert person["resolved"] is True

    def test_resolve_entity_aliases_no_alias(self, service):
        """Test entity resolution for unknown person"""
        entities = {
            "people": ["Unknown Person"],
            "organizations": [],
            "locations": []
        }

        resolved = service.resolve_entity_aliases(entities)

        # Should keep original name
        person = resolved["people"][0]
        assert person["name"] == "Unknown Person"
        assert person["resolved"] is False

    def test_triage_document_duplicate(self, service_with_mock_collection):
        """Test triage detects duplicates"""
        service = service_with_mock_collection

        # Mock duplicate found
        service.collection.get.return_value = {
            'ids': ['existing_doc'],
            'metadatas': [{}]
        }

        content = "Duplicate content"
        metadata = {"title": "Duplicate"}
        entities = {}
        fingerprint = service.generate_fingerprint(content, metadata, entities)

        decision = service.triage_document(content, metadata, entities, fingerprint)

        assert decision.category == "duplicate"
        assert decision.confidence >= 0.95
        assert len(decision.related_documents) > 0

    def test_triage_document_junk_detection(self, service):
        """Test junk/spam detection"""
        content = """
        SPECIAL OFFER! Click here to unsubscribe from this amazing advertisement.
        Promotional content with special offers!
        """
        metadata = {"title": "Spam"}
        entities = {}
        fingerprint = service.generate_fingerprint(content, metadata, entities)

        decision = service.triage_document(content, metadata, entities, fingerprint)

        assert decision.category == "junk"
        assert decision.confidence > 0.5

    def test_triage_document_wedding_detection(self, service):
        """Test wedding/marriage document detection"""
        content = """
        Einladung zur Hochzeit von Anika und Max
        Datum: 15.06.2025
        Ort: Köln
        """
        metadata = {"title": "Wedding Invitation"}
        entities = {"people": ["Anika Kreuzer"]}
        fingerprint = service.generate_fingerprint(content, metadata, entities)

        decision = service.triage_document(content, metadata, entities, fingerprint)

        assert "personal" in decision.category or "wedding" in str(decision.reasoning).lower()
        assert len(decision.actions_suggested) > 0

    def test_triage_document_invoice_detection(self, service):
        """Test invoice/bill detection"""
        content = """
        Rechnung Nr. 12345
        Betrag: €250,00
        Zahlbar bis: 31.10.2025
        """
        metadata = {"title": "Invoice"}
        entities = {}
        fingerprint = service.generate_fingerprint(content, metadata, entities)

        decision = service.triage_document(content, metadata, entities, fingerprint)

        assert "financial" in decision.category or "invoice" in str(decision.reasoning).lower()
        assert decision.confidence > 0.7

    def test_triage_document_legal(self, service):
        """Test legal document categorization"""
        content = "Legal contract content"
        metadata = {"title": "Contract", "domain": "legal"}
        entities = {}
        fingerprint = service.generate_fingerprint(content, metadata, entities)

        decision = service.triage_document(content, metadata, entities, fingerprint)

        assert "legal" in decision.category
        assert "important" in str(decision.reasoning).lower() or "archive" in str(decision.actions_suggested).lower()

    def test_triage_document_health(self, service):
        """Test health document categorization"""
        content = "Medical information"
        metadata = {"title": "Health Record", "domain": "health"}
        entities = {}
        fingerprint = service.generate_fingerprint(content, metadata, entities)

        decision = service.triage_document(content, metadata, entities, fingerprint)

        assert "health" in decision.category or "personal" in decision.category

    def test_extract_upcoming_events_basic(self, service):
        """Test event extraction from content"""
        content = """
        Meeting scheduled for 15.12.2025 at the office.
        Another event on 2025-12-20.
        """
        metadata = {}

        events = service._extract_upcoming_events(content, metadata)

        assert len(events) > 0
        # Should find dates in the future
        assert any("2025" in event["date"] for event in events)

    def test_extract_upcoming_events_filters_old_dates(self, service):
        """Test that old dates are filtered out"""
        # Date from 2 years ago
        old_date = (datetime.now() - timedelta(days=365*2)).strftime("%d.%m.%Y")
        content = f"Old event on {old_date}"
        metadata = {}

        events = service._extract_upcoming_events(content, metadata)

        # Should not include dates older than 30 days
        for event in events:
            assert not event["date"] == old_date

    def test_extract_upcoming_events_includes_context(self, service):
        """Test that event extraction includes context"""
        content = "Important meeting on 15.12.2025 with the client about the new project."
        metadata = {}

        events = service._extract_upcoming_events(content, metadata)

        if events:
            # Context should include surrounding text
            assert "description" in events[0]
            assert len(events[0]["description"]) > 0

    def test_generate_triage_summary_basic(self, service):
        """Test triage summary generation"""
        decision = TriageDecision(
            category="archival",
            confidence=0.85,
            reasoning=["General document", "No special attributes"],
            actions_suggested=["Archive for reference"],
            related_documents=[],
            knowledge_updates=[]
        )

        summary = service.generate_triage_summary(decision)

        assert "ARCHIVAL" in summary
        assert "85%" in summary or "0.85" in summary
        assert "Archive" in summary

    def test_generate_triage_summary_with_kb_updates(self, service):
        """Test summary includes knowledge base updates"""
        decision = TriageDecision(
            category="personal_actionable",
            confidence=0.9,
            reasoning=["Wedding detected"],
            actions_suggested=["Update addressbook"],
            related_documents=[],
            knowledge_updates=[
                {"action": "Update marriage date for Person X"}
            ]
        )

        summary = service.generate_triage_summary(decision)

        assert "Knowledge Base Updates" in summary
        assert "Update marriage date" in summary


# =============================================================================
# DocumentFingerprint Tests
# =============================================================================

class TestDocumentFingerprint:
    """Test DocumentFingerprint dataclass"""

    def test_fingerprint_creation(self):
        """Test creating fingerprint object"""
        fp = DocumentFingerprint(
            content_hash="hash123",
            fuzzy_hash="fuzzy456",
            metadata_hash="meta789",
            title_normalized="testtitle",
            first_100_chars="content preview",
            word_count=150,
            entity_signature="ent123"
        )

        assert fp.content_hash == "hash123"
        assert fp.word_count == 150
        assert fp.entity_signature == "ent123"


# =============================================================================
# TriageDecision Tests
# =============================================================================

class TestTriageDecision:
    """Test TriageDecision dataclass"""

    def test_decision_creation(self):
        """Test creating triage decision"""
        decision = TriageDecision(
            category="junk",
            confidence=0.9,
            reasoning=["Contains spam keywords"],
            actions_suggested=["Delete"],
            related_documents=[],
            knowledge_updates=[]
        )

        assert decision.category == "junk"
        assert decision.confidence == 0.9
        assert len(decision.reasoning) == 1


# =============================================================================
# Integration-style Tests
# =============================================================================

class TestSmartTriageIntegration:
    """Integration tests for triage workflow"""

    def test_full_triage_workflow(self):
        """Test complete triage workflow"""
        service = SmartTriageService(collection=None)

        content = "Test document content for triage"
        metadata = {"title": "Test Doc", "domain": "general"}
        entities = {"people": [], "organizations": []}

        # Generate fingerprint
        fingerprint = service.generate_fingerprint(content, metadata, entities)

        # Triage document
        decision = service.triage_document(content, metadata, entities, fingerprint)

        # Generate summary
        summary = service.generate_triage_summary(decision)

        # Should complete without errors
        assert decision.category is not None
        assert 0 <= decision.confidence <= 1
        assert len(summary) > 0

    def test_personal_kb_integration(self):
        """Test that personal KB is used for alias resolution"""
        service = SmartTriageService(collection=None)

        # Use known alias from KB
        entities = {"people": ["Anika Kreuzer"]}

        resolved = service.resolve_entity_aliases(entities)

        # Should resolve to canonical name
        assert resolved["people"][0]["name"] == "Anika Teckentrup"
