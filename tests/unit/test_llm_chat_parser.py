"""
Unit tests for LLM Chat Parser Service

Tests parsing of ChatGPT and Claude conversation exports
"""
import pytest
import json
from datetime import datetime
from src.services.llm_chat_parser import LLMChatParser


class TestChatGPTExportParsing:
    """Test ChatGPT export parsing"""

    def test_parse_chatgpt_basic(self):
        """Test basic ChatGPT export parsing"""
        export = {
            "conversations": [{
                "title": "Python Help",
                "create_time": 1234567890,
                "mapping": {
                    "node1": {
                        "message": {
                            "author": {"role": "user"},
                            "content": {"parts": ["How do I use pytest?"]},
                            "create_time": 1234567890
                        }
                    },
                    "node2": {
                        "message": {
                            "author": {"role": "assistant"},
                            "content": {"parts": ["Here's how to use pytest..."]},
                            "create_time": 1234567900
                        }
                    }
                }
            }]
        }

        messages, summary, metadata = LLMChatParser.parse_chatgpt_export(json.dumps(export))

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "How do I use pytest?"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Here's how to use pytest..."
        assert "Python Help" in summary
        assert metadata["export_type"] == "chatgpt"
        assert metadata["total_messages"] == 2

    def test_parse_chatgpt_multiple_conversations(self):
        """Test multiple conversations in one export"""
        export = {
            "conversations": [
                {
                    "title": "Conversation 1",
                    "create_time": 1234567890,
                    "mapping": {
                        "node1": {
                            "message": {
                                "author": {"role": "user"},
                                "content": {"parts": ["Hello"]},
                                "create_time": 1234567890
                            }
                        }
                    }
                },
                {
                    "title": "Conversation 2",
                    "create_time": 1234567990,
                    "mapping": {
                        "node1": {
                            "message": {
                                "author": {"role": "user"},
                                "content": {"parts": ["Hi again"]},
                                "create_time": 1234567990
                            }
                        }
                    }
                }
            ]
        }

        messages, summary, metadata = LLMChatParser.parse_chatgpt_export(json.dumps(export))

        assert len(messages) == 2
        assert messages[0]["conversation_title"] == "Conversation 1"
        assert messages[1]["conversation_title"] == "Conversation 2"
        assert metadata["conversation_count"] == 2
        assert "Conversation 1" in metadata["conversation_titles"]
        assert "Conversation 2" in metadata["conversation_titles"]

    def test_parse_chatgpt_multipart_message(self):
        """Test messages with multiple parts"""
        export = {
            "conversations": [{
                "title": "Test",
                "create_time": 1234567890,
                "mapping": {
                    "node1": {
                        "message": {
                            "author": {"role": "user"},
                            "content": {"parts": ["Part 1", "Part 2", "Part 3"]},
                            "create_time": 1234567890
                        }
                    }
                }
            }]
        }

        messages, _, _ = LLMChatParser.parse_chatgpt_export(json.dumps(export))

        assert len(messages) == 1
        assert "Part 1\nPart 2\nPart 3" in messages[0]["content"]

    def test_parse_chatgpt_empty_nodes(self):
        """Test handling of empty nodes in mapping"""
        export = {
            "conversations": [{
                "title": "Test",
                "create_time": 1234567890,
                "mapping": {
                    "node1": {},  # Empty node
                    "node2": {"message": None},  # Null message
                    "node3": {
                        "message": {
                            "author": {"role": "user"},
                            "content": {"parts": ["Valid message"]},
                            "create_time": 1234567890
                        }
                    }
                }
            }]
        }

        messages, _, _ = LLMChatParser.parse_chatgpt_export(json.dumps(export))

        assert len(messages) == 1
        assert messages[0]["content"] == "Valid message"

    def test_parse_chatgpt_no_conversations(self):
        """Test export with no valid conversations"""
        export = {"conversations": []}

        messages, summary, metadata = LLMChatParser.parse_chatgpt_export(json.dumps(export))

        assert len(messages) == 0
        assert "No valid" in summary
        assert metadata == {}

    def test_parse_chatgpt_invalid_json(self):
        """Test invalid JSON handling"""
        invalid_json = "{'not': 'valid json"

        messages, summary, metadata = LLMChatParser.parse_chatgpt_export(invalid_json)

        assert len(messages) == 0
        assert "Invalid JSON" in summary
        assert metadata == {}

    def test_parse_chatgpt_single_conversation_format(self):
        """Test single conversation (not in array)"""
        export = {
            "title": "Single Conversation",
            "create_time": 1234567890,
            "mapping": {
                "node1": {
                    "message": {
                        "author": {"role": "user"},
                        "content": {"parts": ["Hello"]},
                        "create_time": 1234567890
                    }
                }
            }
        }

        messages, summary, metadata = LLMChatParser.parse_chatgpt_export(json.dumps(export))

        assert len(messages) == 1
        assert messages[0]["content"] == "Hello"


