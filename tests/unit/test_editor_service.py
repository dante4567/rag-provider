"""
Unit tests for EditorService

Tests the LLM-as-editor patch generation service.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.services.editor_service import EditorService


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing"""
    service = Mock()
    service.call_llm = AsyncMock()
    return service


@pytest.fixture
def editor_service(mock_llm_service):
    """Create EditorService instance"""
    return EditorService(mock_llm_service)


@pytest.mark.asyncio
async def test_generate_patch_valid_json(editor_service, mock_llm_service):
    """Test patch generation with valid JSON response"""
    # Mock LLM response
    mock_llm_service.call_llm.return_value = (
        '{"add": {"entities.technologies": ["Python"]}, "replace": {"summary.tl_dr": "New summary"}, "remove": []}',
        0.0001,
        "groq/llama-3.1-8b-instant"
    )

    current_metadata = {
        "summary": {"tl_dr": "Old summary"},
        "entities": {"people": [], "organizations": []}
    }

    patch = await editor_service.generate_patch(
        current_metadata=current_metadata,
        critic_suggestions="Add technologies, improve summary",
        body_text="Python programming guide",
        controlled_vocab={"topics": ["tech/programming"]}
    )

    assert "add" in patch
    assert "replace" in patch
    assert "remove" in patch
    assert patch["add"]["entities.technologies"] == ["Python"]
    assert patch["replace"]["summary.tl_dr"] == "New summary"


