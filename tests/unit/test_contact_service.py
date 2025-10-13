"""
Unit tests for ContactService

Tests vCard generation, contact parsing, role inference, and export functionality
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from src.services.contact_service import ContactService, get_contact_service


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_contact_dir():
    """Create temporary directory for vCard files"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def contact_service(temp_contact_dir):
    """Create ContactService with temp directory"""
    return ContactService(output_dir=temp_contact_dir)


# =============================================================================
# Name Sanitization Tests
# =============================================================================

class TestNameSanitization:
    """Test name sanitization for filenames"""

    def test_sanitize_name_basic(self, contact_service):
        """Test basic name sanitization"""
        result = contact_service.sanitize_name("John Doe")
        assert result == "john-doe"

    def test_sanitize_name_special_chars(self, contact_service):
        """Test special character removal"""
        result = contact_service.sanitize_name("John @#$ Doe")
        assert result == "john-doe"

    def test_sanitize_name_german_umlauts(self, contact_service):
        """Test German umlauts preserved"""
        result = contact_service.sanitize_name("Müller Äöü")
        assert "müller" in result
        assert "äöü" in result

    def test_sanitize_name_multiple_spaces(self, contact_service):
        """Test multiple spaces collapsed"""
        result = contact_service.sanitize_name("John    Doe")
        assert result == "john-doe"

    def test_sanitize_name_leading_trailing_spaces(self, contact_service):
        """Test leading/trailing spaces removed"""
        result = contact_service.sanitize_name("  John Doe  ")
        assert result == "john-doe"

    def test_sanitize_name_dots(self, contact_service):
        """Test dots in names (like Dr.)"""
        result = contact_service.sanitize_name("Dr. John Doe")
        assert result == "dr-john-doe"


# =============================================================================
# vCard Creation Tests
# =============================================================================

class TestVCardCreation:
    """Test vCard file creation"""

    def test_create_vcard_minimal(self, contact_service, temp_contact_dir):
        """Test vCard with just name"""
        path = contact_service.create_vcard(name="John Doe")

        assert path is not None
        assert path.exists()
        assert path.suffix == ".vcf"

        content = path.read_text()
        assert "BEGIN:VCARD" in content
        assert "VERSION:3.0" in content
        assert "FN:John Doe" in content
        assert "N:Doe;John;;;" in content
        assert "END:VCARD" in content

    def test_create_vcard_single_name(self, contact_service):
        """Test vCard with single name (no family name)"""
        path = contact_service.create_vcard(name="Madonna")

        content = path.read_text()
        assert "FN:Madonna" in content
        assert "N:;Madonna;;;" in content  # Empty family name

    def test_create_vcard_with_role(self, contact_service):
        """Test vCard with role/title"""
        path = contact_service.create_vcard(
            name="John Doe",
            role="Software Engineer"
        )

        content = path.read_text()
        assert "TITLE:Software Engineer" in content

    def test_create_vcard_with_organization(self, contact_service):
        """Test vCard with organization"""
        path = contact_service.create_vcard(
            name="John Doe",
            organization="Acme Corp"
        )

        content = path.read_text()
        assert "ORG:Acme Corp" in content

    def test_create_vcard_with_email(self, contact_service):
        """Test vCard with email"""
        path = contact_service.create_vcard(
            name="John Doe",
            email="john@example.com"
        )

        content = path.read_text()
        assert "EMAIL;TYPE=INTERNET:john@example.com" in content

    def test_create_vcard_with_phone(self, contact_service):
        """Test vCard with phone number"""
        path = contact_service.create_vcard(
            name="John Doe",
            phone="+1-555-1234"
        )

        content = path.read_text()
        assert "TEL;TYPE=CELL:+1-555-1234" in content

    def test_create_vcard_with_address(self, contact_service):
        """Test vCard with address"""
        path = contact_service.create_vcard(
            name="John Doe",
            address="123 Main St, City, State"
        )

        content = path.read_text()
        assert "ADR;TYPE=WORK:;;123 Main St, City, State;;;;" in content

    def test_create_vcard_with_notes(self, contact_service):
        """Test vCard with notes"""
        path = contact_service.create_vcard(
            name="John Doe",
            notes="Important contact"
        )

        content = path.read_text()
        assert "NOTE:Important contact" in content

    def test_create_vcard_with_document_sources(self, contact_service):
        """Test vCard with document sources"""
        path = contact_service.create_vcard(
            name="John Doe",
            document_sources=["doc1.pdf", "doc2.pdf"]
        )

        content = path.read_text()
        # Commas are escaped in vCard format
        assert "Mentioned in:" in content
        assert "doc1.pdf" in content
        assert "doc2.pdf" in content

    def test_create_vcard_with_many_sources(self, contact_service):
        """Test vCard with many document sources (truncation)"""
        sources = [f"doc{i}.pdf" for i in range(10)]
        path = contact_service.create_vcard(
            name="John Doe",
            document_sources=sources
        )

        content = path.read_text()
        assert "Mentioned in:" in content
        assert "(+7 more)" in content  # Only first 3 shown

    def test_create_vcard_with_all_fields(self, contact_service):
        """Test vCard with all fields populated"""
        path = contact_service.create_vcard(
            name="Dr. Jane Smith",
            role="Chief Medical Officer",
            organization="Health Corp",
            email="jane@health.com",
            phone="+1-555-5678",
            address="456 Medical Plaza",
            document_sources=["patient_records.pdf"],
            notes="Board certified"
        )

        assert path is not None
        content = path.read_text()

        assert "FN:Dr. Jane Smith" in content
        assert "TITLE:Chief Medical Officer" in content
        assert "ORG:Health Corp" in content
        assert "EMAIL;TYPE=INTERNET:jane@health.com" in content
        assert "TEL;TYPE=CELL:+1-555-5678" in content
        assert "ADR;TYPE=WORK:;;456 Medical Plaza;;;;" in content
        assert "Board certified" in content
        assert "Mentioned in: patient_records.pdf" in content

    def test_create_vcard_categories(self, contact_service):
        """Test vCard categories"""
        path = contact_service.create_vcard(
            name="John Doe",
            role="Lawyer"
        )

        content = path.read_text()
        assert "CATEGORIES:RAG-Extracted,Lawyer" in content

    def test_create_vcard_metadata(self, contact_service):
        """Test vCard metadata fields"""
        path = contact_service.create_vcard(name="John Doe")

        content = path.read_text()
        assert "REV:" in content  # Revision timestamp
        assert "PRODID:-//RAG Provider//Contact Service//EN" in content

    def test_create_vcard_note_escaping(self, contact_service):
        """Test special character escaping in notes"""
        path = contact_service.create_vcard(
            name="John Doe",
            notes="Contact info: test@example.com; phone: 555-1234, address"
        )

        content = path.read_text()
        # Commas and semicolons should be escaped
        assert "\\," in content or "\\;" in content


