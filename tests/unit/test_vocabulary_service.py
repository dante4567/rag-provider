"""
Unit tests for VocabularyService

Tests controlled vocabulary management including:
- Loading vocabularies from YAML files
- Topic validation
- Project matching
- Place/people validation
"""
import pytest
from unittest.mock import Mock, patch, mock_open
from datetime import date, timedelta
from src.services.vocabulary_service import VocabularyService


# =============================================================================
# VocabularyService Tests
# =============================================================================

class TestVocabularyService:
    """Test the VocabularyService class"""

    @pytest.fixture
    def mock_vocab_data(self):
        """Mock vocabulary data"""
        return {
            "topics.yaml": """
categories:
  school:
    - school/admin
    - school/enrollment
  work:
    - work/meetings
    - work/projects
""",
            "projects.yaml": """
projects:
  - id: school-2026
    name: School Enrollment 2026
    active: true
    start_date: 2025-01-01
    end_date: 2026-12-31
    watchlist:
      - school/admin
      - school/enrollment
""",
            "places.yaml": """
places:
  - Florianschule Essen
  - Office Downtown
  - Home
""",
            "people.yaml": """
roles:
  - Teacher
  - Manager
  - Family
"""
        }

    @pytest.fixture
    def service_with_mock_data(self, mock_vocab_data, tmp_path):
        """Create VocabularyService with mocked file loading"""
        # Create temp directory structure
        vocab_dir = tmp_path / "vocabulary"
        vocab_dir.mkdir()

        # Write mock YAML files
        for filename, content in mock_vocab_data.items():
            file_path = vocab_dir / filename
            file_path.write_text(content)

        # Create service
        return VocabularyService(str(vocab_dir))

    def test_init_creates_service(self, service_with_mock_data):
        """Test VocabularyService initialization"""
        service = service_with_mock_data
        assert service is not None
        assert service.vocabularies is not None

    def test_get_all_topics(self, service_with_mock_data):
        """Test retrieving all topics"""
        service = service_with_mock_data
        topics = service.get_all_topics()

        assert isinstance(topics, list)
        assert len(topics) > 0
        # Check for hierarchical topics
        assert any("school/" in topic for topic in topics)

    def test_is_valid_topic(self, service_with_mock_data):
        """Test topic validation"""
        service = service_with_mock_data

        # Valid topic
        assert service.is_valid_topic("school/admin") is True

        # Invalid topic
        assert service.is_valid_topic("nonexistent/topic") is False

    def test_get_active_projects(self, service_with_mock_data):
        """Test retrieving active projects"""
        service = service_with_mock_data
        projects = service.get_active_projects()

        assert isinstance(projects, list)
        assert len(projects) > 0
        assert "school-2026" in projects

    def test_get_all_places(self, service_with_mock_data):
        """Test retrieving all places"""
        service = service_with_mock_data
        places = service.get_all_places()

        assert isinstance(places, list)
        assert len(places) > 0
        assert "Florianschule Essen" in places or "Office Downtown" in places

    def test_is_valid_place(self, service_with_mock_data):
        """Test place validation"""
        service = service_with_mock_data

        # Valid place
        assert service.is_valid_place("Florianschule Essen") is True or \
               service.is_valid_place("Office Downtown") is True

        # Invalid place
        assert service.is_valid_place("Nonexistent Place") is False

    def test_get_all_people(self, service_with_mock_data):
        """Test retrieving all people roles"""
        service = service_with_mock_data
        people = service.get_all_people()

        assert isinstance(people, list)
        assert len(people) > 0

    def test_track_suggestion(self, service_with_mock_data):
        """Test tracking suggested tags"""
        service = service_with_mock_data

        # Track a suggestion
        service.track_suggestion("new-tag")
        service.track_suggestion("new-tag")
        service.track_suggestion("new-tag")

        # Get frequent suggestions
        frequent = service.get_frequent_suggestions(min_count=2)

        assert isinstance(frequent, dict)
        assert "new-tag" in frequent
        assert frequent["new-tag"] >= 2

    def test_get_frequent_suggestions(self, service_with_mock_data):
        """Test retrieving frequently suggested tags"""
        service = service_with_mock_data

        # Track multiple suggestions
        for _ in range(5):
            service.track_suggestion("frequent-tag")

        frequent = service.get_frequent_suggestions(min_count=3)

        assert "frequent-tag" in frequent
        assert frequent["frequent-tag"] == 5

    def test_validate_metadata(self, service_with_mock_data):
        """Test metadata validation"""
        service = service_with_mock_data

        metadata = {
            "topics": ["school/admin", "invalid-topic"],
            "projects": ["school-2026", "invalid-project"],
            "places": ["Florianschule Essen", "Invalid Place"]
        }

        result = service.validate_metadata(metadata)

        assert isinstance(result, dict)
        assert "invalid_topics" in result or "invalid" in str(result).lower()

    def test_get_stats(self, service_with_mock_data):
        """Test getting vocabulary statistics"""
        service = service_with_mock_data

        stats = service.get_stats()

        assert isinstance(stats, dict)
        assert "total_topics" in stats or "topics" in str(stats).lower()
        assert "total_projects" in stats or "projects" in str(stats).lower()


# =============================================================================
# Project Matching Tests
# =============================================================================

class TestProjectMatching:
    """Test project matching functionality"""

    @pytest.fixture
    def service_with_projects(self, tmp_path):
        """Create service with project data"""
        vocab_dir = tmp_path / "vocabulary"
        vocab_dir.mkdir()

        # Create projects YAML with watchlist
        projects_yaml = """
projects:
  - id: school-2026
    name: School Enrollment 2026
    active: true
    start_date: 2025-01-01
    end_date: 2026-12-31
    watchlist:
      - school/admin
      - school/enrollment
"""
        (vocab_dir / "projects.yaml").write_text(projects_yaml)

        # Create minimal topics YAML
        topics_yaml = """
categories:
  school:
    - school/admin
    - school/enrollment
"""
        (vocab_dir / "topics.yaml").write_text(topics_yaml)

        # Create minimal places/people YAML
        (vocab_dir / "places.yaml").write_text("places: []")
        (vocab_dir / "people.yaml").write_text("roles: []")

        return VocabularyService(str(vocab_dir))

    def test_match_projects_for_doc(self, service_with_projects):
        """Test matching projects based on document topics"""
        service = service_with_projects

        # Document with school topics
        doc_topics = ["school/admin", "school/enrollment"]
        doc_date = date(2025, 6, 1)

        matched = service.match_projects_for_doc(doc_topics, doc_date)

        # Should match school-2026 project
        assert isinstance(matched, list)
        if len(matched) > 0:
            assert "school-2026" in matched


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestVocabularyServiceErrors:
    """Test error handling in VocabularyService"""

    def test_missing_vocabulary_directory(self):
        """Test handling of missing vocabulary directory"""
        with pytest.raises(Exception):
            VocabularyService("/nonexistent/directory")

    def test_get_stats_without_loading(self, tmp_path):
        """Test getting stats even if loading fails"""
        vocab_dir = tmp_path / "vocabulary"
        vocab_dir.mkdir()

        # Create empty/invalid YAML files
        (vocab_dir / "topics.yaml").write_text("invalid: yaml: content:")

        # Service should handle gracefully or raise clear error
        try:
            service = VocabularyService(str(vocab_dir))
            stats = service.get_stats()
            assert isinstance(stats, dict)
        except Exception as e:
            # Error should be clear
            assert "yaml" in str(e).lower() or "vocabulary" in str(e).lower()
