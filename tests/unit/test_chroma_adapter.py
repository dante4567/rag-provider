"""
Unit tests for ChromaDBAdapter

Tests the critical format conversion layer between API format (nested)
and ChromaDB format (flat strings).
"""

import pytest
from src.adapters.chroma_adapter import ChromaDBAdapter


class TestFlattenEntitiesForStorage:
    """Test conversion from lists to comma-separated strings"""

    def test_flatten_all_entity_types(self):
        """Test flattening all entity types with data"""
        result = ChromaDBAdapter.flatten_entities_for_storage(
            people=["Alice", "Bob", "Charlie"],
            organizations=["ACME Corp", "Globex"],
            locations=["New York", "London"],
            technologies=["Python", "PostgreSQL"]
        )

        assert result == {
            "people": "Alice,Bob,Charlie",
            "organizations": "ACME Corp,Globex",
            "locations": "New York,London",
            "technologies": "Python,PostgreSQL"
        }

    def test_flatten_with_empty_lists(self):
        """Test that empty lists are omitted from result"""
        result = ChromaDBAdapter.flatten_entities_for_storage(
            people=["Alice"],
            organizations=[],
            locations=[],
            technologies=["Python"]
        )

        assert result == {
            "people": "Alice",
            "technologies": "Python"
        }
        assert "organizations" not in result
        assert "locations" not in result

    def test_flatten_with_none_values(self):
        """Test that None values in lists are filtered out"""
        result = ChromaDBAdapter.flatten_entities_for_storage(
            people=["Alice", None, "Bob"],
            organizations=["ACME"],
            locations=[],
            technologies=[]
        )

        assert result == {
            "people": "Alice,Bob",
            "organizations": "ACME"
        }

    def test_flatten_with_whitespace(self):
        """Test that whitespace is properly handled"""
        result = ChromaDBAdapter.flatten_entities_for_storage(
            people=["  Alice  ", "Bob"],
            organizations=["ACME Corp"],
            locations=[],
            technologies=[]
        )

        assert result == {
            "people": "Alice,Bob",  # Whitespace stripped
            "organizations": "ACME Corp"
        }

    def test_flatten_empty_all(self):
        """Test when all lists are empty"""
        result = ChromaDBAdapter.flatten_entities_for_storage(
            people=[],
            organizations=[],
            locations=[],
            technologies=[]
        )

        assert result == {}


class TestParseEntityField:
    """Test parsing individual entity fields from various formats"""

    def test_parse_comma_separated_string(self):
        """Test parsing comma-separated string"""
        result = ChromaDBAdapter.parse_entity_field("Alice,Bob,Charlie", "people")
        assert result == ["Alice", "Bob", "Charlie"]

    def test_parse_single_value_string(self):
        """Test parsing single value (no commas)"""
        result = ChromaDBAdapter.parse_entity_field("Alice", "people")
        assert result == ["Alice"]

    def test_parse_list(self):
        """Test parsing when already a list"""
        result = ChromaDBAdapter.parse_entity_field(["Alice", "Bob"], "people")
        assert result == ["Alice", "Bob"]

    def test_parse_empty_string(self):
        """Test parsing empty string"""
        result = ChromaDBAdapter.parse_entity_field("", "people")
        assert result == []

    def test_parse_none(self):
        """Test parsing None value"""
        result = ChromaDBAdapter.parse_entity_field(None, "people")
        assert result == []

    def test_parse_with_whitespace(self):
        """Test that whitespace is stripped"""
        result = ChromaDBAdapter.parse_entity_field("  Alice  ,  Bob  ", "people")
        assert result == ["Alice", "Bob"]

    def test_parse_with_empty_items(self):
        """Test that empty items are filtered out"""
        result = ChromaDBAdapter.parse_entity_field("Alice,,Bob,", "people")
        assert result == ["Alice", "Bob"]

    def test_parse_unexpected_type(self):
        """Test handling of unexpected types"""
        result = ChromaDBAdapter.parse_entity_field(123, "people")
        assert result == ["123"]  # Converted to string


class TestParseEntitiesFromStorage:
    """Test parsing all entity fields from ChromaDB metadata"""

    def test_parse_all_fields_from_strings(self):
        """Test parsing when all fields are comma-separated strings"""
        metadata = {
            "people": "Alice,Bob",
            "organizations": "ACME Corp",
            "locations": "New York,London",
            "technologies": "Python",
            "title": "Test Doc"  # Non-entity field
        }

        result = ChromaDBAdapter.parse_entities_from_storage(metadata)

        assert result == {
            "people": ["Alice", "Bob"],
            "organizations": ["ACME Corp"],
            "locations": ["New York", "London"],
            "technologies": ["Python"]
        }

    def test_parse_with_missing_fields(self):
        """Test parsing when some entity fields are missing"""
        metadata = {
            "people": "Alice",
            "title": "Test Doc"
        }

        result = ChromaDBAdapter.parse_entities_from_storage(metadata)

        assert result == {
            "people": ["Alice"],
            "organizations": [],
            "locations": [],
            "technologies": []
        }

    def test_parse_with_empty_strings(self):
        """Test parsing when entity fields are empty strings"""
        metadata = {
            "people": "",
            "organizations": "",
            "locations": "",
            "technologies": ""
        }

        result = ChromaDBAdapter.parse_entities_from_storage(metadata)

        assert result == {
            "people": [],
            "organizations": [],
            "locations": [],
            "technologies": []
        }


