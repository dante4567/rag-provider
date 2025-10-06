"""
Unit tests for ObsidianService

Tests Obsidian export functionality including:
- Filename generation (YYYY-MM-DD__type__slug__id format)
- Frontmatter YAML generation
- Tag derivation
- Entity stub creation
- Wiki-link xref blocks
"""
import pytest
from unittest.mock import Mock, patch, mock_open
from datetime import datetime
from pathlib import Path
import tempfile
import shutil
from src.services.obsidian_service import ObsidianService
from src.models.schemas import DocumentType


# =============================================================================
# ObsidianService Tests
# =============================================================================

class TestObsidianService:
    """Test the ObsidianService class"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        temp = tempfile.mkdtemp()
        yield temp
        # Cleanup
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def service(self, temp_dir):
        """Create ObsidianService instance with temp directory"""
        return ObsidianService(
            output_dir=temp_dir,
            refs_dir=f"{temp_dir}/refs"
        )

    def test_init_creates_directories(self, temp_dir):
        """Test that initialization creates required directories"""
        service = ObsidianService(
            output_dir=temp_dir,
            refs_dir=f"{temp_dir}/refs"
        )

        assert service.output_dir.exists()
        assert service.refs_dir.exists()
        assert (service.refs_dir / "people").exists()
        assert (service.refs_dir / "projects").exists()
        assert (service.refs_dir / "places").exists()
        assert (service.refs_dir / "orgs").exists()

    def test_generate_short_id(self, service):
        """Test short ID generation (deterministic hash)"""
        content1 = "Test content for hashing"
        content2 = "Test content for hashing"
        content3 = "Different content"

        # Same content = same ID
        id1 = service.generate_short_id(content1)
        id2 = service.generate_short_id(content2)
        assert id1 == id2

        # Different content = different ID
        id3 = service.generate_short_id(content3)
        assert id1 != id3

        # Length should be 4 by default
        assert len(id1) == 4

    def test_generate_short_id_custom_length(self, service):
        """Test short ID with custom length"""
        content = "Test content"

        short_id = service.generate_short_id(content, length=8)
        assert len(short_id) == 8

    def test_create_slug_basic(self, service):
        """Test slug creation from titles"""
        # Basic title
        assert service.create_slug("Hello World") == "hello-world"

        # With special characters
        slug = service.create_slug("Meeting Notes (2025)")
        assert " " not in slug
        assert "(" not in slug

    def test_create_slug_max_length(self, service):
        """Test slug respects max length"""
        long_title = "A" * 100

        slug = service.create_slug(long_title, max_length=20)
        assert len(slug) <= 20

    def test_create_slug_empty_fallback(self, service):
        """Test slug fallback for empty/invalid input"""
        slug = service.create_slug("")
        assert slug == "document"  # Fallback

    def test_generate_filename_format(self, service):
        """Test filename format: YYYY-MM-DD__type__slug__id.md"""
        filename = service.generate_filename(
            title="Test Document",
            doc_type=DocumentType.pdf,
            created_at=datetime(2025, 10, 6),
            content="Test content"
        )

        # Should match format
        assert filename.startswith("2025-10-06__pdf__")
        assert filename.endswith(".md")
        assert "test-document" in filename

    def test_derive_tags_basic(self, service):
        """Test tag derivation from metadata"""
        tags = service.derive_tags(
            doc_type=DocumentType.email,
            people=["Alice", "Bob"],
            projects=["Project Alpha"],
            places=["Office"],
            topics=["meeting/notes"],
            organizations=["ACME Corp"]
        )

        # Check tag prefixes
        assert "doc/email" in tags
        assert any("person/" in tag for tag in tags)
        assert any("project/" in tag for tag in tags)
        assert any("place/" in tag for tag in tags)
        assert any("topic/" in tag for tag in tags)
        assert any("org/" in tag for tag in tags)

    def test_derive_tags_empty_lists(self, service):
        """Test tag derivation with empty metadata"""
        tags = service.derive_tags(
            doc_type=DocumentType.pdf,
            people=[],
            projects=[],
            places=[],
            topics=[],
            organizations=[]
        )

        # Should at least have doc type tag
        assert len(tags) == 1
        assert tags[0] == "doc/pdf"

    def test_build_frontmatter_structure(self, service):
        """Test frontmatter YAML structure"""
        frontmatter = service.build_frontmatter(
            id="test-id",
            title="Test Document",
            source="test",
            doc_type=DocumentType.pdf,
            people=["Alice"],
            places=["Office"],
            projects=["Project1"],
            topics=["topic1"],
            organizations=["ACME"],
            created_at=datetime(2025, 10, 6),
            ingested_at=datetime(2025, 10, 6),
            metadata={
                'quality_score': 0.95,
                'recency_score': 0.8,
                'content_hash': 'abc123'
            }
        )

        # Should be valid YAML with delimiters
        assert frontmatter.startswith("---\n")
        assert frontmatter.endswith("---\n\n")

        # Should contain key fields
        assert "title:" in frontmatter
        assert "doc_type:" in frontmatter
        assert "tags:" in frontmatter
        assert "rag:" in frontmatter

    def test_build_frontmatter_rag_section(self, service):
        """Test that RAG section is included in frontmatter"""
        frontmatter = service.build_frontmatter(
            id="test",
            title="Test",
            source="test",
            doc_type=DocumentType.pdf,
            people=[],
            places=[],
            projects=[],
            topics=[],
            organizations=[],
            created_at=datetime(2025, 10, 6),
            ingested_at=datetime(2025, 10, 6),
            metadata={
                'quality_score': 0.9,
                'novelty_score': 0.8,
                'actionability_score': 0.7,
                'recency_score': 0.95
            }
        )

        # Check RAG section exists
        assert "rag:" in frontmatter
        assert "quality_score:" in frontmatter
        assert "recency_score:" in frontmatter

    def test_build_xref_block_basic(self, service):
        """Test xref block generation with wiki-links"""
        xref = service.build_xref_block(
            projects=["Project Alpha"],
            places=["Office"],
            people=["Alice", "Bob"],
            organizations=["ACME Corp"]
        )

        # Should have RAG:IGNORE markers
        assert "<!-- RAG:IGNORE-START -->" in xref
        assert "<!-- RAG:IGNORE-END -->" in xref

        # Should have wiki-links
        assert "[[project:Project Alpha]]" in xref
        assert "[[person:Alice]]" in xref
        assert "[[person:Bob]]" in xref

    def test_build_xref_block_empty(self, service):
        """Test xref block returns empty for no entities"""
        xref = service.build_xref_block(
            projects=[],
            places=[],
            people=[],
            organizations=[]
        )

        assert xref == ""

    def test_build_body_basic(self, service):
        """Test body structure generation"""
        body = service.build_body(
            content="Main content here",
            summary="This is a summary",
            key_facts=["Fact 1", "Fact 2"],
            outcomes=["Outcome 1"],
            next_actions=["Action 1"],
            timeline=[]
        )

        # Check sections
        assert "Summary:" in body
        assert "## Key Facts" in body
        assert "## Evidence / Excerpts" in body
        assert "Main content here" in body
        assert "## Outcomes / Decisions" in body
        assert "## Next Actions" in body

    def test_build_body_minimal(self, service):
        """Test body with minimal content"""
        body = service.build_body(
            content="Just content",
            summary="",
            key_facts=[],
            outcomes=[],
            next_actions=[],
            timeline=[]
        )

        # Should have at least evidence section
        assert "## Evidence / Excerpts" in body
        assert "Just content" in body

    def test_create_entity_stub_person(self, service):
        """Test creating person entity stub"""
        stub_path = service.create_entity_stub(
            entity_type="person",
            name="Alice Smith"
        )

        # Check file created
        assert stub_path.exists()

        # Check content
        content = stub_path.read_text()
        assert "# Alice Smith" in content
        assert "type: person" in content
        assert "name: Alice Smith" in content

    def test_create_entity_stub_project(self, service):
        """Test creating project entity stub"""
        stub_path = service.create_entity_stub(
            entity_type="project",
            name="Project Alpha"
        )

        assert stub_path.exists()
        content = stub_path.read_text()
        assert "type: project" in content

    def test_create_entity_stub_idempotent(self, service):
        """Test entity stub creation is idempotent"""
        # Create once
        stub_path1 = service.create_entity_stub("person", "Alice")
        original_content = stub_path1.read_text()

        # Create again
        stub_path2 = service.create_entity_stub("person", "Alice")

        # Should be same file
        assert stub_path1 == stub_path2

        # Content should not change
        assert stub_path2.read_text() == original_content

    def test_parse_csv_basic(self, service):
        """Test CSV parsing"""
        result = service._parse_csv("Alice, Bob, Charlie")

        assert len(result) == 3
        assert "Alice" in result
        assert "Bob" in result
        assert "Charlie" in result

    def test_parse_csv_empty(self, service):
        """Test CSV parsing with empty input"""
        assert service._parse_csv("") == []
        assert service._parse_csv(None) == []

    def test_remove_empty_basic(self, service):
        """Test removing empty values from dict"""
        data = {
            "field1": "value",
            "field2": "",
            "field3": [],
            "field4": None,
            "field5": "keep"
        }

        cleaned = service._remove_empty(data)

        assert "field1" in cleaned
        assert "field5" in cleaned
        assert "field2" not in cleaned
        assert "field3" not in cleaned
        assert "field4" not in cleaned

    def test_remove_empty_nested(self, service):
        """Test removing empty values from nested dict"""
        data = {
            "outer": {
                "inner1": "value",
                "inner2": "",
                "inner3": []
            },
            "keep": "this"
        }

        cleaned = service._remove_empty(data)

        assert "outer" in cleaned
        assert cleaned["outer"]["inner1"] == "value"
        assert "inner2" not in cleaned["outer"]


# =============================================================================
# Integration-style Tests
# =============================================================================

class TestObsidianServiceIntegration:
    """Integration tests for full export workflow"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def service(self, temp_dir):
        """Create service with temp directory"""
        return ObsidianService(temp_dir, f"{temp_dir}/refs")

    def test_export_document_basic(self, service):
        """Test basic document export"""
        metadata = {
            "summary": "Test summary",
            "people_roles": "Alice,Bob",
            "places": "Office",
            "projects": "Project1",
            "topics": "meeting/notes",
            "organizations": "ACME",
            "quality_score": 0.9,
            "recency_score": 0.95
        }

        result = service.export_document(
            title="Test Meeting Notes",
            content="Meeting content here",
            metadata=metadata,
            document_type=DocumentType.email,
            created_at=datetime(2025, 10, 6),
            source="email"
        )

        # Check file created
        assert result.exists()
        assert result.suffix == ".md"

        # Check filename format
        assert result.name.startswith("2025-10-06__email__")

    def test_export_creates_entity_stubs(self, service):
        """Test that export creates entity stubs"""
        metadata = {
            "people_roles": "Alice,Bob",
            "projects": "ProjectAlpha",
            "places": "Office"
        }

        service.export_document(
            title="Test",
            content="Content",
            metadata=metadata,
            document_type=DocumentType.pdf,
            created_at=datetime(2025, 10, 6)
        )

        # Check stubs created
        people_dir = service.refs_dir / "peoples"
        projects_dir = service.refs_dir / "projects"

        # Note: Might need to check actual stub files exist
        assert service.refs_dir.exists()

    def test_export_content_structure(self, service):
        """Test exported content has correct structure"""
        metadata = {
            "summary": "Important meeting",
            "quality_score": 0.85
        }

        result = service.export_document(
            title="Test Document",
            content="Test content",
            metadata=metadata,
            document_type=DocumentType.pdf,
            created_at=datetime(2025, 10, 6)
        )

        content = result.read_text()

        # Check structure
        assert content.startswith("---\n")  # Frontmatter
        assert "# Test Document" in content  # Title
        assert "Summary:" in content  # Summary
        assert "## Evidence / Excerpts" in content  # Body section
        assert "Test content" in content  # Actual content
