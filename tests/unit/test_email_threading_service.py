"""
Unit tests for EmailThreadingService

Tests email threading functionality including:
- Subject normalization
- Email parsing
- Thread building
- Markdown generation
- Statistics
"""
import pytest
from datetime import datetime
from pathlib import Path
from src.services.email_threading_service import (
    EmailThreadingService,
    EmailMessage,
    EmailThread
)


# =============================================================================
# EmailThreadingService Tests
# =============================================================================

class TestEmailThreadingService:
    """Test the EmailThreadingService class"""

    @pytest.fixture
    def service(self):
        """Create EmailThreadingService instance"""
        return EmailThreadingService()

    @pytest.fixture
    def sample_messages(self):
        """Create sample email messages"""
        return [
            EmailMessage(
                message_id="<msg1@example.com>",
                subject="Meeting tomorrow",
                sender="alice@example.com",
                recipients=["bob@example.com"],
                date=datetime(2025, 10, 1, 10, 0),
                body="Can we meet tomorrow at 10am?",
                in_reply_to=None,
                references=[],
                attachments=[]
            ),
            EmailMessage(
                message_id="<msg2@example.com>",
                subject="Re: Meeting tomorrow",
                sender="bob@example.com",
                recipients=["alice@example.com"],
                date=datetime(2025, 10, 1, 11, 0),
                body="Yes, that works for me.",
                in_reply_to="<msg1@example.com>",
                references=["<msg1@example.com>"],
                attachments=[]
            ),
            EmailMessage(
                message_id="<msg3@example.com>",
                subject="RE: Meeting tomorrow",
                sender="alice@example.com",
                recipients=["bob@example.com"],
                date=datetime(2025, 10, 1, 12, 0),
                body="Great, see you then!",
                in_reply_to="<msg2@example.com>",
                references=["<msg1@example.com>", "<msg2@example.com>"],
                attachments=[]
            )
        ]

    def test_init(self, service):
        """Test EmailThreadingService initialization"""
        assert service is not None
        assert service.threads == {}

    def test_normalize_subject_removes_re(self, service):
        """Test that Re: prefixes are removed"""
        assert service.normalize_subject("Re: Meeting") == "meeting"
        assert service.normalize_subject("RE: Meeting") == "meeting"
        assert service.normalize_subject("re: Meeting") == "meeting"

    def test_normalize_subject_removes_fwd(self, service):
        """Test that Fwd: prefixes are removed"""
        assert service.normalize_subject("Fwd: Meeting") == "meeting"
        assert service.normalize_subject("FW: Meeting") == "meeting"
        assert service.normalize_subject("fw: Meeting") == "meeting"

    def test_normalize_subject_removes_whitespace(self, service):
        """Test whitespace normalization"""
        assert service.normalize_subject("  Meeting   tomorrow  ") == "meeting tomorrow"

    def test_normalize_subject_case_insensitive(self, service):
        """Test case normalization"""
        assert service.normalize_subject("Meeting Tomorrow") == "meeting tomorrow"
        assert service.normalize_subject("MEETING TOMORROW") == "meeting tomorrow"

    def test_build_threads_groups_by_subject(self, service, sample_messages):
        """Test that messages are grouped into threads by subject"""
        threads = service.build_threads(sample_messages)

        assert len(threads) == 1
        assert threads[0].message_count == 3

    def test_build_threads_sorts_by_date(self, service, sample_messages):
        """Test that messages within threads are sorted by date"""
        # Shuffle messages
        shuffled = [sample_messages[2], sample_messages[0], sample_messages[1]]

        threads = service.build_threads(shuffled)

        # Messages should be in chronological order
        assert threads[0].messages[0].date < threads[0].messages[1].date
        assert threads[0].messages[1].date < threads[0].messages[2].date

    def test_build_threads_extracts_participants(self, service, sample_messages):
        """Test participant extraction"""
        threads = service.build_threads(sample_messages)

        participants = threads[0].participants
        assert "alice@example.com" in participants
        assert "bob@example.com" in participants
        assert len(participants) == 2

    def test_build_threads_detects_attachments(self, service):
        """Test attachment detection"""
        messages = [
            EmailMessage(
                message_id="<msg1@example.com>",
                subject="Document",
                sender="alice@example.com",
                recipients=["bob@example.com"],
                date=datetime(2025, 10, 1, 10, 0),
                body="See attached",
                attachments=["document.pdf"]
            )
        ]

        threads = service.build_threads(messages)

        assert threads[0].has_attachments is True

    def test_build_threads_no_attachments(self, service, sample_messages):
        """Test when no attachments present"""
        threads = service.build_threads(sample_messages)

        assert threads[0].has_attachments is False

    def test_build_threads_multiple_separate_threads(self, service):
        """Test creating multiple separate threads"""
        messages = [
            EmailMessage(
                message_id="<msg1@example.com>",
                subject="Meeting",
                sender="alice@example.com",
                recipients=["bob@example.com"],
                date=datetime(2025, 10, 1, 10, 0),
                body="About meeting"
            ),
            EmailMessage(
                message_id="<msg2@example.com>",
                subject="Invoice",
                sender="alice@example.com",
                recipients=["bob@example.com"],
                date=datetime(2025, 10, 1, 11, 0),
                body="About invoice"
            )
        ]

        threads = service.build_threads(messages)

        assert len(threads) == 2
        assert threads[0].subject != threads[1].subject

    def test_generate_thread_markdown_structure(self, service, sample_messages):
        """Test markdown generation structure"""
        threads = service.build_threads(sample_messages)
        markdown = service.generate_thread_markdown(threads[0])

        # Check YAML frontmatter
        assert markdown.startswith("---")
        assert "id:" in markdown
        assert "source: email" in markdown
        assert "doc_type: correspondence.thread" in markdown

        # Check body
        assert "# Meeting tomorrow" in markdown
        assert "## Messages" in markdown

    def test_generate_thread_markdown_includes_messages(self, service, sample_messages):
        """Test that all messages are included in markdown"""
        threads = service.build_threads(sample_messages)
        markdown = service.generate_thread_markdown(threads[0])

        # Each message should be present
        assert "Can we meet tomorrow" in markdown
        assert "Yes, that works for me" in markdown
        assert "Great, see you then" in markdown

    def test_generate_thread_markdown_includes_metadata(self, service, sample_messages):
        """Test that thread metadata is included"""
        threads = service.build_threads(sample_messages)
        markdown = service.generate_thread_markdown(threads[0])

        # Check thread metadata
        assert "message_count: 3" in markdown
        assert "alice@example.com" in markdown
        assert "bob@example.com" in markdown

    def test_get_thread_statistics_basic(self, service, sample_messages):
        """Test basic statistics generation"""
        threads = service.build_threads(sample_messages)
        stats = service.get_thread_statistics(threads)

        assert stats["total_threads"] == 1
        assert stats["total_messages"] == 3
        assert stats["avg_messages_per_thread"] == 3.0
        assert stats["total_participants"] == 2

    def test_get_thread_statistics_empty(self, service):
        """Test statistics with no threads"""
        stats = service.get_thread_statistics([])

        assert stats == {}

    def test_get_thread_statistics_multiple_threads(self, service):
        """Test statistics with multiple threads"""
        messages1 = [
            EmailMessage(
                message_id="<msg1@example.com>",
                subject="Meeting",
                sender="alice@example.com",
                recipients=["bob@example.com"],
                date=datetime(2025, 10, 1, 10, 0),
                body="Message 1"
            ),
            EmailMessage(
                message_id="<msg2@example.com>",
                subject="Re: Meeting",
                sender="bob@example.com",
                recipients=["alice@example.com"],
                date=datetime(2025, 10, 1, 11, 0),
                body="Message 2"
            )
        ]

        messages2 = [
            EmailMessage(
                message_id="<msg3@example.com>",
                subject="Invoice",
                sender="charlie@example.com",
                recipients=["alice@example.com"],
                date=datetime(2025, 10, 2, 10, 0),
                body="Message 3"
            )
        ]

        threads = service.build_threads(messages1 + messages2)
        stats = service.get_thread_statistics(threads)

        assert stats["total_threads"] == 2
        assert stats["total_messages"] == 3
        assert stats["total_participants"] == 3  # alice, bob, charlie