# =============================================================================
# Role Inference Tests
# =============================================================================

class TestRoleInference:
    """Test role inference from names"""

    def test_infer_role_judge_female(self, contact_service):
        """Test judge (female) inference"""
        role = contact_service._infer_role("Richterin Schmidt")
        assert role == "Judge"

    def test_infer_role_judge_male(self, contact_service):
        """Test judge (male) inference"""
        role = contact_service._infer_role("Richter Müller")
        assert role == "Judge"

    def test_infer_role_lawyer_male(self, contact_service):
        """Test lawyer (male) inference"""
        role = contact_service._infer_role("Rechtsanwalt Weber")
        assert role == "Lawyer"

    def test_infer_role_lawyer_female(self, contact_service):
        """Test lawyer (female) inference"""
        role = contact_service._infer_role("Rechtsanwältin Fischer")
        assert role == "Lawyer"

    def test_infer_role_doctor(self, contact_service):
        """Test doctor title inference"""
        role = contact_service._infer_role("Dr. Schmidt")
        assert role == "Doctor"

    def test_infer_role_professor(self, contact_service):
        """Test professor title inference"""
        role = contact_service._infer_role("Prof. Weber")
        assert role == "Professor"

    def test_infer_role_none(self, contact_service):
        """Test no role inference"""
        role = contact_service._infer_role("John Doe")
        assert role is None


# =============================================================================
# Update/Merge Tests
# =============================================================================

