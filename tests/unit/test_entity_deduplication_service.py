"""
Unit tests for EntityDeduplicationService

Tests entity matching, normalization, and cross-referencing:
- Name normalization (titles, punctuation, case)
- Similarity computation (exact, substring, fuzzy)
- Entity deduplication (same person, different mentions)
- Manual merging
- Statistics and export
"""
import pytest
from src.services.entity_deduplication_service import (
    EntityDeduplicationService,
    Entity,
    get_entity_deduplication_service
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def service():
    """Create fresh EntityDeduplicationService instance"""
    return EntityDeduplicationService(similarity_threshold=0.85)


@pytest.fixture
def populated_service():
    """Service with test data already added"""
    service = EntityDeduplicationService(similarity_threshold=0.85)

    # Add some test entities
    service.add_entity("Dr. Weber", "person", "doc1")
    service.add_entity("Thomas Weber", "person", "doc2")
    service.add_entity("Schmidt", "person", "doc3")
    service.add_entity("Rechtsanwalt Schmidt", "person", "doc4")
    service.add_entity("Meyer & Partner", "organization", "doc5")

    return service


# =============================================================================
# Name Normalization Tests
# =============================================================================

class TestNameNormalization:
    """Test name normalization logic"""

    def test_normalize_simple_name(self, service):
        """Test normalization of simple name"""
        normalized, titles, roles = service.normalize_name("Thomas Weber", "person")
        assert normalized == "thomas weber"
        assert len(titles) == 0
        assert len(roles) == 0

    def test_normalize_with_title(self, service):
        """Test extraction of academic titles"""
        normalized, titles, roles = service.normalize_name("Dr. Weber", "person", extract_titles=True)
        assert "dr" in normalized or normalized == "weber"  # Title may be removed
        assert "dr" in titles or "dr." in titles

    def test_normalize_multiple_titles(self, service):
        """Test extraction of multiple titles"""
        normalized, titles, roles = service.normalize_name("Prof. Dr. Weber", "person", extract_titles=True)
        assert "prof" in titles or "prof." in titles
        assert "dr" in titles or "dr." in titles

    def test_normalize_with_role(self, service):
        """Test normalization with professional role"""
        normalized, titles, roles = service.normalize_name("Rechtsanwalt Schmidt", "person", extract_titles=True)
        assert "schmidt" in normalized
        # Rechtsanwalt is a title, gets extracted and removed
        assert "rechtsanwalt" in titles or "rechtsanwalt" in normalized

    def test_normalize_removes_punctuation(self, service):
        """Test that punctuation is removed"""
        normalized, _, _ = service.normalize_name("Weber, Thomas", "person")
        assert "," not in normalized
        assert "weber" in normalized
        assert "thomas" in normalized

    def test_normalize_organization(self, service):
        """Test normalization of organization names"""
        normalized, _, _ = service.normalize_name("Meyer & Partner GmbH", "organization")
        assert "meyer" in normalized
        assert "partner" in normalized

    def test_normalize_empty_name(self, service):
        """Test normalization of empty string"""
        normalized, titles, roles = service.normalize_name("", "person")
        assert normalized == ""
        assert len(titles) == 0
        assert len(roles) == 0

    def test_normalize_whitespace_only(self, service):
        """Test normalization of whitespace"""
        normalized, titles, roles = service.normalize_name("   ", "person")
        assert normalized == ""


# =============================================================================
# Similarity Computation Tests
# =============================================================================

class TestSimilarityComputation:
    """Test similarity scoring between names"""

    def test_exact_match(self, service):
        """Test exact match returns 1.0"""
        score = service.compute_similarity("thomas weber", "thomas weber")
        assert score == 1.0

    def test_substring_match(self, service):
        """Test substring matching (e.g., 'Weber' vs 'Thomas Weber')"""
        score = service.compute_similarity("weber", "thomas weber")
        assert score >= 0.8  # High score for substring match

    def test_partial_match(self, service):
        """Test partial similarity"""
        score = service.compute_similarity("thomas weber", "thomas meyer")
        assert 0.5 < score < 0.9  # Partial match

    def test_no_match(self, service):
        """Test completely different names"""
        score = service.compute_similarity("weber", "schmidt")
        assert score < 0.5

    def test_token_overlap(self, service):
        """Test token-based matching"""
        score = service.compute_similarity("dr thomas weber", "thomas weber prof")
        assert score >= 0.7  # Good overlap

    def test_case_insensitive(self, service):
        """Test that comparison is case-insensitive"""
        # Case differences after normalization to lowercase
        # Names normalized BEFORE similarity computation (done by caller)
        # So test already-normalized names
        norm1, _, _ = service.normalize_name("weber", "person")
        norm2, _, _ = service.normalize_name("Weber", "person")
        score = service.compute_similarity(norm1, norm2)
        assert score == 1.0  # Exact match after normalization


# =============================================================================
# Entity Addition and Deduplication Tests
# =============================================================================

class TestEntityDeduplication:
    """Test entity deduplication logic"""

    def test_add_first_entity(self, service):
        """Test adding first entity"""
        entity = service.add_entity("Dr. Weber", "person", "doc1")
        assert entity is not None
        assert entity.canonical_name == "Dr. Weber"
        assert entity.mentions_count == 1
        assert "doc1" in entity.source_docs

    def test_add_duplicate_exact(self, service):
        """Test adding exact duplicate"""
        entity1 = service.add_entity("Dr. Weber", "person", "doc1")
        entity2 = service.add_entity("Dr. Weber", "person", "doc2")

        assert entity1 is entity2  # Same entity object
        assert entity2.mentions_count == 2
        assert len(entity2.source_docs) == 2

    def test_deduplicate_similar_names(self, service):
        """Test deduplication of similar names"""
        entity1 = service.add_entity("Dr. Weber", "person", "doc1")
        entity2 = service.add_entity("Thomas Weber", "person", "doc2")

        # Should be deduplicated (same canonical)
        canonical1 = service.resolve_name("Dr. Weber")
        canonical2 = service.resolve_name("Thomas Weber")

        assert canonical1 == canonical2  # Both resolve to same canonical

    def test_deduplicate_with_title_variations(self, service):
        """Test deduplication across title variations"""
        service.add_entity("Weber", "person", "doc1")
        service.add_entity("Dr. Weber", "person", "doc2")
        service.add_entity("Prof. Dr. Weber", "person", "doc3")

        # All should be deduplicated
        canonical1 = service.resolve_name("Weber")
        canonical2 = service.resolve_name("Dr. Weber")
        canonical3 = service.resolve_name("Prof. Dr. Weber")

        assert canonical1 == canonical2 == canonical3

    def test_different_entities_not_merged(self, service):
        """Test that different entities are not merged"""
        entity1 = service.add_entity("Weber", "person", "doc1")
        entity2 = service.add_entity("Schmidt", "person", "doc2")

        assert entity1.canonical_name != entity2.canonical_name
        assert len(service.entities) == 2

    def test_force_new_entity(self, service):
        """Test force_new parameter"""
        entity1 = service.add_entity("Dr. Weber", "person", "doc1")
        entity2 = service.add_entity("Thomas Weber", "person", "doc2", force_new=True)

        # Should create separate entities
        assert entity1.canonical_name != entity2.canonical_name
        assert len(service.entities) == 2

    def test_entity_type_separation(self, service):
        """Test that different entity types are kept separate"""
        person = service.add_entity("Weber", "person", "doc1")
        org = service.add_entity("Weber GmbH", "organization", "doc2")

        # Should be different entities
        assert person.entity_type == "person"
        assert org.entity_type == "organization"
        assert person.canonical_name != org.canonical_name


# =============================================================================
# Entity Resolution Tests
# =============================================================================

class TestEntityResolution:
    """Test entity lookup and resolution"""

    def test_get_entity_by_canonical(self, populated_service):
        """Test retrieving entity by canonical name"""
        entity = populated_service.get_entity("Dr. Weber")
        assert entity is not None
        assert entity.canonical_name == "Dr. Weber"

    def test_get_entity_by_alias(self, populated_service):
        """Test retrieving entity by alias"""
        # Add entity with alias
        populated_service.add_entity("Prof. Weber", "person", "doc10")

        # Should resolve through alias
        entity = populated_service.get_entity("Prof. Weber")
        assert entity is not None

    def test_get_entity_not_found(self, service):
        """Test getting non-existent entity"""
        entity = service.get_entity("Unknown Person")
        assert entity is None

    def test_resolve_name_known(self, populated_service):
        """Test resolving known name to canonical"""
        canonical = populated_service.resolve_name("Dr. Weber")
        assert canonical == "Dr. Weber"

    def test_resolve_name_unknown(self, service):
        """Test resolving unknown name returns original"""
        canonical = service.resolve_name("Unknown Person")
        assert canonical == "Unknown Person"


# =============================================================================
# Manual Merging Tests
# =============================================================================

class TestManualMerging:
    """Test manual entity merging"""

    def test_merge_two_entities(self, service):
        """Test manually merging two entities"""
        entity1 = service.add_entity("Weber", "person", "doc1", force_new=True)
        entity2 = service.add_entity("Thomas Weber", "person", "doc2", force_new=True)

        # Initially separate
        assert len(service.entities) == 2

        # Merge manually
        merged = service.merge_entities("Weber", "Thomas Weber", preferred_canonical="Thomas Weber")

        assert merged is not None
        assert merged.canonical_name == "Thomas Weber"
        assert "Weber" in merged.aliases
        assert "Thomas Weber" in merged.aliases
        assert len(service.entities) == 1  # Only one entity now

    def test_merge_accumulates_data(self, service):
        """Test that merging accumulates mentions, docs, etc."""
        service.add_entity("Dr. Weber", "person", "doc1", force_new=True)
        service.add_entity("Prof. Weber", "person", "doc2", force_new=True)

        merged = service.merge_entities("Dr. Weber", "Prof. Weber")

        assert merged.mentions_count == 2
        assert len(merged.source_docs) == 2
        assert "doc1" in merged.source_docs
        assert "doc2" in merged.source_docs

    def test_merge_nonexistent_entity(self, service):
        """Test merging with non-existent entity"""
        service.add_entity("Weber", "person", "doc1")

        merged = service.merge_entities("Weber", "Unknown Person")
        assert merged is None

    def test_merge_same_entity(self, service):
        """Test merging entity with itself"""
        entity = service.add_entity("Dr. Weber", "person", "doc1")
        service.add_entity("Thomas Weber", "person", "doc2")  # Gets deduplicated

        # Try to merge already-merged entities
        merged = service.merge_entities("Dr. Weber", "Thomas Weber")

        # Should return the entity (already merged)
        assert merged is entity


# =============================================================================
# Retrieval and Statistics Tests
# =============================================================================

class TestRetrievalAndStats:
    """Test entity retrieval and statistics"""

    def test_get_all_entities(self, populated_service):
        """Test retrieving all entities"""
        entities = populated_service.get_all_entities()
        assert len(entities) >= 3  # At least Weber, Schmidt, Meyer & Partner

    def test_get_entities_by_type(self, populated_service):
        """Test filtering entities by type"""
        people = populated_service.get_all_entities(entity_type="person")
        orgs = populated_service.get_all_entities(entity_type="organization")

        assert all(e.entity_type == "person" for e in people)
        assert all(e.entity_type == "organization" for e in orgs)
        assert len(orgs) >= 1  # Meyer & Partner

    def test_entities_sorted_by_mentions(self, service):
        """Test that entities are sorted by mention count"""
        service.add_entity("Popular Person", "person", "doc1")
        service.add_entity("Popular Person", "person", "doc2")
        service.add_entity("Popular Person", "person", "doc3")
        service.add_entity("Rare Person", "person", "doc4")

        entities = service.get_all_entities()

        # First entity should have most mentions
        assert entities[0].mentions_count >= entities[-1].mentions_count

    def test_get_statistics(self, populated_service):
        """Test statistics generation"""
        stats = populated_service.get_statistics()

        assert 'total_entities' in stats
        assert 'total_aliases' in stats
        assert 'avg_aliases_per_entity' in stats
        assert 'entities_by_type' in stats
        assert 'deduplication_rate' in stats

        assert stats['total_entities'] > 0
        assert stats['total_aliases'] >= stats['total_entities']

    def test_export_entity_mappings(self, populated_service):
        """Test exporting entity mappings"""
        mappings = populated_service.export_entity_mappings()

        assert isinstance(mappings, dict)

        # Each mapping should have canonical -> list of aliases
        for canonical, aliases in mappings.items():
            assert isinstance(aliases, list)
            assert len(aliases) > 1  # Only entities with multiple aliases


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_name(self, service):
        """Test adding entity with empty name"""
        entity = service.add_entity("", "person", "doc1")
        assert entity is None

    def test_whitespace_only_name(self, service):
        """Test adding entity with whitespace-only name"""
        entity = service.add_entity("   ", "person", "doc1")
        assert entity is None

    def test_very_long_name(self, service):
        """Test handling very long names"""
        long_name = "Dr. Prof. " + " ".join([f"Name{i}" for i in range(50)])
        entity = service.add_entity(long_name, "person", "doc1")
        assert entity is not None
        assert entity.canonical_name == long_name

    def test_special_characters(self, service):
        """Test names with special characters"""
        entity = service.add_entity("O'Brien", "person", "doc1")
        assert entity is not None

        entity2 = service.add_entity("Müller-Schmidt", "person", "doc2")
        assert entity2 is not None

    def test_numbers_in_name(self, service):
        """Test names with numbers"""
        entity = service.add_entity("Weber & Partner 2024", "organization", "doc1")
        assert entity is not None

    def test_unicode_names(self, service):
        """Test Unicode names"""
        entity = service.add_entity("Владимир Петров", "person", "doc1")
        assert entity is not None

        entity2 = service.add_entity("李明", "person", "doc2")
        assert entity2 is not None


# =============================================================================
# Singleton Pattern Tests
# =============================================================================

class TestSingletonPattern:
    """Test singleton pattern for service"""

    def test_get_singleton(self):
        """Test that singleton returns same instance"""
        # Reset singleton
        import src.services.entity_deduplication_service as module
        module._entity_dedup_service = None

        service1 = get_entity_deduplication_service()
        service2 = get_entity_deduplication_service()

        assert service1 is service2

    def test_singleton_threshold_parameter(self):
        """Test that threshold parameter is used on first call"""
        import src.services.entity_deduplication_service as module
        module._entity_dedup_service = None

        service = get_entity_deduplication_service(similarity_threshold=0.9)
        assert service.similarity_threshold == 0.9


# =============================================================================
# Integration-Like Tests
# =============================================================================

class TestRealWorldScenarios:
    """Test realistic entity deduplication scenarios"""

    def test_german_legal_names(self, service):
        """Test German legal professionals"""
        # Various mentions of same lawyer
        service.add_entity("Rechtsanwalt Schmidt", "person", "doc1")
        service.add_entity("RA Schmidt", "person", "doc2")
        service.add_entity("Herr Schmidt", "person", "doc3")
        service.add_entity("Schmidt", "person", "doc4")

        # Should mostly deduplicate
        canonical = service.resolve_name("Rechtsanwalt Schmidt")
        assert service.resolve_name("RA Schmidt") == canonical
        assert service.resolve_name("Schmidt") == canonical

    def test_academic_titles(self, service):
        """Test academic title variations"""
        service.add_entity("Prof. Dr. Weber", "person", "doc1")
        service.add_entity("Dr. Weber", "person", "doc2")
        service.add_entity("Professor Weber", "person", "doc3")
        service.add_entity("Weber", "person", "doc4")

        # Should deduplicate
        canonical = service.resolve_name("Prof. Dr. Weber")
        assert service.resolve_name("Dr. Weber") == canonical

    def test_organization_variations(self, service):
        """Test organization name variations"""
        service.add_entity("Meyer & Partner", "organization", "doc1")
        service.add_entity("Meyer und Partner", "organization", "doc2")
        service.add_entity("Meyer & Partner GmbH", "organization", "doc3")

        # Should deduplicate
        canonical = service.resolve_name("Meyer & Partner")
        assert service.resolve_name("Meyer und Partner") == canonical

    def test_mixed_document_sources(self, service):
        """Test tracking entity across multiple documents"""
        service.add_entity("Dr. Weber", "person", "email_001")
        service.add_entity("Thomas Weber", "person", "court_doc_042")
        service.add_entity("Prof. Weber", "person", "letter_2024_03")

        entity = service.get_entity("Dr. Weber")
        assert len(entity.source_docs) == 3
        assert "email_001" in entity.source_docs
        assert "court_doc_042" in entity.source_docs
