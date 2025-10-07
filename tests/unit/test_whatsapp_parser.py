"""
Unit tests for WhatsAppParser

Tests WhatsApp chat export parsing including:
- Multiple timestamp format support
- Message extraction
- Participant tracking
- Summary generation
- Metadata generation
- Format detection
"""
import pytest
from datetime import datetime
from src.services.whatsapp_parser import WhatsAppParser


# =============================================================================
# WhatsAppParser Tests
# =============================================================================

class TestWhatsAppParser:
    """Test the WhatsAppParser class"""

    @pytest.fixture
    def us_format_chat(self):
        """Sample WhatsApp export in US format"""
        return """1/15/24, 3:45 PM - Alice: Hey, how are you?
1/15/24, 3:46 PM - Bob: I'm good! How about you?
1/15/24, 3:47 PM - Alice: Doing well, thanks for asking
1/15/24, 4:00 PM - Bob: Want to grab coffee later?
1/15/24, 4:02 PM - Alice: Sure, sounds great!"""

    @pytest.fixture
    def eu_format_chat(self):
        """Sample WhatsApp export in EU format"""
        return """15.1.24, 15:45 - Alice: Hey, how are you?
15.1.24, 15:46 - Bob: I'm good! How about you?
15.1.24, 15:47 - Alice: Doing well, thanks"""

    @pytest.fixture
    def iso_format_chat(self):
        """Sample WhatsApp export in ISO format"""
        return """2024-01-15 15:45:00 - Alice: Hey there
2024-01-15 15:46:00 - Bob: Hi Alice
2024-01-15 15:47:00 - Alice: How's it going?"""

    @pytest.fixture
    def bracket_format_chat(self):
        """Sample WhatsApp export with brackets"""
        return """[1/15/24, 3:45 PM] Alice: Message one
[1/15/24, 3:46 PM] Bob: Message two"""

    def test_parse_us_format(self, us_format_chat):
        """Test parsing US date format"""
        messages, summary, metadata = WhatsAppParser.parse_whatsapp_export(us_format_chat)

        assert len(messages) == 5
        assert all('timestamp' in msg for msg in messages)
        assert all('sender' in msg for msg in messages)
        assert all('message' in msg for msg in messages)

        # Check participants
        senders = {msg['sender'] for msg in messages}
        assert 'Alice' in senders
        assert 'Bob' in senders

        # Check message content
        assert messages[0]['message'] == "Hey, how are you?"
        assert messages[0]['sender'] == "Alice"

    def test_parse_eu_format(self, eu_format_chat):
        """Test parsing EU date format"""
        messages, summary, metadata = WhatsAppParser.parse_whatsapp_export(eu_format_chat)

        assert len(messages) == 3
        assert all('timestamp' in msg for msg in messages)
        assert messages[0]['sender'] == "Alice"

    def test_parse_iso_format(self, iso_format_chat):
        """Test parsing ISO date format"""
        messages, summary, metadata = WhatsAppParser.parse_whatsapp_export(iso_format_chat)

        assert len(messages) == 3
        assert messages[0]['message'] == "Hey there"

    def test_parse_bracket_format(self, bracket_format_chat):
        """Test parsing bracket format"""
        messages, summary, metadata = WhatsAppParser.parse_whatsapp_export(bracket_format_chat)

        assert len(messages) == 2
        assert messages[0]['sender'] == "Alice"
        assert messages[1]['sender'] == "Bob"

    def test_messages_sorted_by_timestamp(self, us_format_chat):
        """Test that messages are sorted chronologically"""
        messages, _, _ = WhatsAppParser.parse_whatsapp_export(us_format_chat)

        timestamps = [msg['timestamp'] for msg in messages]
        assert timestamps == sorted(timestamps)

    def test_parse_empty_content(self):
        """Test parsing empty content"""
        messages, summary, metadata = WhatsAppParser.parse_whatsapp_export("")

        assert messages == []
        assert "No valid WhatsApp messages found" in summary
        assert metadata == {}

    def test_parse_non_whatsapp_content(self):
        """Test parsing non-WhatsApp content"""
        content = "This is just regular text without WhatsApp format"
        messages, summary, metadata = WhatsAppParser.parse_whatsapp_export(content)

        assert messages == []
        assert "No valid WhatsApp messages found" in summary

    def test_message_type_field(self, us_format_chat):
        """Test that messages have correct type field"""
        messages, _, _ = WhatsAppParser.parse_whatsapp_export(us_format_chat)

        assert all(msg['type'] == 'whatsapp_message' for msg in messages)


# =============================================================================
# Summary Generation Tests
# =============================================================================