class TestUpdateOrCreate:
    """Test updating existing vCards"""

    def test_update_or_create_new(self, contact_service, temp_contact_dir):
        """Test creating new vCard"""
        path = contact_service.update_or_create_vcard(
            name="John Doe",
            role="Engineer",
            document_source="doc1.pdf"
        )

        assert path.exists()
        content = path.read_text()
        assert "TITLE:Engineer" in content
        assert "Mentioned in: doc1.pdf" in content

    def test_update_or_create_merge_sources(self, contact_service):
        """Test merging document sources"""
        # Create initial vCard
        contact_service.update_or_create_vcard(
            name="John Doe",
            document_source="doc1.pdf"
        )

        # Update with new source
        path = contact_service.update_or_create_vcard(
            name="John Doe",
            document_source="doc2.pdf"
        )

        content = path.read_text()
        assert "doc1.pdf" in content
        assert "doc2.pdf" in content

    def test_update_or_create_preserve_role(self, contact_service):
        """Test preserving existing role"""
        # Create with role
        contact_service.update_or_create_vcard(
            name="John Doe",
            role="Engineer"
        )

        # Update without role (should preserve)
        path = contact_service.update_or_create_vcard(
            name="John Doe",
            document_source="doc2.pdf"
        )

        content = path.read_text()
        assert "TITLE:Engineer" in content

    def test_update_or_create_update_role(self, contact_service):
        """Test updating role"""
        # Create with role
        contact_service.update_or_create_vcard(
            name="John Doe",
            role="Engineer"
        )

        # Update with new role
        path = contact_service.update_or_create_vcard(
            name="John Doe",
            role="Senior Engineer"
        )

        content = path.read_text()
        assert "TITLE:Senior Engineer" in content
        assert "TITLE:Engineer" not in content or content.count("TITLE:") == 1

    def test_update_or_create_duplicate_sources(self, contact_service):
        """Test preventing duplicate sources"""
        # Create with source
        contact_service.update_or_create_vcard(
            name="John Doe",
            document_source="doc1.pdf"
        )

        # Update with same source
        path = contact_service.update_or_create_vcard(
            name="John Doe",
            document_source="doc1.pdf"
        )

        content = path.read_text()
        # Should only appear once
        assert content.count("doc1.pdf") == 1


# =============================================================================
# Batch Creation Tests
# =============================================================================

class TestBatchVCardCreation:
    """Test creating vCards from metadata"""

    def test_create_vcards_from_strings(self, contact_service):
        """Test batch creation from string names"""
        people = ["John Doe", "Jane Smith", "Dr. Weber"]
        paths = contact_service.create_vcards_from_metadata(
            people=people,
            document_title="test_doc.pdf"
        )

        assert len(paths) == 3
        for path in paths:
            assert path.exists()

    def test_create_vcards_from_dict_objects(self, contact_service):
        """Test batch creation from person objects"""
        people = [
            {"name": "John Doe", "email": "john@example.com"},
            {"name": "Jane Smith", "phone": "+1-555-1234"}
        ]
        paths = contact_service.create_vcards_from_metadata(
            people=people,
            document_title="contacts.pdf"
        )

        assert len(paths) == 2

        # Check first vCard has email
        content1 = paths[0].read_text()
        assert "EMAIL;TYPE=INTERNET:john@example.com" in content1

        # Check second vCard has phone
        content2 = paths[1].read_text()
        assert "TEL;TYPE=CELL:+1-555-1234" in content2

    def test_create_vcards_mixed_format(self, contact_service):
        """Test batch creation with mixed string/dict format"""
        people = [
            "John Doe",  # String
            {"name": "Jane Smith", "email": "jane@example.com"}  # Dict
        ]
        paths = contact_service.create_vcards_from_metadata(people=people)

        assert len(paths) == 2

    def test_create_vcards_with_role_inference(self, contact_service):
        """Test role inference during batch creation"""
        people = ["Rechtsanwalt Müller", "Dr. Schmidt"]
        paths = contact_service.create_vcards_from_metadata(people=people)

        content1 = paths[0].read_text()
        assert "TITLE:Lawyer" in content1

        content2 = paths[1].read_text()
        assert "TITLE:Doctor" in content2

    def test_create_vcards_skip_empty_names(self, contact_service):
        """Test skipping person objects without names"""
        people = [
            {"name": "John Doe"},
            {"email": "orphan@example.com"},  # No name
            {"name": ""}  # Empty name
        ]
        paths = contact_service.create_vcards_from_metadata(people=people)

        assert len(paths) == 1  # Only John Doe

    def test_create_vcards_with_bank_account(self, contact_service):
        """Test person with bank account info"""
        people = [
            {"name": "John Doe", "bank_account": "DE89370400440532013000"}
        ]
        paths = contact_service.create_vcards_from_metadata(people=people)

        content = paths[0].read_text()
        assert "Bank account:" in content


# =============================================================================
# Export Tests
# =============================================================================

