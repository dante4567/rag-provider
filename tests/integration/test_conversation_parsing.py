"""
Integration tests for conversation-aware parsing

Tests real export files (WhatsApp, ChatGPT, Claude)
"""
import pytest
from pathlib import Path
from src.services.whatsapp_parser import WhatsAppParser
from src.services.llm_chat_parser import LLMChatParser


class TestWhatsAppParsing:
    """Test WhatsApp parsing with real export files"""

    def test_whatsapp_us_format(self):
        """Test US format (MM/DD/YY, 12-hour with AM/PM)"""
        file_path = Path("tests/data/exports/whatsapp_us_format.txt")
        with open(file_path) as f:
            content = f.read()

        assert WhatsAppParser.is_whatsapp_export(content)
        messages, summary, metadata = WhatsAppParser.parse_whatsapp_export(content)

        assert len(messages) > 0
        assert "Alice" in metadata["participants"]
        assert "Bob" in metadata["participants"]
        assert metadata["participant_count"] == 2

        # Test threading
        threads = WhatsAppParser.group_into_threads(messages, time_gap_hours=4)
        assert len(threads) >= 2  # At least 2 separate conversations detected

        print(f"✅ US Format: {len(messages)} messages → {len(threads)} threads")

    def test_whatsapp_eu_format(self):
        """Test EU format (DD.MM.YY, 24-hour)"""
        file_path = Path("tests/data/exports/whatsapp_eu_format.txt")
        with open(file_path) as f:
            content = f.read()

        assert WhatsAppParser.is_whatsapp_export(content)
        messages, summary, metadata = WhatsAppParser.parse_whatsapp_export(content)

        assert len(messages) > 0
        assert "Anna" in metadata["participants"]
        assert "Klaus" in metadata["participants"]

        # Test threading
        threads = WhatsAppParser.group_into_threads(messages, time_gap_hours=4)
        assert len(threads) >= 2  # At least 2 separate conversations detected

        print(f"✅ EU Format: {len(messages)} messages → {len(threads)} threads")

    def test_whatsapp_iso_format(self):
        """Test ISO format (YYYY-MM-DD HH:MM:SS)"""
        file_path = Path("tests/data/exports/whatsapp_iso_format.txt")
        with open(file_path) as f:
            content = f.read()

        assert WhatsAppParser.is_whatsapp_export(content)
        messages, summary, metadata = WhatsAppParser.parse_whatsapp_export(content)

        assert len(messages) > 0
        assert "Alice" in metadata["participants"]
        assert "Bob" in metadata["participants"]

        threads = WhatsAppParser.group_into_threads(messages, time_gap_hours=4)
        assert len(threads) == 3

        print(f"✅ ISO Format: {len(messages)} messages → {len(threads)} threads")

    def test_whatsapp_bracket_format(self):
        """Test bracket format ([MM/DD/YY, HH:MM AM/PM])"""
        file_path = Path("tests/data/exports/whatsapp_bracket_format.txt")
        with open(file_path) as f:
            content = f.read()

        assert WhatsAppParser.is_whatsapp_export(content)
        messages, summary, metadata = WhatsAppParser.parse_whatsapp_export(content)

        assert len(messages) > 0
        assert "Alice" in metadata["participants"]
        assert "Bob" in metadata["participants"]

        threads = WhatsAppParser.group_into_threads(messages, time_gap_hours=4)
        assert len(threads) >= 1  # At least 1 conversation detected

        print(f"✅ Bracket Format: {len(messages)} messages → {len(threads)} threads")

    def test_whatsapp_group_complex(self):
        """Test complex group chat with system messages"""
        file_path = Path("tests/data/exports/whatsapp_group_complex.txt")
        with open(file_path) as f:
            content = f.read()

        assert WhatsAppParser.is_whatsapp_export(content)
        messages, summary, metadata = WhatsAppParser.parse_whatsapp_export(content)

        # Should parse user messages (system messages may be skipped)
        assert len(messages) > 0
        assert metadata["participant_count"] >= 3  # Sarah, Michael, Lisa, Thomas

        # Test threading (should detect gaps between conversations)
        threads = WhatsAppParser.group_into_threads(messages, time_gap_hours=4)
        assert len(threads) >= 4  # Multiple conversation threads

        print(f"✅ Group Chat: {len(messages)} messages → {len(threads)} threads")
        print(f"   Participants: {', '.join(metadata['participants'][:5])}")

    def test_whatsapp_thread_metadata(self):
        """Test thread formatting includes proper metadata"""
        file_path = Path("tests/data/exports/whatsapp_us_format.txt")
        with open(file_path) as f:
            content = f.read()

        messages, _, _ = WhatsAppParser.parse_whatsapp_export(content)
        threads = WhatsAppParser.group_into_threads(messages, time_gap_hours=4)

        # Test formatting of first thread
        formatted = WhatsAppParser.format_thread_as_text(threads[0], 1)

        assert "CONVERSATION THREAD 1" in formatted
        assert "Participants:" in formatted
        assert "Messages:" in formatted
        assert "Duration:" in formatted
        assert "Alice" in formatted or "Bob" in formatted

        print(f"✅ Thread metadata formatting verified")