# =============================================================================
# EmailMessage Tests
# =============================================================================

class TestEmailMessage:
    """Test EmailMessage dataclass"""

    def test_email_message_creation(self):
        """Test creating EmailMessage"""
        msg = EmailMessage(
            message_id="<test@example.com>",
            subject="Test",
            sender="alice@example.com",
            recipients=["bob@example.com"],
            date=datetime(2025, 10, 1, 10, 0),
            body="Test message"
        )

        assert msg.message_id == "<test@example.com>"
        assert msg.subject == "Test"
        assert msg.sender == "alice@example.com"
        assert msg.recipients == ["bob@example.com"]
        assert msg.body == "Test message"

    def test_email_message_optional_fields(self):
        """Test EmailMessage with optional fields"""
        msg = EmailMessage(
            message_id="<test@example.com>",
            subject="Test",
            sender="alice@example.com",
            recipients=["bob@example.com"],
            date=datetime(2025, 10, 1, 10, 0),
            body="Test",
            in_reply_to="<previous@example.com>",
            references=["<ref1@example.com>", "<ref2@example.com>"],
            attachments=["file.pdf"]
        )

        assert msg.in_reply_to == "<previous@example.com>"
        assert len(msg.references) == 2
        assert len(msg.attachments) == 1


# =============================================================================
# EmailThread Tests
# =============================================================================