class TestClaudeExportParsing:
    """Test Claude export parsing"""

    def test_parse_claude_basic(self):
        """Test basic Claude export parsing"""
        export = {
            "uuid": "conv-123",
            "name": "Python Help",
            "created_at": "2024-01-15T10:30:00Z",
            "chat_messages": [
                {
                    "uuid": "msg-1",
                    "text": "How do I use pytest?",
                    "sender": "human",
                    "created_at": "2024-01-15T10:30:00Z"
                },
                {
                    "uuid": "msg-2",
                    "text": "Here's how to use pytest...",
                    "sender": "assistant",
                    "created_at": "2024-01-15T10:31:00Z"
                }
            ]
        }

        messages, summary, metadata = LLMChatParser.parse_claude_export(json.dumps(export))

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "How do I use pytest?"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Here's how to use pytest..."
        assert "Python Help" in summary
        assert metadata["export_type"] == "claude"
        assert metadata["conversation_title"] == "Python Help"

    def test_parse_claude_user_messages_only(self):
        """Test conversation with only user messages"""
        export = {
            "uuid": "conv-123",
            "name": "User Only",
            "created_at": "2024-01-15T10:30:00Z",
            "chat_messages": [
                {
                    "uuid": "msg-1",
                    "text": "Message 1",
                    "sender": "human",
                    "created_at": "2024-01-15T10:30:00Z"
                },
                {
                    "uuid": "msg-2",
                    "text": "Message 2",
                    "sender": "human",
                    "created_at": "2024-01-15T10:31:00Z"
                }
            ]
        }

        messages, _, metadata = LLMChatParser.parse_claude_export(json.dumps(export))

        assert len(messages) == 2
        assert all(msg["role"] == "user" for msg in messages)
        assert metadata["user_messages"] == 2
        assert metadata["assistant_messages"] == 0

    def test_parse_claude_empty_messages(self):
        """Test handling of empty message text"""
        export = {
            "uuid": "conv-123",
            "name": "Test",
            "created_at": "2024-01-15T10:30:00Z",
            "chat_messages": [
                {
                    "uuid": "msg-1",
                    "text": "",
                    "sender": "human",
                    "created_at": "2024-01-15T10:30:00Z"
                },
                {
                    "uuid": "msg-2",
                    "text": "Valid message",
                    "sender": "assistant",
                    "created_at": "2024-01-15T10:31:00Z"
                }
            ]
        }

        messages, _, _ = LLMChatParser.parse_claude_export(json.dumps(export))

        assert len(messages) == 1
        assert messages[0]["content"] == "Valid message"

    def test_parse_claude_no_messages(self):
        """Test export with no messages"""
        export = {
            "uuid": "conv-123",
            "name": "Empty",
            "created_at": "2024-01-15T10:30:00Z",
            "chat_messages": []
        }

        messages, summary, metadata = LLMChatParser.parse_claude_export(json.dumps(export))

        assert len(messages) == 0
        assert "No valid" in summary
        assert metadata == {}

    def test_parse_claude_invalid_timestamp(self):
        """Test handling of invalid timestamps"""
        export = {
            "uuid": "conv-123",
            "name": "Test",
            "created_at": "invalid-date",
            "chat_messages": [
                {
                    "uuid": "msg-1",
                    "text": "Hello",
                    "sender": "human",
                    "created_at": "not-a-date"
                }
            ]
        }

        messages, _, _ = LLMChatParser.parse_claude_export(json.dumps(export))

        assert len(messages) == 1
        assert messages[0]["content"] == "Hello"
        # Should use datetime.now() for invalid timestamps
        assert isinstance(messages[0]["timestamp"], datetime)

    def test_parse_claude_unknown_sender(self):
        """Test handling of unknown sender"""
        export = {
            "uuid": "conv-123",
            "name": "Test",
            "created_at": "2024-01-15T10:30:00Z",
            "chat_messages": [
                {
                    "uuid": "msg-1",
                    "text": "Hello",
                    "sender": "unknown_type",
                    "created_at": "2024-01-15T10:30:00Z"
                }
            ]
        }

        messages, _, _ = LLMChatParser.parse_claude_export(json.dumps(export))

        assert len(messages) == 1
        assert messages[0]["role"] == "user"  # Defaults to user