class TestExportAllVCards:
    """Test exporting all vCards to single file"""

    def test_export_all_vcards(self, contact_service, temp_contact_dir):
        """Test combining multiple vCards"""
        # Create some vCards
        contact_service.create_vcard("John Doe")
        contact_service.create_vcard("Jane Smith")
        contact_service.create_vcard("Bob Johnson")

        # Export all
        export_path = contact_service.export_all_vcards()

        assert export_path.exists()
        content = export_path.read_text()

        # Should have 3 vCards
        assert content.count("BEGIN:VCARD") == 3
        assert content.count("END:VCARD") == 3
        assert "John Doe" in content
        assert "Jane Smith" in content
        assert "Bob Johnson" in content

    def test_export_all_vcards_custom_path(self, contact_service, temp_contact_dir):
        """Test export to custom path"""
        contact_service.create_vcard("Test Person")

        custom_path = temp_contact_dir / "custom_export.vcf"
        export_path = contact_service.export_all_vcards(output_file=custom_path)

        assert export_path == custom_path
        assert custom_path.exists()

    def test_export_all_vcards_empty(self, contact_service):
        """Test export with no vCards"""
        export_path = contact_service.export_all_vcards()

        assert export_path.exists()
        # Should be empty or just whitespace
        content = export_path.read_text()
        assert len(content.strip()) == 0


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestFactoryFunction:
    """Test get_contact_service factory"""

    def test_get_contact_service_default(self):
        """Test factory with default output dir"""
        service = get_contact_service()
        assert isinstance(service, ContactService)
        assert service.output_dir == Path("/data/contacts")

    def test_get_contact_service_custom_dir(self, temp_contact_dir):
        """Test factory with custom output dir"""
        service = get_contact_service(output_dir=temp_contact_dir)
        assert service.output_dir == temp_contact_dir


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_vcard_with_unicode_names(self, contact_service):
        """Test vCard with unicode characters"""
        path = contact_service.create_vcard(name="François Müller")

        assert path is not None
        content = path.read_text(encoding='utf-8')
        assert "François Müller" in content

    def test_vcard_with_very_long_name(self, contact_service):
        """Test vCard with very long name"""
        long_name = "A" * 100 + " " + "B" * 100
        path = contact_service.create_vcard(name=long_name)

        assert path is not None
        assert path.exists()

    def test_vcard_overwrite_same_name(self, contact_service, temp_contact_dir):
        """Test creating vCard with same name overwrites"""
        path1 = contact_service.create_vcard("John Doe", role="Engineer")
        path2 = contact_service.create_vcard("John Doe", role="Manager")

        # Should be same file (overwritten)
        assert path1 == path2

        # Should only have one file
        matching_files = list(temp_contact_dir.glob("john-doe.vcf"))
        assert len(matching_files) == 1

        # Should have new role
        content = path2.read_text()
        assert "TITLE:Manager" in content

    def test_output_dir_creation(self, temp_contact_dir):
        """Test output directory is created if it doesn't exist"""
        non_existent = temp_contact_dir / "subdir" / "contacts"
        service = ContactService(output_dir=non_existent)

        assert non_existent.exists()
        assert non_existent.is_dir()

    def test_parse_vcard_with_sources(self, contact_service):
        """Test parsing vCard with document sources"""
        # Create vCard with sources
        path = contact_service.create_vcard(
            name="John Doe",
            document_sources=["doc1.pdf", "doc2.pdf"]
        )

        # Parse it
        data = contact_service._parse_vcard(path)

        assert "document_sources" in data
        assert len(data["document_sources"]) == 2
        # Sources may have escape characters, check they contain the filenames
        sources_str = " ".join(data["document_sources"])
        assert "doc1.pdf" in sources_str
        assert "doc2.pdf" in sources_str

    def test_parse_vcard_with_many_sources_truncated(self, contact_service):
        """Test parsing vCard with truncated source list"""
        sources = [f"doc{i}.pdf" for i in range(10)]
        path = contact_service.create_vcard(
            name="John Doe",
            document_sources=sources
        )

        # Parse it
        data = contact_service._parse_vcard(path)

        # Should have parsed 3 sources (before truncation)
        assert "document_sources" in data
        assert len(data["document_sources"]) == 3

    def test_empty_organizations_list(self, contact_service):
        """Test batch creation with empty organizations"""
        people = ["John Doe"]
        paths = contact_service.create_vcards_from_metadata(
            people=people,
            organizations=[]
        )

        assert len(paths) == 1

    def test_organization_mapping_returns_empty(self, contact_service):
        """Test organization mapping with no orgs"""
        mapping = contact_service._infer_organization_mapping(
            people=["John Doe"],
            organizations=None
        )

        assert mapping == {}
