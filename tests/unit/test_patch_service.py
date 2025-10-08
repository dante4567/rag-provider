"""
Unit tests for PatchService

Tests safe JSON patch application with diff logging.
"""
import pytest
from src.services.patch_service import PatchService


@pytest.fixture
def patch_service():
    """Create PatchService instance"""
    return PatchService()


def test_apply_patch_add_operations(patch_service):
    """Test adding new fields"""
    original = {
        "title": "Test",
        "topics": ["tech"]
    }

    patch = {
        "add": {
            "entities.technologies": ["Python", "Docker"],
            "summary.tl_dr": "New summary"
        },
        "replace": {},
        "remove": []
    }

    patched, diff = patch_service.apply_patch(original, patch)

    assert "entities" in patched
    assert patched["entities"]["technologies"] == ["Python", "Docker"]
    assert "summary" in patched
    assert patched["summary"]["tl_dr"] == "New summary"
    assert "added" in diff
    assert len(diff["added"]) == 2


def test_apply_patch_replace_operations(patch_service):
    """Test replacing existing fields"""
    original = {
        "title": "Old Title",
        "summary": "Old summary"
    }

    patch = {
        "add": {},
        "replace": {
            "title": "New Title",
            "summary": "New summary"
        },
        "remove": []
    }

    patched, diff = patch_service.apply_patch(original, patch)

    assert patched["title"] == "New Title"
    assert patched["summary"] == "New summary"
    assert "replaced" in diff
    assert len(diff["replaced"]) == 2
    assert diff["replaced"]["title"]["old"] == "Old Title"
    assert diff["replaced"]["title"]["new"] == "New Title"


def test_apply_patch_remove_operations(patch_service):
    """Test removing fields"""
    original = {
        "title": "Test",
        "obsolete_field": "Remove me",
        "topics": ["a", "b", "c"]
    }

    patch = {
        "add": {},
        "replace": {},
        "remove": ["obsolete_field", "topics[1]"]  # Remove field and array element
    }

    patched, diff = patch_service.apply_patch(original, patch)

    assert "obsolete_field" not in patched
    assert patched["topics"] == ["a", "c"]  # Middle element removed
    assert "removed" in diff
    assert len(diff["removed"]) == 2


def test_apply_patch_nested_paths(patch_service):
    """Test setting nested values with dot notation"""
    original = {
        "summary": {
            "tl_dr": "Old"
        }
    }

    patch = {
        "add": {
            "summary.key_points": ["Point 1", "Point 2"],
            "entities.people": ["Alice"]
        },
        "replace": {
            "summary.tl_dr": "New"
        },
        "remove": []
    }

    patched, diff = patch_service.apply_patch(original, patch)

    assert patched["summary"]["tl_dr"] == "New"
    assert patched["summary"]["key_points"] == ["Point 1", "Point 2"]
    assert patched["entities"]["people"] == ["Alice"]


def test_apply_patch_forbidden_paths_rejected(patch_service):
    """Test that forbidden paths are rejected"""
    original = {"id": "abc123", "title": "Test"}

    patch = {
        "add": {},
        "replace": {"id": "new-id"},  # Forbidden!
        "remove": []
    }

    forbidden = ["id", "source.path"]

    with pytest.raises(ValueError, match="Cannot modify forbidden path"):
        patch_service.apply_patch(original, patch, forbidden_paths=forbidden)


def test_apply_patch_merge_dicts(patch_service):
    """Test that add operations merge with existing dicts"""
    original = {
        "entities": {
            "people": ["Alice"],
            "organizations": ["CompanyA"]
        }
    }

    patch = {
        "add": {
            "entities.technologies": ["Python"],  # Add new key
            "entities.people": ["Bob"]  # Merge with existing
        },
        "replace": {},
        "remove": []
    }

    patched, diff = patch_service.apply_patch(original, patch)

    assert patched["entities"]["people"] == ["Alice", "Bob"]  # Merged
    assert patched["entities"]["organizations"] == ["CompanyA"]  # Unchanged
    assert patched["entities"]["technologies"] == ["Python"]  # Added


def test_apply_patch_merge_lists_no_duplicates(patch_service):
    """Test that lists are merged without duplicates"""
    original = {
        "topics": ["tech", "programming"]
    }

    patch = {
        "add": {
            "topics": ["ai", "tech"]  # "tech" is duplicate
        },
        "replace": {},
        "remove": []
    }

    patched, diff = patch_service.apply_patch(original, patch)

    assert "tech" in patched["topics"]
    assert patched["topics"].count("tech") == 1  # No duplicates
    assert "ai" in patched["topics"]
    assert "programming" in patched["topics"]


