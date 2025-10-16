"""
Tests for EmailHandler - Critical path validation only

Focuses on proven functionality:
- Reply chain removal (tested with real German emails)
- Signature detection
- Metadata extraction
- Language detection
"""
import pytest
from src.services.document_type_handlers.email_handler import EmailHandler


@pytest.fixture
def handler():
    return EmailHandler()


def test_clean_email_high_retention(handler):
    """Clean emails should retain >95% of content"""
    text = "Project update: We're on track for March delivery. Testing is 80% complete."
    result = handler.preprocess(text, {})

    retention = len(result) / len(text)
    assert retention > 0.95
    assert "March delivery" in result


def test_reply_chain_removal(handler):
    """Reply chains with > markers should be removed"""
    text = """Thanks for the update.

> On Mon, Oct 16, 2025 Alice wrote:
> Can you review the proposal?

Let me know if you need anything."""

    result = handler.preprocess(text, {})

    assert "> On Mon" not in result
    assert "> Can you review" not in result
    assert "Thanks for the update" in result


def test_german_language_detection(handler):
    """German language detection works"""
    text = "Das Projekt läuft gut und wir haben die Testphase abgeschlossen."
    lang = handler.detect_language(text)
    assert lang == 'de'


def test_signature_removal(handler):
    """Standard -- signatures should be removed"""
    text = """Meeting is at 2pm.

--
John Smith
Engineering Manager"""

    result = handler.preprocess(text, {})

    assert "Engineering Manager" not in result
    assert "Meeting is at 2pm" in result


def test_action_item_detection(handler):
    """Action items should be detected"""
    text = "Please review the document by Friday. TODO: Update budget."
    metadata = handler.extract_metadata(text, {})

    assert metadata.get('has_action_items') is True


def test_urgency_detection(handler):
    """Urgent keywords should be detected"""
    text = "URGENT: Server is down. Need immediate action."
    metadata = handler.extract_metadata(text, {})

    assert metadata.get('is_urgent') is True


def test_thread_chunking_strategy(handler):
    """Thread emails should use 'thread' chunking"""
    metadata = {'thread_id': 'abc123', 'in_reply_to': '<msg@example.com>'}
    strategy = handler.get_chunking_strategy(metadata)
    assert strategy == 'thread'


def test_message_chunking_strategy(handler):
    """Single emails should use 'message' chunking"""
    metadata = {'subject': 'Project Update'}
    strategy = handler.get_chunking_strategy(metadata)
    assert strategy == 'message'


def test_thread_summary_prompt(handler):
    """Thread summary prompts focus on outcome"""
    metadata = {
        'sender': 'alice@example.com',
        'subject': 'Budget Discussion',
        'in_reply_to': '<msg123>'
    }
    prompt = handler.get_summary_prompt("test", metadata)

    assert 'thread' in prompt.lower()
    assert 'outcome' in prompt.lower()


def test_whitespace_normalization(handler):
    """Excessive whitespace should be normalized"""
    text = "Line 1\n\n\n\n\nLine 2"
    result = handler.preprocess(text, {})

    assert '\n\n\n' not in result
    assert 'Line 1' in result
    assert 'Line 2' in result


def test_empty_text_handling(handler):
    """Empty text should not crash"""
    result = handler.preprocess("", {})
    assert result == ""


def test_english_language_detection(handler):
    """English language detection works"""
    text = "The project is going well and we have completed the testing phase."
    lang = handler.detect_language(text)
    assert lang == 'en'


def test_mobile_signature_removal(handler):
    """Mobile device signatures should be removed"""
    text = """Looks good!

Sent from my iPhone"""

    result = handler.preprocess(text, {})
    assert "Sent from my iPhone" not in result


def test_high_quote_ratio_detection(handler):
    """Heavily quoted emails should be flagged"""
    cleaned_text = "Yes"
    metadata = handler.extract_metadata(cleaned_text, {'original_length': 1000})

    assert metadata.get('high_quote_ratio') is True


def test_small_thread_grouping(handler):
    """Small threads should be grouped"""
    chunks = ["chunk1", "chunk2", "chunk3"]
    metadata = {'thread_id': 'thread123'}

    should_group = handler.should_chunk_together(chunks, metadata)
    assert should_group is True