class TestFormatDetection:
    """Test format detection and auto-parsing"""

    def test_detect_chatgpt_format(self):
        """Test ChatGPT format detection"""
        export = {
            "conversations": [{
                "title": "Test",
                "mapping": {}
            }]
        }

        format_type = LLMChatParser.detect_format(json.dumps(export))
        assert format_type == "chatgpt"

    def test_detect_claude_format(self):
        """Test Claude format detection"""
        export = {
            "uuid": "conv-123",
            "chat_messages": []
        }

        format_type = LLMChatParser.detect_format(json.dumps(export))
        assert format_type == "claude"

    def test_detect_unknown_format(self):
        """Test unknown format detection"""
        export = {"random": "data"}

        format_type = LLMChatParser.detect_format(json.dumps(export))
        assert format_type is None

    def test_detect_invalid_json(self):
        """Test invalid JSON returns None"""
        format_type = LLMChatParser.detect_format("not json")
        assert format_type is None

    def test_is_llm_export_true(self):
        """Test is_llm_export returns True for valid exports"""
        chatgpt_export = {"conversations": [{"mapping": {}}]}
        assert LLMChatParser.is_llm_export(json.dumps(chatgpt_export)) is True

        claude_export = {"uuid": "123", "chat_messages": []}
        assert LLMChatParser.is_llm_export(json.dumps(claude_export)) is True

    def test_is_llm_export_false(self):
        """Test is_llm_export returns False for non-exports"""
        assert LLMChatParser.is_llm_export("random text") is False
        assert LLMChatParser.is_llm_export('{"random": "json"}') is False

    def test_parse_llm_export_auto_chatgpt(self):
        """Test auto-parsing ChatGPT format"""
        export = {
            "conversations": [{
                "title": "Test",
                "create_time": 1234567890,
                "mapping": {
                    "node1": {
                        "message": {
                            "author": {"role": "user"},
                            "content": {"parts": ["Hello"]},
                            "create_time": 1234567890
                        }
                    }
                }
            }]
        }

        messages, summary, metadata = LLMChatParser.parse_llm_export(json.dumps(export))

        assert len(messages) == 1
        assert metadata["export_type"] == "chatgpt"

    def test_parse_llm_export_auto_claude(self):
        """Test auto-parsing Claude format"""
        export = {
            "uuid": "conv-123",
            "name": "Test",
            "created_at": "2024-01-15T10:30:00Z",
            "chat_messages": [{
                "uuid": "msg-1",
                "text": "Hello",
                "sender": "human",
                "created_at": "2024-01-15T10:30:00Z"
            }]
        }

        messages, summary, metadata = LLMChatParser.parse_llm_export(json.dumps(export))

        assert len(messages) == 1
        assert metadata["export_type"] == "claude"

    def test_parse_llm_export_unknown(self):
        """Test auto-parsing unknown format"""
        messages, summary, metadata = LLMChatParser.parse_llm_export('{"random": "data"}')

        assert len(messages) == 0
        assert "Unknown" in summary
        assert metadata == {}


class TestMarkdownFormatting:
    """Test markdown output formatting"""

    def test_format_as_markdown_basic(self):
        """Test basic markdown formatting"""
        messages = [
            {
                "role": "user",
                "content": "Hello",
                "timestamp": datetime(2024, 1, 15, 10, 30, 0)
            },
            {
                "role": "assistant",
                "content": "Hi there!",
                "timestamp": datetime(2024, 1, 15, 10, 31, 0)
            }
        ]

        markdown = LLMChatParser.format_as_markdown(messages, "Test Conversation")

        assert "# Test Conversation" in markdown
        assert "## January 15, 2024" in markdown
        assert "**User**" in markdown
        assert "**Assistant**" in markdown
        assert "Hello" in markdown
        assert "Hi there!" in markdown

    def test_format_as_markdown_multiple_days(self):
        """Test markdown with messages across multiple days"""
        messages = [
            {
                "role": "user",
                "content": "Day 1",
                "timestamp": datetime(2024, 1, 15, 10, 30, 0)
            },
            {
                "role": "user",
                "content": "Day 2",
                "timestamp": datetime(2024, 1, 16, 10, 30, 0)
            }
        ]

        markdown = LLMChatParser.format_as_markdown(messages)

        assert "## January 15, 2024" in markdown
        assert "## January 16, 2024" in markdown

    def test_format_as_markdown_empty(self):
        """Test markdown formatting with no messages"""
        markdown = LLMChatParser.format_as_markdown([])
        assert markdown == "No messages"

    def test_format_as_markdown_default_title(self):
        """Test markdown with default title"""
        messages = [{
            "role": "user",
            "content": "Test",
            "timestamp": datetime(2024, 1, 15, 10, 30, 0)
        }]

        markdown = LLMChatParser.format_as_markdown(messages)
        assert "# LLM Conversation" in markdown