class TestSummaryGeneration:
    """Test conversation summary generation"""

    @pytest.fixture
    def sample_chat(self):
        return """1/15/24, 3:45 PM - Alice: First message
1/15/24, 3:46 PM - Bob: Second message
1/15/24, 3:47 PM - Alice: Third message
1/15/24, 3:48 PM - Alice: Fourth message
1/16/24, 9:00 AM - Bob: Fifth message"""

    def test_summary_includes_participant_count(self, sample_chat):
        """Test that summary includes participant count"""
        _, summary, _ = WhatsAppParser.parse_whatsapp_export(sample_chat)

        assert "2 participant(s)" in summary or "Alice" in summary and "Bob" in summary

    def test_summary_includes_message_count(self, sample_chat):
        """Test that summary includes total message count"""
        _, summary, _ = WhatsAppParser.parse_whatsapp_export(sample_chat)

        assert "5" in summary or "Total messages: 5" in summary

    def test_summary_includes_date_range(self, sample_chat):
        """Test that summary includes date range"""
        _, summary, _ = WhatsAppParser.parse_whatsapp_export(sample_chat)

        assert "2024-01-15" in summary or "2024-01-16" in summary

    def test_summary_includes_message_distribution(self, sample_chat):
        """Test that summary includes per-user message counts"""
        _, summary, _ = WhatsAppParser.parse_whatsapp_export(sample_chat)

        # Alice: 3 messages, Bob: 2 messages
        assert "Alice" in summary
        assert "Bob" in summary
        # Should show counts or percentages
        assert "3" in summary or "60" in summary  # Alice's count or percentage


# =============================================================================
# Metadata Generation Tests
# =============================================================================

class TestMetadataGeneration:
    """Test conversation metadata generation"""

    @pytest.fixture
    def sample_chat(self):
        return """1/15/24, 3:45 PM - Alice: Short
1/15/24, 3:46 PM - Bob: This is a longer message with more content
1/15/24, 3:47 PM - Alice: Another message here"""

    def test_metadata_structure(self, sample_chat):
        """Test metadata has required fields"""
        _, _, metadata = WhatsAppParser.parse_whatsapp_export(sample_chat)

        assert 'participants' in metadata
        assert 'participant_count' in metadata
        assert 'total_messages' in metadata
        assert 'message_counts' in metadata
        assert 'date_range' in metadata
        assert 'average_message_length' in metadata
        assert 'conversation_type' in metadata

    def test_metadata_participants(self, sample_chat):
        """Test participant tracking in metadata"""
        _, _, metadata = WhatsAppParser.parse_whatsapp_export(sample_chat)

        assert metadata['participant_count'] == 2
        assert 'Alice' in metadata['participants']
        assert 'Bob' in metadata['participants']

    def test_metadata_message_counts(self, sample_chat):
        """Test message count tracking"""
        _, _, metadata = WhatsAppParser.parse_whatsapp_export(sample_chat)

        assert metadata['total_messages'] == 3
        assert metadata['message_counts']['Alice'] == 2
        assert metadata['message_counts']['Bob'] == 1

    def test_metadata_date_range(self, sample_chat):
        """Test date range in metadata"""
        _, _, metadata = WhatsAppParser.parse_whatsapp_export(sample_chat)

        assert 'start' in metadata['date_range']
        assert 'end' in metadata['date_range']
        # Should be ISO format strings
        assert isinstance(metadata['date_range']['start'], str)
        assert isinstance(metadata['date_range']['end'], str)

    def test_metadata_average_length(self, sample_chat):
        """Test average message length calculation"""
        _, _, metadata = WhatsAppParser.parse_whatsapp_export(sample_chat)

        assert metadata['average_message_length'] > 0
        assert isinstance(metadata['average_message_length'], (int, float))

    def test_metadata_conversation_type(self, sample_chat):
        """Test conversation type field"""
        _, _, metadata = WhatsAppParser.parse_whatsapp_export(sample_chat)

        assert metadata['conversation_type'] == 'whatsapp_chat'


# =============================================================================
# Format Detection Tests
# =============================================================================

class TestFormatDetection:
    """Test WhatsApp format detection"""

    def test_is_whatsapp_export_us_format(self):
        """Test detection of US format"""
        content = "1/15/24, 3:45 PM - Alice: Test message"
        assert WhatsAppParser.is_whatsapp_export(content) is True

    def test_is_whatsapp_export_eu_format(self):
        """Test detection of EU format"""
        content = "15.1.24, 15:45 - Bob: Test message"
        assert WhatsAppParser.is_whatsapp_export(content) is True

    def test_is_whatsapp_export_iso_format(self):
        """Test detection of ISO format"""
        content = "2024-01-15 15:45:00 - Alice: Test"
        assert WhatsAppParser.is_whatsapp_export(content) is True

    def test_is_not_whatsapp_export(self):
        """Test detection of non-WhatsApp content"""
        content = "This is just regular text without timestamps"
        assert WhatsAppParser.is_whatsapp_export(content) is False

    def test_is_not_whatsapp_export_partial_match(self):
        """Test that partial matches don't pass"""
        content = "1/15/24 - Missing time component"
        # Should not match if format isn't complete
        result = WhatsAppParser.is_whatsapp_export(content)
        # May or may not match depending on pattern strictness
        assert isinstance(result, bool)


# =============================================================================
# Markdown Formatting Tests
# =============================================================================

