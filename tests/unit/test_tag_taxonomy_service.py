"""
Unit tests for TagTaxonomyService

Tests evolving tag hierarchy management including:
- Tag cache refresh
- Tag suggestions
- Similarity detection
- Deduplication
- Statistics generation
"""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta
from src.services.tag_taxonomy_service import TagTaxonomyService


# =============================================================================
# TagTaxonomyService Tests
# =============================================================================

class TestTagTaxonomyService:
    """Test the TagTaxonomyService class"""

    @pytest.fixture
    def mock_collection(self):
        """Create mock ChromaDB collection"""
        mock = Mock()
        # Mock data with tags
        mock.get.return_value = {
            "ids": ["doc1", "doc2", "doc3"],
            "metadatas": [
                {"tags": "tech/ai/ml, literature, cont/in/read", "domain": "technology"},
                {"tags": "tech/ai, psychology/cognitive, permanent", "domain": "psychology"},
                {"tags": "tech/ai/ml, project/active", "domain": "technology"}
            ]
        }
        return mock

    @pytest.fixture
    def service(self):
        """Create TagTaxonomyService instance"""
        return TagTaxonomyService()

    @pytest.fixture
    def service_with_collection(self, mock_collection):
        """Create service with mock collection"""
        return TagTaxonomyService(collection=mock_collection)

    def test_init(self, service):
        """Test TagTaxonomyService initialization"""
        assert service.collection is None
        assert service.tag_cache == {}
        assert service.last_refresh is None
        assert 'workflow' in service.base_taxonomy
        assert 'type' in service.base_taxonomy

    def test_init_with_collection(self, service_with_collection, mock_collection):
        """Test initialization with collection"""
        assert service_with_collection.collection == mock_collection

    @pytest.mark.asyncio
    async def test_refresh_tag_cache(self, service_with_collection, mock_collection):
        """Test refreshing tag cache from collection"""
        await service_with_collection.refresh_tag_cache()

        # Cache should be populated
        assert 'frequency' in service_with_collection.tag_cache
        assert 'co_occurrence' in service_with_collection.tag_cache
        assert 'by_domain' in service_with_collection.tag_cache
        assert 'total_docs' in service_with_collection.tag_cache
        assert 'unique_tags' in service_with_collection.tag_cache

        # Check frequency counts
        freq = service_with_collection.tag_cache['frequency']
        assert 'tech/ai/ml' in freq
        assert freq['tech/ai/ml'] == 2  # Appears twice
        assert 'literature' in freq
        assert freq['literature'] == 1

        # Check domain grouping
        domains = service_with_collection.tag_cache['by_domain']
        assert 'technology' in domains
        assert 'tech/ai/ml' in domains['technology']

    @pytest.mark.asyncio
    async def test_refresh_tag_cache_no_collection(self, service):
        """Test refresh when no collection is set"""
        # Should not crash
        await service.refresh_tag_cache()
        assert service.tag_cache == {}

    @pytest.mark.asyncio
    async def test_refresh_tag_cache_throttling(self, service_with_collection):
        """Test that cache refresh is throttled"""
        # First refresh
        await service_with_collection.refresh_tag_cache()
        first_refresh_time = service_with_collection.last_refresh

        # Immediate second refresh should be skipped
        await service_with_collection.refresh_tag_cache()
        assert service_with_collection.last_refresh == first_refresh_time

        # Force refresh should work
        await service_with_collection.refresh_tag_cache(force=True)
        assert service_with_collection.last_refresh > first_refresh_time

    def test_get_existing_tags_for_context_empty_cache(self, service):
        """Test getting tags when cache is empty"""
        tags = service.get_existing_tags_for_context()
        assert tags == []

    @pytest.mark.asyncio
    async def test_get_existing_tags_for_context(self, service_with_collection):
        """Test getting existing tags for LLM context"""
        await service_with_collection.refresh_tag_cache()

        tags = service_with_collection.get_existing_tags_for_context(limit=10)

        assert isinstance(tags, list)
        assert len(tags) > 0
        # Should be sorted by frequency
        assert 'tech/ai/ml' in tags  # Most frequent

    @pytest.mark.asyncio
    async def test_get_existing_tags_by_domain(self, service_with_collection):
        """Test getting domain-specific tags"""
        await service_with_collection.refresh_tag_cache()

        tech_tags = service_with_collection.get_existing_tags_for_context(
            domain="technology",
            limit=10
        )

        assert isinstance(tech_tags, list)
        assert len(tech_tags) > 0
        # Should prioritize technology domain tags
        assert any('tech/' in tag for tag in tech_tags)

    def test_get_tag_statistics_empty_cache(self, service):
        """Test statistics when cache is empty"""
        stats = service.get_tag_statistics()
        assert stats == {}

    @pytest.mark.asyncio
    async def test_get_tag_statistics(self, service_with_collection):
        """Test getting tag usage statistics"""
        await service_with_collection.refresh_tag_cache()

        stats = service.get_tag_statistics()

        assert 'total_unique_tags' in stats
        assert 'total_documents' in stats
        assert 'avg_frequency' in stats
        assert 'most_used' in stats
        assert 'domains' in stats

        # Check most_used format
        assert isinstance(stats['most_used'], list)
        if stats['most_used']:
            assert isinstance(stats['most_used'][0], tuple)
            assert len(stats['most_used'][0]) == 2  # (tag, count)

    def test_suggest_similar_tags_empty_cache(self, service):
        """Test suggesting similar tags when cache is empty"""
        similar = service.suggest_similar_tags("new-tag")
        assert similar == []

    @pytest.mark.asyncio
    async def test_suggest_similar_tags_exact_match(self, service_with_collection):
        """Test suggesting similar tags with exact match"""
        await service_with_collection.refresh_tag_cache()

        similar = service.suggest_similar_tags("tech/ai/ml")

        assert len(similar) > 0
        # Exact match should have similarity 1.0
        assert similar[0][0] == "tech/ai/ml"
        assert similar[0][1] == 1.0

    @pytest.mark.asyncio
    async def test_suggest_similar_tags_substring(self, service_with_collection):
        """Test suggesting similar tags with substring match"""
        await service_with_collection.refresh_tag_cache()

        similar = service.suggest_similar_tags("tech/ai")

        assert len(similar) > 0
        # Should find "tech/ai" or "tech/ai/ml"
        assert any('tech/ai' in tag for tag, _ in similar)
        # Similarity should be high (0.9 for substring)
        assert similar[0][1] >= 0.9

    @pytest.mark.asyncio
    async def test_suggest_similar_tags_hierarchical(self, service_with_collection):
        """Test suggesting similar tags with hierarchical matching"""
        await service_with_collection.refresh_tag_cache()

        similar = service.suggest_similar_tags("technology/artificial-intelligence")

        # Should find tags with similar path components
        assert isinstance(similar, list)
        # Results should be sorted by similarity
        if len(similar) > 1:
            assert similar[0][1] >= similar[1][1]

    @pytest.mark.asyncio
    async def test_validate_and_deduplicate_tags(self, service_with_collection):
        """Test tag validation and deduplication"""
        await service_with_collection.refresh_tag_cache()

        proposed = [
            "tech/ai/ml",  # Exact match with existing
            "TECH/AI/ML",  # Case variant
            "  tech/ai  ",  # Whitespace
            "#hashtag",  # Hash prefix
            "new-unique-tag",  # New tag
            "",  # Empty
            "x"  # Too short
        ]

        validated = service.validate_and_deduplicate_tags(proposed)

        # Should normalize and deduplicate
        assert isinstance(validated, list)
        # Empty and too short should be filtered
        assert "" not in validated
        assert "x" not in validated
        # Hash prefix should be removed
        assert "hashtag" in validated or any('hashtag' in t for t in validated)
        # New tag should be included
        assert "new-unique-tag" in validated

    @pytest.mark.asyncio
    async def test_validate_merges_near_duplicates(self, service_with_collection):
        """Test that validation merges near-duplicate tags"""
        await service_with_collection.refresh_tag_cache()

        # Propose tag very similar to existing "tech/ai/ml"
        proposed = ["tech/ai/ml", "tech-ai-ml"]

        validated = service.validate_and_deduplicate_tags(proposed)

        # Should merge similar tags (exact match has similarity 1.0)
        # At least one variant should be present
        assert any('tech' in tag and 'ai' in tag and 'ml' in tag for tag in validated)

    def test_enrich_tags_with_hierarchy(self, service):
        """Test adding hierarchical structure to flat tags"""
        tags = ["literature", "read"]

        enriched = service.enrich_tags_with_hierarchy(tags)

        assert isinstance(enriched, list)
        assert "literature" in enriched
        # Should add workflow tag for "read"
        assert "cont/in/read" in enriched

    def test_enrich_tags_preserves_originals(self, service):
        """Test that enrichment preserves original tags"""
        tags = ["custom-tag", "my-note"]

        enriched = service.enrich_tags_with_hierarchy(tags)

        # Original tags should be preserved
        assert "custom-tag" in enriched
        assert "my-note" in enriched

    def test_get_tag_suggestions_for_llm_no_cache(self, service):
        """Test LLM tag suggestions when cache is empty"""
        suggestions = service.get_tag_suggestions_for_llm()

        assert isinstance(suggestions, str)
        # Should include base taxonomy
        assert "cont/in/read" in suggestions
        assert "literature" in suggestions

    @pytest.mark.asyncio
    async def test_get_tag_suggestions_for_llm_with_cache(self, service_with_collection):
        """Test LLM tag suggestions with populated cache"""
        await service_with_collection.refresh_tag_cache()

        suggestions = service.get_tag_suggestions_for_llm(domain="technology")

        assert isinstance(suggestions, str)
        # Should include existing tags
        assert "Existing tags" in suggestions or "existing tags" in suggestions.lower()
        # Should include base taxonomy
        assert "cont/in/read" in suggestions
        # Should include guidelines
        assert "Guidelines" in suggestions or "guidelines" in suggestions.lower()