class TestSanitizeForChromaDB:
    """Test sanitization of metadata for ChromaDB storage"""

    def test_sanitize_basic_types(self):
        """Test that basic types pass through"""
        metadata = {
            "title": "Test",
            "count": 42,
            "score": 0.95,
            "active": True
        }

        result = ChromaDBAdapter.sanitize_for_chromadb(metadata)

        assert result == metadata

    def test_sanitize_removes_none(self):
        """Test that None values are removed"""
        metadata = {
            "title": "Test",
            "description": None,
            "count": 42
        }

        result = ChromaDBAdapter.sanitize_for_chromadb(metadata)

        assert result == {
            "title": "Test",
            "count": 42
        }
        assert "description" not in result

    def test_sanitize_converts_lists(self):
        """Test that lists are converted to comma-separated strings"""
        metadata = {
            "tags": ["tag1", "tag2", "tag3"],
            "numbers": [1, 2, 3]
        }

        result = ChromaDBAdapter.sanitize_for_chromadb(metadata)

        assert result == {
            "tags": "tag1,tag2,tag3",
            "numbers": "1,2,3"
        }

    def test_sanitize_skips_empty_lists(self):
        """Test that empty lists are omitted"""
        metadata = {
            "title": "Test",
            "tags": [],
            "count": 42
        }

        result = ChromaDBAdapter.sanitize_for_chromadb(metadata)

        assert result == {
            "title": "Test",
            "count": 42
        }
        assert "tags" not in result

    def test_sanitize_converts_dict_to_json(self):
        """Test that dicts are converted to JSON strings"""
        metadata = {
            "title": "Test",
            "nested": {"key": "value"}
        }

        result = ChromaDBAdapter.sanitize_for_chromadb(metadata)

        assert result["title"] == "Test"
        assert isinstance(result["nested"], str)
        assert "key" in result["nested"]


class TestRoundTrip:
    """Test round-trip conversions (flatten → parse → original)"""

    def test_round_trip_entities(self):
        """Test that entities survive a round-trip conversion"""
        # Original data
        people = ["Alice", "Bob"]
        orgs = ["ACME Corp"]
        locations = ["New York"]
        tech = ["Python", "PostgreSQL"]

        # Flatten for storage
        flattened = ChromaDBAdapter.flatten_entities_for_storage(
            people=people,
            organizations=orgs,
            locations=locations,
            technologies=tech
        )

        # Parse from storage
        parsed = ChromaDBAdapter.parse_entities_from_storage(flattened)

        # Verify round-trip
        assert parsed["people"] == people
        assert parsed["organizations"] == orgs
        assert parsed["locations"] == locations
        assert parsed["technologies"] == tech

    def test_round_trip_with_special_characters(self):
        """Test round-trip with names containing commas (edge case)"""
        # Note: This is a known limitation - commas in names will break parsing
        # This test documents the current behavior
        people = ["Smith, John"]  # Name with comma

        flattened = ChromaDBAdapter.flatten_entities_for_storage(
            people=people,
            organizations=[],
            locations=[],
            technologies=[]
        )

        parsed = ChromaDBAdapter.parse_entities_from_storage(flattened)

        # Current behavior: splits on comma (limitation)
        # This is a trade-off for simplicity
        assert parsed["people"] == ["Smith", "John"]  # Split into two


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_empty_metadata(self):
        """Test with completely empty metadata"""
        result = ChromaDBAdapter.parse_entities_from_storage({})
        assert all(len(v) == 0 for v in result.values())

    def test_very_long_lists(self):
        """Test with very long entity lists"""
        long_list = [f"Person{i}" for i in range(1000)]

        flattened = ChromaDBAdapter.flatten_entities_for_storage(
            people=long_list,
            organizations=[],
            locations=[],
            technologies=[]
        )

        parsed = ChromaDBAdapter.parse_entities_from_storage(flattened)
        assert len(parsed["people"]) == 1000
        assert parsed["people"] == long_list

    def test_unicode_names(self):
        """Test with Unicode characters in names"""
        people = ["François", "José", "李明"]

        flattened = ChromaDBAdapter.flatten_entities_for_storage(
            people=people,
            organizations=[],
            locations=[],
            technologies=[]
        )

        parsed = ChromaDBAdapter.parse_entities_from_storage(flattened)
        assert parsed["people"] == people