@pytest.mark.asyncio
async def test_generate_patch_with_markdown_wrapper(editor_service, mock_llm_service):
    """Test extraction from markdown code blocks"""
    # Mock LLM response with markdown wrapper
    mock_llm_service.call_llm.return_value = (
        '```json\n{"add": {}, "replace": {"title": "Updated Title"}, "remove": []}\n```',
        0.0001,
        "groq/llama-3.1-8b-instant"
    )

    current_metadata = {"title": "Old Title"}

    patch = await editor_service.generate_patch(
        current_metadata=current_metadata,
        critic_suggestions="Improve title",
        body_text="Document content",
        controlled_vocab={"topics": []}
    )

    assert patch["replace"]["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_generate_patch_forbidden_path_rejected(editor_service, mock_llm_service):
    """Test that patches touching forbidden paths return empty patch"""
    # Mock LLM trying to modify forbidden field
    mock_llm_service.call_llm.return_value = (
        '{"add": {}, "replace": {"id": "new-id", "source.path": "/new/path"}, "remove": []}',
        0.0001,
        "groq/llama-3.1-8b-instant"
    )

    current_metadata = {"id": "old-id", "source": {"path": "/old/path"}}

    patch = await editor_service.generate_patch(
        current_metadata=current_metadata,
        critic_suggestions="Update metadata",
        body_text="Content",
        controlled_vocab={"topics": []}
    )

    # Should return empty patch due to forbidden path violation
    assert patch == {"add": {}, "replace": {}, "remove": []}


@pytest.mark.asyncio
async def test_generate_patch_invalid_json_returns_empty(editor_service, mock_llm_service):
    """Test that invalid JSON returns empty patch"""
    # Mock LLM with invalid JSON
    mock_llm_service.call_llm.return_value = (
        'This is not JSON at all!',
        0.0001,
        "groq/llama-3.1-8b-instant"
    )

    current_metadata = {"title": "Test"}

    patch = await editor_service.generate_patch(
        current_metadata=current_metadata,
        critic_suggestions="Improve",
        body_text="Content",
        controlled_vocab={"topics": []}
    )

    # Should return empty patch on error
    assert patch == {"add": {}, "replace": {}, "remove": []}


def test_validate_patch_paths_allows_safe_paths(editor_service):
    """Test that safe paths are allowed"""
    patch = {
        "add": {"entities.technologies": ["Python"]},
        "replace": {"summary.tl_dr": "New"},
        "remove": ["topics[0]"]
    }

    # Should not raise
    editor_service._validate_patch_paths(patch)


def test_validate_patch_paths_rejects_forbidden(editor_service):
    """Test that forbidden paths are rejected"""
    patch = {
        "add": {},
        "replace": {"id": "new-id"},  # Forbidden!
        "remove": []
    }

    with pytest.raises(ValueError, match="❌ Patch cannot modify forbidden field"):
        editor_service._validate_patch_paths(patch)


def test_validate_patch_paths_rejects_forbidden_nested(editor_service):
    """Test that nested forbidden paths are rejected"""
    patch = {
        "add": {"source.content_hash": "abc123"},  # Forbidden nested path
        "replace": {},
        "remove": []
    }

    with pytest.raises(ValueError, match="❌ Patch cannot modify forbidden field"):
        editor_service._validate_patch_paths(patch)


def test_extract_json_patch_direct(editor_service):
    """Test direct JSON parsing"""
    response = '{"add": {}, "replace": {}, "remove": []}'
    patch = editor_service._extract_json_patch(response)

    assert "add" in patch
    assert "replace" in patch
    assert "remove" in patch


def test_extract_json_patch_from_code_block(editor_service):
    """Test extraction from markdown code block"""
    response = '''Here's the patch:
```json
{"add": {"new_field": "value"}, "replace": {}, "remove": []}
```
That should help!'''

    patch = editor_service._extract_json_patch(response)
    assert patch["add"]["new_field"] == "value"


def test_extract_json_patch_from_text(editor_service):
    """Test extraction when embedded in text"""
    response = 'The changes are: {"add": {}, "replace": {"title": "New"}, "remove": []} as shown above.'

    patch = editor_service._extract_json_patch(response)
    assert patch["replace"]["title"] == "New"


def test_extract_json_patch_invalid_raises(editor_service):
    """Test that invalid JSON raises ValueError"""
    response = 'No JSON here at all!'

    with pytest.raises(ValueError, match="No valid JSON found"):
        editor_service._extract_json_patch(response)


def test_validate_patch_structure_valid(editor_service):
    """Test validation of correct patch structure"""
    patch = {
        "add": {"field": "value"},
        "replace": {"other": "val"},
        "remove": ["field[0]"]
    }

    # Should not raise
    editor_service._validate_patch_structure(patch)


def test_validate_patch_structure_missing_keys(editor_service):
    """Test that completely missing keys raise ValueError"""
    patch = {}  # No add, replace, or remove keys at all

    with pytest.raises(ValueError, match="Patch must have at least one of"):
        editor_service._validate_patch_structure(patch)


def test_validate_patch_structure_wrong_types(editor_service):
    """Test that wrong value types raise ValueError"""
    patch = {
        "add": "not a dict",  # Should be dict
        "replace": {},
        "remove": []
    }

    with pytest.raises(ValueError, match="Patch 'add' must be a dict"):
        editor_service._validate_patch_structure(patch)


@pytest.mark.asyncio
async def test_build_editor_prompt_includes_context(editor_service, mock_llm_service):
    """Test that prompt includes all necessary context"""
    mock_llm_service.call_llm.return_value = (
        '{"add": {}, "replace": {}, "remove": []}',
        0.0001,
        "test"
    )

    current_metadata = {"title": "Test", "topics": ["tech"]}
    critic_suggestions = "Improve title clarity"
    body_text = "Document content here"
    controlled_vocab = {"topics": ["tech/programming", "tech/ai"], "projects": ["project-2025"]}

    await editor_service.generate_patch(
        current_metadata=current_metadata,
        critic_suggestions=critic_suggestions,
        body_text=body_text,
        controlled_vocab=controlled_vocab
    )

    # Check that call was made
    assert mock_llm_service.call_llm.called

    # Check prompt content
    call_args = mock_llm_service.call_llm.call_args
    prompt = call_args.kwargs['prompt']

    assert "tech/programming" in prompt  # Controlled vocab included
    assert "project-2025" in prompt
    assert "Improve title clarity" in prompt  # Critic suggestions included
    assert "Document content" in prompt  # Body text included
    assert '"title": "Test"' in prompt  # Current metadata included


@pytest.mark.asyncio
async def test_generate_patch_uses_correct_model(editor_service, mock_llm_service):
    """Test that editor uses Groq for cheap, fast patches"""
    mock_llm_service.call_llm.return_value = (
        '{"add": {}, "replace": {}, "remove": []}',
        0.0001,
        "groq/llama-3.1-8b-instant"
    )

    await editor_service.generate_patch(
        current_metadata={},
        critic_suggestions="Test",
        body_text="Content",
        controlled_vocab={"topics": []}
    )

    # Verify correct model was used
    call_args = mock_llm_service.call_llm.call_args
    assert call_args.kwargs['model_id'] == "groq/llama-3.1-8b-instant"
    assert call_args.kwargs['temperature'] == 0.0  # Deterministic
    assert call_args.kwargs['max_tokens'] == 1000
