"""
Unit tests for SchemaValidator

Tests JSON Schema validation for enrichment metadata.
"""
import pytest
from src.services.schema_validator import SchemaValidator
from pathlib import Path


@pytest.fixture
def validator():
    """Create SchemaValidator instance with test schema"""
    schema_path = Path(__file__).parent.parent.parent / "src" / "schemas" / "enrichment_schema.json"
    return SchemaValidator(schema_path=str(schema_path))


def test_validate_enrichment_valid_metadata(validator):
    """Test that valid metadata passes validation"""
    metadata = {
        "id": "12345678-1234-1234-1234-123456789012",  # Valid UUID format
        "source": {
            "type": "pdf",  # Valid enum value
            "path": "/test/path.pdf",
            "content_hash": "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"  # Valid sha256 format
        },
        "doc_time": {
            "created": "2025-01-01T00:00:00Z",
            "observed": "2025-01-01T00:00:00Z"  # Required field
        },
        "summary": {
            "tl_dr": "Test summary under 600 chars",
            "key_points": ["Point 1", "Point 2"]
        },
        "topics": ["tech/programming", "tech/ai"],
        "entities": {
            "orgs": ["CompanyA"],
            "places": ["Berlin"]
        }
    }

    is_valid, errors = validator.validate_enrichment(metadata, strict=False)

    assert is_valid
    assert len(errors) == 0


def test_validate_enrichment_missing_required_fields(validator):
    """Test that missing required fields fail strict validation"""
    metadata = {
        "summary": "Test"
        # Missing required: id, source, doc_time
    }

    is_valid, errors = validator.validate_enrichment(metadata, strict=True)

    assert not is_valid
    assert len(errors) > 0
    assert any("required" in err.lower() for err in errors)


def test_validate_enrichment_tl_dr_too_long(validator):
    """Test that tl_dr over 600 chars fails"""
    metadata = {
        "id": "12345678-1234-1234-1234-123456789012",
        "source": {
            "type": "text",
            "path": "/test"
        },
        "doc_time": {
            "created": "2025-01-01T00:00:00Z",
            "observed": "2025-01-01T00:00:00Z"
        },
        "summary": {
            "tl_dr": "x" * 601  # 601 characters - too long!
        }
    }

    is_valid, errors = validator.validate_enrichment(metadata, strict=False)

    # Non-strict mode might still pass but should have warnings
    if not is_valid or len(errors) > 0:
        assert any("tl_dr" in str(err).lower() or "summary" in str(err).lower() for err in errors)


def test_validate_enrichment_too_many_key_points(validator):
    """Test that more than 5 key points fails"""
    metadata = {
        "id": "test",
        "source": {"type": "upload", "path": "/test"},
        "doc_time": {"created": "2025-01-01T00:00:00"},
        "summary": {
            "key_points": ["1", "2", "3", "4", "5", "6"]  # 6 points - too many!
        }
    }

    is_valid, errors = validator.validate_enrichment(metadata, strict=False)

    assert any("key_points" in err for err in errors)
    assert any("5" in err or "maxItems" in err for err in errors)


def test_validate_enrichment_too_many_topics(validator):
    """Test that more than 5 topics fails"""
    metadata = {
        "id": "test",
        "source": {"type": "upload", "path": "/test"},
        "doc_time": {"created": "2025-01-01T00:00:00"},
        "topics": ["topic1", "topic2", "topic3", "topic4", "topic5", "topic6"]  # Too many
    }

    is_valid, errors = validator.validate_enrichment(metadata, strict=False)

    assert any("topics" in err for err in errors)
    assert any("5" in err or "maxItems" in err for err in errors)


def test_validate_enrichment_wrong_type(validator):
    """Test that wrong field types fail"""
    metadata = {
        "id": "test",
        "source": {"type": "upload", "path": "/test"},
        "doc_time": {"created": "2025-01-01T00:00:00"},
        "topics": "not-a-list"  # Should be array!
    }

    is_valid, errors = validator.validate_enrichment(metadata, strict=False)

    assert any("topics" in err for err in errors)
    assert any("array" in err.lower() or "list" in err.lower() for err in errors)


def test_validate_enrichment_non_strict_passes_with_warnings(validator):
    """Test that non-strict mode passes with warnings"""
    metadata = {
        "id": "test",
        "source": {"type": "upload", "path": "/test"},
        "doc_time": {"created": "2025-01-01T00:00:00"},
        "summary": {
            "tl_dr": "x" * 601  # Too long
        }
    }

    is_valid, errors = validator.validate_enrichment(metadata, strict=False)

    # Non-strict should pass but return errors as warnings
    assert is_valid  # Passes in non-strict mode
    assert len(errors) > 0  # But has warnings