# =============================================================================
# Co-occurrence Tests
# =============================================================================

class TestCoOccurrence:
    """Test tag co-occurrence tracking"""

    @pytest.mark.asyncio
    async def test_co_occurrence_tracking(self):
        """Test that co-occurring tags are tracked"""
        mock_collection = Mock()
        mock_collection.get.return_value = {
            "ids": ["doc1", "doc2"],
            "metadatas": [
                {"tags": "tag-a, tag-b, tag-c"},
                {"tags": "tag-a, tag-b"}
            ]
        }

        service = TagTaxonomyService(collection=mock_collection)
        await service.refresh_tag_cache()

        co_occur = service.tag_cache['co_occurrence']

        # tag-a and tag-b appear together twice
        assert 'tag-a' in co_occur
        assert co_occur['tag-a']['tag-b'] == 2

        # tag-b and tag-c appear together once
        assert co_occur['tag-b']['tag-c'] == 1


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_refresh_with_malformed_metadata(self):
        """Test refresh with malformed metadata"""
        mock_collection = Mock()
        mock_collection.get.return_value = {
            "ids": ["doc1", "doc2"],
            "metadatas": [
                None,  # Null metadata
                {"tags": "valid-tag"}
            ]
        }

        service = TagTaxonomyService(collection=mock_collection)

        # Should not crash
        await service.refresh_tag_cache()

        # Should still process valid entries
        assert service.tag_cache['total_docs'] == 2

    @pytest.mark.asyncio
    async def test_refresh_with_empty_tags(self):
        """Test refresh when documents have empty tags"""
        mock_collection = Mock()
        mock_collection.get.return_value = {
            "ids": ["doc1"],
            "metadatas": [{"tags": ""}]
        }

        service = TagTaxonomyService(collection=mock_collection)
        await service.refresh_tag_cache()

        # Should not crash, no tags should be added
        assert service.tag_cache['unique_tags'] == 0

    def test_validate_with_empty_list(self, service):
        """Test validation with empty tag list"""
        validated = service.validate_and_deduplicate_tags([])
        assert validated == []

    def test_suggest_similar_with_special_characters(self, service):
        """Test suggesting similar tags with special characters"""
        # Should not crash with special regex characters
        similar = service.suggest_similar_tags("test[tag]")
        assert isinstance(similar, list)

    @pytest.mark.asyncio
    async def test_refresh_with_collection_error(self):
        """Test graceful handling of collection errors"""
        mock_collection = Mock()
        mock_collection.get.side_effect = Exception("Database error")

        service = TagTaxonomyService(collection=mock_collection)

        # Should not crash, should log error
        await service.refresh_tag_cache()

        # Cache should remain empty
        assert service.tag_cache == {}