class TestEmailThread:
    """Test EmailThread dataclass"""

    def test_email_thread_creation(self):
        """Test creating EmailThread"""
        msg = EmailMessage(
            message_id="<test@example.com>",
            subject="Test",
            sender="alice@example.com",
            recipients=["bob@example.com"],
            date=datetime(2025, 10, 1, 10, 0),
            body="Test"
        )

        thread = EmailThread(
            thread_id="thread1",
            subject="Test",
            participants={"alice@example.com", "bob@example.com"},
            messages=[msg],
            start_date=datetime(2025, 10, 1, 10, 0),
            end_date=datetime(2025, 10, 1, 10, 0),
            message_count=1
        )

        assert thread.thread_id == "thread1"
        assert thread.message_count == 1
        assert len(thread.participants) == 2


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def service(self):
        return EmailThreadingService()

    def test_normalize_subject_empty(self, service):
        """Test normalizing empty subject"""
        assert service.normalize_subject("") == ""

    def test_normalize_subject_only_prefix(self, service):
        """Test subject with only Re: prefix"""
        assert service.normalize_subject("Re:") == ""
        assert service.normalize_subject("Re: ") == ""

    def test_build_threads_empty_list(self, service):
        """Test building threads from empty list"""
        threads = service.build_threads([])
        assert threads == []

    def test_build_threads_single_message(self, service):
        """Test thread with single message"""
        messages = [
            EmailMessage(
                message_id="<msg1@example.com>",
                subject="Single",
                sender="alice@example.com",
                recipients=["bob@example.com"],
                date=datetime(2025, 10, 1, 10, 0),
                body="Single message"
            )
        ]

        threads = service.build_threads(messages)

        assert len(threads) == 1
        assert threads[0].message_count == 1

    def test_build_threads_no_recipients(self, service):
        """Test message with no recipients"""
        messages = [
            EmailMessage(
                message_id="<msg1@example.com>",
                subject="Test",
                sender="alice@example.com",
                recipients=[],
                date=datetime(2025, 10, 1, 10, 0),
                body="Test"
            )
        ]

        threads = service.build_threads(messages)

        assert len(threads) == 1
        assert "alice@example.com" in threads[0].participants

    def test_generate_markdown_empty_body(self, service):
        """Test markdown generation with empty message body"""
        msg = EmailMessage(
            message_id="<test@example.com>",
            subject="Test",
            sender="alice@example.com",
            recipients=["bob@example.com"],
            date=datetime(2025, 10, 1, 10, 0),
            body=""
        )

        thread = EmailThread(
            thread_id="test",
            subject="Test",
            participants={"alice@example.com"},
            messages=[msg],
            start_date=msg.date,
            end_date=msg.date,
            message_count=1
        )

        markdown = service.generate_thread_markdown(thread)

        # Should still generate valid markdown
        assert "---" in markdown
        assert "# Test" in markdown

    def test_parse_email_file_nonexistent(self, service, tmp_path):
        """Test parsing nonexistent file"""
        result = service.parse_email_file("/nonexistent/file.eml")
        assert result is None
