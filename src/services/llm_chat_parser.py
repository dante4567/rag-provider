"""
LLM Chat Export Parser

Parses conversation exports from ChatGPT, Claude, and other LLM platforms
Extracts structured data and formats as conversation threads
"""
import json
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class LLMChatParser:
    """
    Parses LLM chat exports (ChatGPT, Claude) into structured conversation data

    Supports:
    - ChatGPT JSON export format
    - Claude conversation JSON format
    - Generic conversation JSON with message arrays
    """

    @staticmethod
    def parse_chatgpt_export(content: str) -> Tuple[List[Dict], str, Dict]:
        """
        Parse ChatGPT conversation export (JSON format)

        Expected format:
        {
          "conversations": [
            {
              "title": "Conversation Title",
              "create_time": 1234567890,
              "mapping": {
                "node_id": {
                  "message": {
                    "author": {"role": "user"},
                    "content": {"parts": ["message text"]},
                    "create_time": 1234567890
                  }
                }
              }
            }
          ]
        }

        Args:
            content: Raw JSON export content

        Returns:
            Tuple of (messages, summary, metadata)
        """
        try:
            data = json.loads(content)
            all_conversations = []
            total_messages = 0

            # Handle both single conversation and array of conversations
            conversations = data.get("conversations", [data] if "title" in data else [])

            for conv_idx, conversation in enumerate(conversations, 1):
                title = conversation.get("title", f"Conversation {conv_idx}")
                create_time = conversation.get("create_time", 0)

                # Extract messages from mapping structure
                mapping = conversation.get("mapping", {})
                messages = []

                for node_id, node in mapping.items():
                    message_data = node.get("message")
                    if not message_data:
                        continue

                    author = message_data.get("author", {})
                    role = author.get("role", "unknown")
                    content_data = message_data.get("content", {})
                    parts = content_data.get("parts", [])
                    text = "\n".join(str(part) for part in parts if part)

                    if text.strip():
                        timestamp = message_data.get("create_time", create_time)
                        messages.append({
                            "role": role,
                            "content": text,
                            "timestamp": datetime.fromtimestamp(timestamp) if timestamp else datetime.now(),
                            "type": "chatgpt_message"
                        })

                if messages:
                    # Sort by timestamp
                    messages.sort(key=lambda x: x["timestamp"])

                    all_conversations.append({
                        "title": title,
                        "messages": messages,
                        "create_time": datetime.fromtimestamp(create_time) if create_time else None
                    })
                    total_messages += len(messages)

            if not all_conversations:
                logger.warning("No ChatGPT conversations found in export")
                return [], "No valid ChatGPT conversations found", {}

            # Generate summary
            summary = LLMChatParser._generate_chatgpt_summary(all_conversations, total_messages)
            metadata = LLMChatParser._generate_chatgpt_metadata(all_conversations, total_messages)

            # Flatten messages with conversation context
            all_messages = []
            for conv in all_conversations:
                for msg in conv["messages"]:
                    msg["conversation_title"] = conv["title"]
                    all_messages.append(msg)

            return all_messages, summary, metadata

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ChatGPT export JSON: {e}")
            return [], f"Invalid JSON format: {e}", {}
        except Exception as e:
            logger.error(f"ChatGPT export parsing failed: {e}")
            return [], f"Parsing error: {e}", {}

    @staticmethod
    def parse_claude_export(content: str) -> Tuple[List[Dict], str, Dict]:
        """
        Parse Claude conversation export (JSON format)

        Expected format:
        {
          "uuid": "conversation-id",
          "name": "Conversation Title",
          "created_at": "2024-01-15T10:30:00Z",
          "chat_messages": [
            {
              "uuid": "msg-id",
              "text": "message text",
              "sender": "human",
              "created_at": "2024-01-15T10:30:00Z"
            }
          ]
        }

        Args:
            content: Raw JSON export content

        Returns:
            Tuple of (messages, summary, metadata)
        """
        try:
            data = json.loads(content)
            messages = []

            # Extract conversation metadata
            conv_title = data.get("name", "Claude Conversation")
            conv_created = data.get("created_at")

            # Parse messages
            chat_messages = data.get("chat_messages", [])

            for msg_data in chat_messages:
                text = msg_data.get("text", "")
                sender = msg_data.get("sender", "unknown")
                created_at = msg_data.get("created_at")

                if text.strip():
                    # Convert sender to role
                    role = "assistant" if sender == "assistant" else "user"

                    # Parse timestamp
                    try:
                        timestamp = datetime.fromisoformat(created_at.replace('Z', '+00:00')) if created_at else datetime.now()
                    except Exception:
                        timestamp = datetime.now()

                    messages.append({
                        "role": role,
                        "content": text,
                        "timestamp": timestamp,
                        "conversation_title": conv_title,
                        "type": "claude_message"
                    })

            if not messages:
                logger.warning("No Claude messages found in export")
                return [], "No valid Claude messages found", {}

            # Sort by timestamp
            messages.sort(key=lambda x: x["timestamp"])

            # Generate summary and metadata
            summary = LLMChatParser._generate_claude_summary(conv_title, messages)
            metadata = LLMChatParser._generate_claude_metadata(conv_title, messages, conv_created)

            return messages, summary, metadata

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude export JSON: {e}")
            return [], f"Invalid JSON format: {e}", {}
        except Exception as e:
            logger.error(f"Claude export parsing failed: {e}")
            return [], f"Parsing error: {e}", {}

    @staticmethod
    def detect_format(content: str) -> Optional[str]:
        """
        Detect which LLM export format the content is

        Returns:
            "chatgpt", "claude", or None
        """
        try:
            data = json.loads(content)

            # ChatGPT indicators
            if "conversations" in data or "mapping" in data:
                return "chatgpt"

            # Claude indicators
            if "chat_messages" in data and "uuid" in data:
                return "claude"

            return None
        except:
            return None

    @staticmethod
    def parse_llm_export(content: str) -> Tuple[List[Dict], str, Dict]:
        """
        Auto-detect and parse LLM chat export

        Args:
            content: Raw export content

        Returns:
            Tuple of (messages, summary, metadata)
        """
        format_type = LLMChatParser.detect_format(content)

        if format_type == "chatgpt":
            logger.info("Detected ChatGPT export format")
            return LLMChatParser.parse_chatgpt_export(content)
        elif format_type == "claude":
            logger.info("Detected Claude export format")
            return LLMChatParser.parse_claude_export(content)
        else:
            logger.warning("Unknown LLM export format")
            return [], "Unknown or unsupported LLM export format", {}

    @staticmethod
    def is_llm_export(content: str) -> bool:
        """
        Check if content appears to be an LLM chat export

        Args:
            content: Text to check

        Returns:
            True if content matches LLM export format
        """
        return LLMChatParser.detect_format(content) is not None

    @staticmethod
    def format_as_markdown(messages: List[Dict], conversation_title: str = "LLM Conversation") -> str:
        """
        Format parsed messages as readable markdown

        Args:
            messages: List of parsed message dictionaries
            conversation_title: Title for the conversation

        Returns:
            Markdown-formatted conversation
        """
        if not messages:
            return "No messages"

        lines = [f"# {conversation_title}\n"]

        current_date = None
        for msg in messages:
            msg_date = msg["timestamp"].date()

            # Add date header when date changes
            if msg_date != current_date:
                current_date = msg_date
                lines.append(f"\n## {msg_date.strftime('%B %d, %Y')}\n")

            # Format message
            time_str = msg["timestamp"].strftime("%I:%M %p")
            role = msg["role"].capitalize()
            content = msg["content"]

            lines.append(f"**{role}** ({time_str}):\n{content}\n")

        return "\n".join(lines)

    # Helper methods for summaries and metadata

    @staticmethod
    def _generate_chatgpt_summary(conversations: List[Dict], total_messages: int) -> str:
        """Generate summary for ChatGPT export"""
        summary_parts = [
            f"ChatGPT Export: {len(conversations)} conversation(s)",
            f"Total messages: {total_messages}",
            ""
        ]

        for idx, conv in enumerate(conversations, 1):
            msg_count = len(conv["messages"])
            title = conv["title"]
            summary_parts.append(f"{idx}. {title} ({msg_count} messages)")

        return "\n".join(summary_parts)

    @staticmethod
    def _generate_chatgpt_metadata(conversations: List[Dict], total_messages: int) -> Dict:
        """Generate metadata for ChatGPT export"""
        return {
            "conversation_count": len(conversations),
            "total_messages": total_messages,
            "conversation_titles": [c["title"] for c in conversations],
            "export_type": "chatgpt",
            "conversation_type": "llm_chat"
        }

    @staticmethod
    def _generate_claude_summary(title: str, messages: List[Dict]) -> str:
        """Generate summary for Claude export"""
        user_msgs = sum(1 for m in messages if m["role"] == "user")
        assistant_msgs = sum(1 for m in messages if m["role"] == "assistant")

        summary_parts = [
            f"Claude Conversation: {title}",
            f"Total messages: {len(messages)}",
            f"User messages: {user_msgs}",
            f"Assistant messages: {assistant_msgs}",
            f"Date range: {messages[0]['timestamp'].strftime('%Y-%m-%d')} to {messages[-1]['timestamp'].strftime('%Y-%m-%d')}"
        ]

        return "\n".join(summary_parts)

    @staticmethod
    def _generate_claude_metadata(title: str, messages: List[Dict], created_at: Optional[str]) -> Dict:
        """Generate metadata for Claude export"""
        return {
            "conversation_title": title,
            "total_messages": len(messages),
            "user_messages": sum(1 for m in messages if m["role"] == "user"),
            "assistant_messages": sum(1 for m in messages if m["role"] == "assistant"),
            "date_range": {
                "start": messages[0]["timestamp"].isoformat(),
                "end": messages[-1]["timestamp"].isoformat()
            },
            "export_type": "claude",
            "conversation_type": "llm_chat"
        }