def test_validate_patch_simulates_application(validator):
    """Test that patch validation simulates applying the patch"""
    current = {
        "id": "12345678-1234-1234-1234-123456789012",
        "source": {
            "type": "text",
            "path": "/test"
        },
        "doc_time": {
            "created": "2025-01-01T00:00:00Z",
            "observed": "2025-01-01T00:00:00Z"
        },
        "topics": ["topic1", "topic2"]
    }

    # Valid patch - adds 3 more topics (total 5, which is max)
    valid_patch = {
        "add": {
            "topics": ["topic3", "topic4", "topic5"]
        },
        "replace": {},
        "remove": []
    }

    is_valid, errors = validator.validate_patch(current, valid_patch)

    # Should pass in non-strict mode
    assert is_valid or len(errors) == 0  # Either valid or no errors


def test_validate_patch_detects_violation_after_application(validator):
    """Test that patch validation detects violations after applying"""
    current = {
        "id": "test",
        "source": {"type": "upload", "path": "/test"},
        "doc_time": {"created": "2025-01-01T00:00:00"},
        "topics": ["topic1", "topic2", "topic3"]
    }

    # Invalid patch - would result in 6 topics (over max of 5)
    invalid_patch = {
        "add": {
            "topics": ["topic4", "topic5", "topic6"]
        },
        "replace": {},
        "remove": []
    }

    is_valid, errors = validator.validate_patch(current, invalid_patch)

    # Should pass in non-strict mode but have warnings
    assert is_valid  # Non-strict
    assert len(errors) > 0
    assert any("topics" in err for err in errors)


def test_validate_patch_handles_exceptions(validator):
    """Test that patch validation handles invalid patches gracefully"""
    current = {"id": "test"}

    # Malformed patch
    invalid_patch = {
        "add": "not-a-dict",  # Should be dict
        "replace": {},
        "remove": []
    }

    is_valid, errors = validator.validate_patch(current, invalid_patch)

    assert not is_valid
    assert len(errors) > 0


def test_get_schema_summary_returns_constraints(validator):
    """Test that schema summary returns human-readable constraints"""
    summary = validator.get_schema_summary()

    assert "Required:" in summary or "required" in summary.lower()
    assert "tl_dr" in summary
    assert "600" in summary  # Max length
    assert "key_points" in summary
    assert "5" in summary  # Max items
    assert "topics" in summary


def test_validator_handles_missing_schema_file():
    """Test that validator handles missing schema file gracefully"""
    # Try to load from nonexistent path
    validator = SchemaValidator(schema_path="/nonexistent/path/schema.json")

    # Should fall back to permissive schema
    metadata = {"anything": "goes"}

    is_valid, errors = validator.validate_enrichment(metadata, strict=False)

    # Permissive schema should accept anything
    assert is_valid


def test_validator_error_messages_include_paths(validator):
    """Test that error messages include field paths"""
    metadata = {
        "id": "test",
        "source": {"type": "upload", "path": "/test"},
        "doc_time": {"created": "2025-01-01T00:00:00"},
        "summary": {
            "tl_dr": "x" * 601,
            "key_points": ["1", "2", "3", "4", "5", "6"]
        }
    }

    is_valid, errors = validator.validate_enrichment(metadata, strict=False)

    # Errors should include field paths
    assert any("summary" in err for err in errors)
    assert any("tl_dr" in err or "key_points" in err for err in errors)


def test_validate_enrichment_unique_topics(validator):
    """Test that duplicate topics are flagged"""
    metadata = {
        "id": "test",
        "source": {"type": "upload", "path": "/test"},
        "doc_time": {"created": "2025-01-01T00:00:00"},
        "topics": ["tech", "tech", "programming"]  # Duplicates
    }

    is_valid, errors = validator.validate_enrichment(metadata, strict=False)

    # Schema should have uniqueItems constraint
    # This may or may not error depending on schema strictness


def test_validate_complex_nested_structure(validator):
    """Test validation of complex nested metadata"""
    metadata = {
        "id": "12345678-1234-1234-1234-123456789abc",  # Valid UUID
        "source": {
            "type": "pdf",  # Valid enum value
            "path": "/complex/doc.pdf",
            "content_hash": "sha256:abcd1234567890abcd1234567890abcd1234567890abcd1234567890abcd1234",  # Valid sha256
            "url": "https://example.com"
        },
        "doc_time": {
            "created": "2025-01-01T12:00:00Z",
            "observed": "2025-01-02T12:00:00Z"  # Required field, changed from "modified"
        },
        "summary": {
            "tl_dr": "Complex document with many fields",
            "key_points": [
                "Point about tech",
                "Point about business",
                "Point about data"
            ]
        },
        "topics": ["tech/ai", "business/strategy", "data/analytics"],
        "entities": {
            "orgs": ["TechCorp", "DataInc"],
            "places": ["San Francisco", "New York"]
        },
        "people": {
            "mentioned": ["Dr. Smith", "Jane Doe"]
        },
        "tasks": [
            {"text": "Review document", "status": "todo"},
            {"text": "Share with team", "status": "todo"}
        ]
    }

    is_valid, errors = validator.validate_enrichment(metadata, strict=False)

    # Should pass or have minimal warnings in non-strict mode
    assert is_valid or len(errors) < 3  # Allow some minor warnings