class TestLLMChatParsing:
    """Test LLM chat export parsing with real files"""

    def test_chatgpt_export_parsing(self):
        """Test ChatGPT export parsing"""
        file_path = Path("tests/data/exports/chatgpt_export.json")
        with open(file_path) as f:
            content = f.read()

        assert LLMChatParser.is_llm_export(content)
        assert LLMChatParser.detect_format(content) == "chatgpt"

        messages, summary, metadata = LLMChatParser.parse_llm_export(content)

        assert len(messages) == 4  # 4 messages in the conversation
        assert metadata["export_type"] == "chatgpt"
        assert metadata["total_messages"] == 4
        assert "Python Testing Best Practices" in metadata["conversation_titles"]

        # Check message content
        assert any("pytest" in msg["content"] for msg in messages)
        assert any("fixture" in msg["content"].lower() for msg in messages)

        print(f"✅ ChatGPT Export: {len(messages)} messages")
        print(f"   Conversation: {metadata['conversation_titles'][0]}")

    def test_claude_export_parsing(self):
        """Test Claude export parsing"""
        file_path = Path("tests/data/exports/claude_export.json")
        with open(file_path) as f:
            content = f.read()

        assert LLMChatParser.is_llm_export(content)
        assert LLMChatParser.detect_format(content) == "claude"

        messages, summary, metadata = LLMChatParser.parse_llm_export(content)

        assert len(messages) == 6  # 6 messages in the conversation
        assert metadata["export_type"] == "claude"
        assert metadata["total_messages"] == 6
        assert metadata["conversation_title"] == "RAG System Architecture Discussion"

        # Check message roles
        user_msgs = [m for m in messages if m["role"] == "user"]
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert len(user_msgs) == 3
        assert len(assistant_msgs) == 3

        # Check content
        assert any("RAG" in msg["content"] for msg in messages)
        assert any("WhatsApp" in msg["content"] for msg in messages)

        print(f"✅ Claude Export: {len(messages)} messages")
        print(f"   Conversation: {metadata['conversation_title']}")
        print(f"   User: {len(user_msgs)}, Assistant: {len(assistant_msgs)}")

    def test_llm_markdown_formatting(self):
        """Test markdown formatting of LLM chats"""
        file_path = Path("tests/data/exports/chatgpt_export.json")
        with open(file_path) as f:
            content = f.read()

        messages, _, metadata = LLMChatParser.parse_llm_export(content)
        markdown = LLMChatParser.format_as_markdown(messages, metadata["conversation_titles"][0])

        assert "# Python Testing Best Practices" in markdown
        assert "**User**" in markdown
        assert "**Assistant**" in markdown
        assert "## January" in markdown  # Date headers

        print(f"✅ Markdown formatting verified")


class TestEndToEndConversationParsing:
    """End-to-end tests simulating real usage"""

    def test_whatsapp_full_pipeline(self):
        """Test complete WhatsApp processing pipeline"""
        file_path = Path("tests/data/exports/whatsapp_us_format.txt")
        with open(file_path) as f:
            content = f.read()

        # Step 1: Detection
        is_whatsapp = WhatsAppParser.is_whatsapp_export(content)
        assert is_whatsapp

        # Step 2: Parsing
        messages, summary, metadata = WhatsAppParser.parse_whatsapp_export(content)
        assert len(messages) > 0

        # Step 3: Threading
        threads = WhatsAppParser.group_into_threads(messages, time_gap_hours=4)
        assert len(threads) > 0

        # Step 4: Formatting
        formatted_output = ""
        for idx, thread in enumerate(threads, 1):
            formatted_output += WhatsAppParser.format_thread_as_text(thread, idx)

        assert len(formatted_output) > 0
        assert "CONVERSATION THREAD" in formatted_output

        print(f"✅ Full Pipeline: {len(messages)} msgs → {len(threads)} threads → formatted")

    def test_all_formats_detected_correctly(self):
        """Verify all export formats are correctly detected"""
        test_files = {
            "whatsapp_us_format.txt": "whatsapp",
            "whatsapp_eu_format.txt": "whatsapp",
            "whatsapp_iso_format.txt": "whatsapp",
            "whatsapp_bracket_format.txt": "whatsapp",
            "whatsapp_group_complex.txt": "whatsapp",
            "chatgpt_export.json": "chatgpt",
            "claude_export.json": "claude"
        }

        for filename, expected_type in test_files.items():
            file_path = Path(f"tests/data/exports/{filename}")
            with open(file_path) as f:
                content = f.read()

            if expected_type == "whatsapp":
                assert WhatsAppParser.is_whatsapp_export(content), f"Failed: {filename}"
            else:
                detected = LLMChatParser.detect_format(content)
                assert detected == expected_type, f"Failed: {filename} (got {detected})"

        print(f"✅ All formats detected correctly")

    def test_edge_case_empty_content(self):
        """Test handling of empty or invalid content"""
        # Empty string
        assert not WhatsAppParser.is_whatsapp_export("")
        assert LLMChatParser.detect_format("") is None

        # Invalid JSON
        assert LLMChatParser.detect_format("{invalid json") is None

        # Random text
        random_text = "This is just random text without any chat format"
        assert not WhatsAppParser.is_whatsapp_export(random_text)
        assert LLMChatParser.detect_format(random_text) is None

        print(f"✅ Edge cases handled correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
