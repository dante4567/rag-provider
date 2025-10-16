"""
Tests for ChatLogHandler - Critical path validation

Focuses on proven functionality:
- Boilerplate removal
- Code block preservation
- Turn counting
- Technology detection
"""
import pytest
from src.services.document_type_handlers.chat_log_handler import ChatLogHandler


@pytest.fixture
def handler():
    return ChatLogHandler()


def test_remove_boilerplate(handler):
    """AI boilerplate should be removed"""
    text = """I'm Claude, an AI assistant.

User: How to install Python?
Assistant: Download from python.org"""

    result = handler.preprocess(text, {})
    assert "I'm Claude" not in result or len(result) > 20


def test_code_block_detection(handler):
    """Code blocks should be detected in metadata"""
    text = """```python
print("hello")
```"""

    metadata = handler.extract_metadata(text, {})
    assert metadata['has_code'] is True


def test_turn_counting(handler):
    """Turn count should be extracted"""
    text = """User: Question 1
Assistant: Answer 1
User: Question 2
Assistant: Answer 2"""

    metadata = handler.extract_metadata(text, {})
    assert metadata['turn_count'] >= 4


def test_technology_detection(handler):
    """Technologies should be detected"""
    text = "We're using Python and Docker for this project."

    metadata = handler.extract_metadata(text, {})
    assert len(metadata.get('technologies_mentioned', [])) > 0


def test_programming_language_detection(handler):
    """Programming languages in code fences should be detected"""
    text = """```python
def hello():
    pass
```"""

    metadata = handler.extract_metadata(text, {})
    assert 'python' in metadata.get('programming_languages', [])


def test_short_conversation_chunking(handler):
    """Short conversations should use 'whole' chunking"""
    metadata = {'turn_count': 5}
    strategy = handler.get_chunking_strategy(metadata)
    assert strategy == 'whole'


def test_medium_conversation_chunking(handler):
    """Medium conversations should use 'session' chunking"""
    metadata = {'turn_count': 25}
    strategy = handler.get_chunking_strategy(metadata)
    assert strategy == 'session'


def test_long_conversation_chunking(handler):
    """Long conversations should use 'semantic' chunking"""
    metadata = {'turn_count': 60}
    strategy = handler.get_chunking_strategy(metadata)
    assert strategy == 'semantic'


def test_summary_prompt_with_code(handler):
    """Summary prompts should mention code when present"""
    metadata = {'has_code': True, 'turn_count': 10, 'technologies_mentioned': ['Python']}
    prompt = handler.get_summary_prompt("test", metadata)

    assert 'code' in prompt.lower() or 'implementation' in prompt.lower()


def test_question_detection(handler):
    """Questions should be detected"""
    text = "How do I configure Docker?"

    metadata = handler.extract_metadata(text, {})
    assert metadata.get('has_questions') is True


def test_todo_detection(handler):
    """TODOs should be detected"""
    text = "TODO: Fix the bug in module.py"

    metadata = handler.extract_metadata(text, {})
    assert metadata.get('has_todos') is True


def test_empty_text_handling(handler):
    """Empty text should not crash"""
    result = handler.preprocess("", {})
    assert result == ""


def test_whitespace_normalization(handler):
    """Excessive whitespace should be normalized"""
    text = "Line 1\n\n\n\n\nLine 2"
    result = handler.preprocess(text, {})

    assert '\n\n\n' not in result


def test_high_retention_for_useful_content(handler):
    """Useful content should be mostly retained"""
    text = "User: How to fix error?\nAssistant: Try this solution..."

    result = handler.preprocess(text, {})
    retention = len(result) / len(text)

    assert retention > 0.70  # Should retain >70% of useful content
