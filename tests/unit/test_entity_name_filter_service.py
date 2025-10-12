"""
Unit tests for EntityNameFilterService

Tests filtering of generic roles from specific person names
"""

import pytest
from src.services.entity_name_filter_service import EntityNameFilterService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def service():
    """Create EntityNameFilterService instance"""
    return EntityNameFilterService()


# ============================================================================
# Person Filtering Tests
# ============================================================================

class TestPersonFiltering:
    """Test person filtering functionality"""

    def test_filter_empty_list(self, service):
        """Should return empty list for empty input"""
        result = service.filter_people([])
        assert result == []

    def test_filter_generic_role_removed(self, service):
        """Should remove generic single-word roles"""
        people = ["Richter", "Anwalt", "Lehrer"]
        result = service.filter_people(people)
        assert result == []

    def test_filter_specific_person_kept(self, service):
        """Should keep specific named people"""
        people = ["Dr. Schmidt", "Prof. Meyer", "Rechtsanwalt Müller"]
        result = service.filter_people(people)
        assert len(result) == 3

    def test_filter_mixed_list(self, service):
        """Should filter generic, keep specific"""
        people = ["Richter", "Dr. Schmidt", "Anwalt", "Prof. Meyer"]
        result = service.filter_people(people)
        assert len(result) == 2
        assert "Dr. Schmidt" in result
        assert "Prof. Meyer" in result

    def test_filter_dict_format(self, service):
        """Should handle dictionary format (person objects)"""
        people = [
            {"name": "Richter"},
            {"name": "Dr. Schmidt"}
        ]
        result = service.filter_people(people)
        assert len(result) == 1
        assert result[0]["name"] == "Dr. Schmidt"


# ============================================================================
# Specific Person Detection Tests
# ============================================================================

class TestSpecificPersonDetection:
    """Test is_specific_person logic"""

    def test_empty_name_false(self, service):
        """Should return False for empty name"""
        assert service.is_specific_person("") is False
        assert service.is_specific_person("   ") is False

    def test_generic_role_false(self, service):
        """Should return False for known generic roles"""
        assert service.is_specific_person("Richter") is False
        assert service.is_specific_person("Anwalt") is False
        assert service.is_specific_person("Lehrer") is False

    def test_with_title_true(self, service):
        """Should return True for names with titles"""
        assert service.is_specific_person("Dr. Schmidt") is True
        assert service.is_specific_person("Prof. Meyer") is True
        assert service.is_specific_person("Dr. Meyer") is True

    def test_multiple_words_true(self, service):
        """Should return True for multi-word names"""
        assert service.is_specific_person("Hans Müller") is True
        assert service.is_specific_person("Anna Schmidt") is True
        assert service.is_specific_person("Rechtsanwalt Müller") is True

    def test_english_roles_false(self, service):
        """Should return False for English generic roles"""
        assert service.is_specific_person("judge") is False
        assert service.is_specific_person("lawyer") is False
        assert service.is_specific_person("teacher") is False


# ============================================================================
# Role Set Tests
# ============================================================================

class TestRoleSets:
    """Test role sets are properly configured"""

    def test_german_roles_defined(self, service):
        """Should have German roles defined"""
        assert len(service.GERMAN_ROLES) > 0
        assert 'richter' in service.GERMAN_ROLES
        assert 'anwalt' in service.GERMAN_ROLES

    def test_english_roles_defined(self, service):
        """Should have English roles defined"""
        assert len(service.ENGLISH_ROLES) > 0
        assert 'judge' in service.ENGLISH_ROLES
        assert 'lawyer' in service.ENGLISH_ROLES

    def test_specific_titles_defined(self, service):
        """Should have specific titles defined"""
        assert len(service.SPECIFIC_TITLES) > 0
        assert 'dr.' in service.SPECIFIC_TITLES
        assert 'prof.' in service.SPECIFIC_TITLES