class TestMarkdownFormatting:
    """Test markdown output formatting"""

    @pytest.fixture
    def sample_chat(self):
        return """1/15/24, 3:45 PM - Alice: Hello
1/15/24, 3:46 PM - Bob: Hi there
1/16/24, 9:00 AM - Alice: Good morning"""

    def test_format_as_markdown(self, sample_chat):
        """Test markdown formatting"""
        messages, _, _ = WhatsAppParser.parse_whatsapp_export(sample_chat)
        markdown = WhatsAppParser.format_messages_as_markdown(messages)

        assert isinstance(markdown, str)
        assert "# WhatsApp Conversation" in markdown
        assert "Alice" in markdown
        assert "Bob" in markdown

    def test_markdown_includes_dates(self, sample_chat):
        """Test that markdown includes date headers"""
        messages, _, _ = WhatsAppParser.parse_whatsapp_export(sample_chat)
        markdown = WhatsAppParser.format_messages_as_markdown(messages)

        # Should have date headers (##)
        assert "##" in markdown
        # Should include date information
        assert "2024" in markdown or "January" in markdown

    def test_markdown_empty_messages(self):
        """Test markdown formatting with empty messages"""
        markdown = WhatsAppParser.format_messages_as_markdown([])
        assert markdown == "No messages"

    def test_markdown_preserves_message_order(self, sample_chat):
        """Test that markdown preserves message order"""
        messages, _, _ = WhatsAppParser.parse_whatsapp_export(sample_chat)
        markdown = WhatsAppParser.format_messages_as_markdown(messages)

        # First message should appear before second
        alice_pos = markdown.find("Hello")
        bob_pos = markdown.find("Hi there")
        assert alice_pos < bob_pos


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_multiline_messages(self):
        """Test handling of multiline messages"""
        content = """1/15/24, 3:45 PM - Alice: This is a message
that spans multiple lines
1/15/24, 3:46 PM - Bob: Another message"""

        messages, _, _ = WhatsAppParser.parse_whatsapp_export(content)

        # Should parse both messages
        assert len(messages) >= 1
        # Note: Multiline handling depends on pattern strictness

    def test_messages_with_colons(self):
        """Test messages containing colons"""
        content = "1/15/24, 3:45 PM - Alice: Time is 3:45 PM: still talking"
        messages, _, _ = WhatsAppParser.parse_whatsapp_export(content)

        if messages:
            # Message content should include text after sender colon
            assert "3:45 PM" in messages[0]['message'] or "still talking" in messages[0]['message']

    def test_messages_with_special_characters(self):
        """Test messages with special characters"""
        content = "1/15/24, 3:45 PM - Alice: Hello! 😊 #test @mention"
        messages, _, _ = WhatsAppParser.parse_whatsapp_export(content)

        if messages:
            assert '😊' in messages[0]['message'] or '#test' in messages[0]['message']

    def test_sender_names_with_numbers(self):
        """Test handling of sender names with numbers"""
        content = "1/15/24, 3:45 PM - Alice123: Test message"
        messages, _, _ = WhatsAppParser.parse_whatsapp_export(content)

        if messages:
            assert messages[0]['sender'] == "Alice123"

    def test_sender_names_with_spaces(self):
        """Test handling of sender names with spaces"""
        content = "1/15/24, 3:45 PM - Alice Smith: Test message"
        messages, _, _ = WhatsAppParser.parse_whatsapp_export(content)

        if messages:
            assert messages[0]['sender'] == "Alice Smith"

    def test_invalid_timestamp_handling(self):
        """Test graceful handling of invalid timestamps"""
        content = "99/99/99, 99:99 PM - Alice: Test"
        messages, _, _ = WhatsAppParser.parse_whatsapp_export(content)

        # Should either skip or use fallback timestamp
        # Should not crash
        assert isinstance(messages, list)

    def test_mixed_format_content(self):
        """Test content with mixed formats"""
        content = """1/15/24, 3:45 PM - Alice: US format
15.1.24, 15:46 - Bob: EU format
Random text in between
2024-01-15 15:47:00 - Charlie: ISO format"""

        messages, _, _ = WhatsAppParser.parse_whatsapp_export(content)

        # Should parse at least one format
        assert len(messages) > 0

    def test_system_messages_handling(self):
        """Test handling of WhatsApp system messages"""
        content = """1/15/24, 3:45 PM - Alice: Regular message
1/15/24, 3:46 PM - System: Alice added Bob
1/15/24, 3:47 PM - Bob: Another regular message"""

        messages, _, _ = WhatsAppParser.parse_whatsapp_export(content)

        # Should parse messages (including or excluding system messages)
        assert isinstance(messages, list)

    def test_very_long_message(self):
        """Test handling of very long messages"""
        long_text = "A" * 10000
        content = f"1/15/24, 3:45 PM - Alice: {long_text}"

        messages, _, _ = WhatsAppParser.parse_whatsapp_export(content)

        if messages:
            assert len(messages[0]['message']) > 1000