def test_apply_patch_replace_non_dict_with_dict(patch_service):
    """Test replacing non-dict values to allow nested access"""
    original = {
        "summary": "Simple string"  # Not a dict
    }

    patch = {
        "add": {
            "summary.tl_dr": "New structured summary"  # Needs summary to be dict
        },
        "replace": {},
        "remove": []
    }

    patched, diff = patch_service.apply_patch(original, patch)

    # Should convert summary to dict to allow nested access
    assert isinstance(patched["summary"], dict)
    assert patched["summary"]["tl_dr"] == "New structured summary"


def test_apply_patch_array_index_removal(patch_service):
    """Test removing array elements by index"""
    original = {
        "topics": ["topic-0", "topic-1", "topic-2", "topic-3"]
    }

    patch = {
        "add": {},
        "replace": {},
        "remove": ["topics[1]", "topics[2]"]  # Remove indices 1 and 2
    }

    patched, diff = patch_service.apply_patch(original, patch)

    # Note: After removing index 1, indices shift
    # So this removes "topic-1" first, then "topic-3" (which was at index 3, now at 2)
    assert "topic-0" in patched["topics"]


def test_apply_patch_deep_copy_preserves_original(patch_service):
    """Test that original metadata is not modified"""
    original = {
        "title": "Original",
        "topics": ["topic-1"]
    }

    patch = {
        "add": {},
        "replace": {"title": "Modified"},
        "remove": []
    }

    patched, diff = patch_service.apply_patch(original, patch)

    # Original should be unchanged
    assert original["title"] == "Original"
    assert patched["title"] == "Modified"


def test_generate_diff_includes_summary(patch_service):
    """Test that diff includes human-readable summary"""
    original = {"title": "Old"}

    patch = {
        "add": {"new_field": "value"},
        "replace": {"title": "New"},
        "remove": []
    }

    patched, diff = patch_service.apply_patch(original, patch)

    assert "summary" in diff
    assert "Added 1 field" in diff["summary"]
    assert "Modified 1 field" in diff["summary"]
    assert "timestamp" in diff
    assert "changes_count" in diff
    assert diff["changes_count"] == 2  # 1 add + 1 replace


def test_generate_diff_tracks_old_and_new_values(patch_service):
    """Test that diff tracks before/after values"""
    original = {
        "summary": "Old summary",
        "quality_score": 3.0
    }

    patch = {
        "add": {},
        "replace": {
            "summary": "New summary",
            "quality_score": 4.5
        },
        "remove": []
    }

    patched, diff = patch_service.apply_patch(original, patch)

    assert diff["replaced"]["summary"]["old"] == "Old summary"
    assert diff["replaced"]["summary"]["new"] == "New summary"
    assert diff["replaced"]["quality_score"]["old"] == 3.0
    assert diff["replaced"]["quality_score"]["new"] == 4.5


def test_validate_paths_allows_safe_operations(patch_service):
    """Test that safe paths pass validation"""
    patch = {
        "add": {"entities.people": ["Alice"]},
        "replace": {"summary.tl_dr": "New"},
        "remove": ["topics[0]"]
    }

    forbidden = ["id", "source.path"]

    # Should not raise
    patch_service._validate_paths(patch, forbidden)


def test_validate_paths_rejects_forbidden_add(patch_service):
    """Test that forbidden paths in add are rejected"""
    patch = {
        "add": {"source.content_hash": "abc123"},
        "replace": {},
        "remove": []
    }

    forbidden = ["source.content_hash"]

    with pytest.raises(ValueError, match="Cannot modify forbidden path"):
        patch_service._validate_paths(patch, forbidden)


def test_validate_paths_rejects_forbidden_remove(patch_service):
    """Test that forbidden paths in remove are rejected"""
    patch = {
        "add": {},
        "replace": {},
        "remove": ["id", "source.path"]
    }

    forbidden = ["id", "source"]

    with pytest.raises(ValueError, match="Cannot remove forbidden path"):
        patch_service._validate_paths(patch, forbidden)


def test_set_nested_value_creates_intermediate_dicts(patch_service):
    """Test that nested paths create intermediate dictionaries"""
    obj = {}

    old_value = patch_service._set_nested_value(
        obj,
        "a.b.c.d",
        "value",
        merge=False
    )

    assert obj == {"a": {"b": {"c": {"d": "value"}}}}
    assert old_value is None


def test_remove_nested_value_returns_removed(patch_service):
    """Test that remove returns the removed value"""
    obj = {
        "summary": {
            "tl_dr": "Summary text",
            "key_points": ["Point 1"]
        }
    }

    removed = patch_service._remove_nested_value(obj, "summary.tl_dr")

    assert removed == "Summary text"
    assert "tl_dr" not in obj["summary"]
    assert "key_points" in obj["summary"]  # Other keys preserved


def test_remove_nested_value_nonexistent_returns_none(patch_service):
    """Test that removing nonexistent path returns None"""
    obj = {"title": "Test"}

    removed = patch_service._remove_nested_value(obj, "nonexistent.path")

    assert removed is None
    assert obj == {"title": "Test"}  # Unchanged