class TestMetadataGeneration:
    """Test metadata generation for summaries"""

    def test_chatgpt_metadata_single_conversation(self):
        """Test ChatGPT metadata for single conversation"""
        conversations = [{
            "title": "Test",
            "messages": [
                {"role": "user", "content": "msg1"},
                {"role": "assistant", "content": "msg2"}
            ]
        }]

        metadata = LLMChatParser._generate_chatgpt_metadata(conversations, 2)

        assert metadata["conversation_count"] == 1
        assert metadata["total_messages"] == 2
        assert metadata["export_type"] == "chatgpt"
        assert "Test" in metadata["conversation_titles"]

    def test_claude_metadata_message_counts(self):
        """Test Claude metadata message counts"""
        messages = [
            {"role": "user", "content": "msg1", "timestamp": datetime(2024, 1, 15, 10, 0, 0)},
            {"role": "user", "content": "msg2", "timestamp": datetime(2024, 1, 15, 10, 1, 0)},
            {"role": "assistant", "content": "msg3", "timestamp": datetime(2024, 1, 15, 10, 2, 0)}
        ]

        metadata = LLMChatParser._generate_claude_metadata("Test", messages, None)

        assert metadata["user_messages"] == 2
        assert metadata["assistant_messages"] == 1
        assert metadata["total_messages"] == 3

    def test_claude_summary_generation(self):
        """Test Claude summary generation"""
        messages = [
            {
                "role": "user",
                "content": "msg1",
                "timestamp": datetime(2024, 1, 15, 10, 30, 0)
            },
            {
                "role": "assistant",
                "content": "msg2",
                "timestamp": datetime(2024, 1, 16, 10, 30, 0)
            }
        ]

        summary = LLMChatParser._generate_claude_summary("Test Conversation", messages)

        assert "Test Conversation" in summary
        assert "Total messages: 2" in summary
        assert "User messages: 1" in summary
        assert "Assistant messages: 1" in summary
        assert "2024-01-15 to 2024-01-16" in summary


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_chatgpt_missing_fields(self):
        """Test ChatGPT export with missing optional fields"""
        export = {
            "conversations": [{
                "mapping": {
                    "node1": {
                        "message": {
                            "content": {"parts": ["Hello"]}
                            # Missing: author, create_time
                        }
                    }
                }
            }]
        }

        messages, _, _ = LLMChatParser.parse_chatgpt_export(json.dumps(export))

        # Should handle missing fields gracefully
        assert len(messages) == 1
        assert messages[0]["role"] == "unknown"
        assert isinstance(messages[0]["timestamp"], datetime)

    def test_claude_missing_optional_fields(self):
        """Test Claude export with minimal required fields"""
        export = {
            "uuid": "123",
            "chat_messages": [{
                "text": "Hello"
                # Missing: sender, created_at, uuid
            }]
        }

        messages, _, _ = LLMChatParser.parse_claude_export(json.dumps(export))

        # Should handle missing fields gracefully
        assert len(messages) == 1
        assert messages[0]["content"] == "Hello"

    def test_very_long_conversation(self):
        """Test handling of very long conversations"""
        export = {
            "conversations": [{
                "title": "Long Conversation",
                "create_time": 1234567890,
                "mapping": {
                    f"node{i}": {
                        "message": {
                            "author": {"role": "user"},
                            "content": {"parts": [f"Message {i}"]},
                            "create_time": 1234567890 + i
                        }
                    }
                    for i in range(1000)
                }
            }]
        }

        messages, summary, metadata = LLMChatParser.parse_chatgpt_export(json.dumps(export))

        assert len(messages) == 1000
        assert metadata["total_messages"] == 1000

    def test_unicode_content(self):
        """Test handling of unicode characters"""
        export = {
            "uuid": "123",
            "name": "Unicode Test 你好 🎉",
            "created_at": "2024-01-15T10:30:00Z",
            "chat_messages": [{
                "text": "Hello 世界 emoji: 🚀🎯",
                "sender": "human",
                "created_at": "2024-01-15T10:30:00Z"
            }]
        }

        messages, summary, _ = LLMChatParser.parse_claude_export(json.dumps(export))

        assert "Hello 世界 emoji: 🚀🎯" in messages[0]["content"]
        assert "Unicode Test 你好 🎉" in summary

    def test_null_values(self):
        """Test handling of null values in data"""
        export = {
            "conversations": [{
                "title": None,
                "create_time": None,
                "mapping": {
                    "node1": {
                        "message": {
                            "author": {"role": "user"},
                            "content": {"parts": [None, "Valid", None]},
                            "create_time": None
                        }
                    }
                }
            }]
        }

        messages, _, _ = LLMChatParser.parse_chatgpt_export(json.dumps(export))

        # Should filter out None values
        assert len(messages) == 1
        assert "Valid" in messages[0]["content"]
