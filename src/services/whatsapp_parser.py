"""
WhatsApp chat export parser

Extracts structured data from WhatsApp text exports
"""
import re
import logging
from typing import List, Dict, Tuple, Set
from datetime import datetime
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


class WhatsAppParser:
    """
    Parses WhatsApp chat exports into structured message data

    Supports multiple timestamp formats used by WhatsApp across regions
    """

    # Common WhatsApp timestamp patterns
    PATTERNS = [
        r'(\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2}(?::\d{2})?\s?(?:[AP]M)?) - ([^:]+): (.*)',  # US: 1/15/24, 3:45 PM
        r'(\d{1,2}\.\d{1,2}\.\d{2,4}, \d{1,2}:\d{2}(?::\d{2})?) - ([^:]+): (.*)',  # EU: 15.1.24, 15:45
        r'(\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}(?::\d{2})?) - ([^:]+): (.*)',          # ISO: 2024-01-15 15:45
        r'\[(\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2}(?::\d{2})?\s?(?:[AP]M)?)\] ([^:]+): (.*)'  # Brackets: [1/15/24, 3:45 PM]
    ]

    @staticmethod
    def parse_whatsapp_export(content: str) -> Tuple[List[Dict], str, Dict]:
        """
        Parse WhatsApp chat export text

        Args:
            content: Raw WhatsApp export text

        Returns:
            Tuple of (messages, summary, metadata)
            - messages: List of parsed message dictionaries
            - summary: Generated conversation summary
            - metadata: Conversation statistics
        """
        messages = []
        participants = set()

        # Try each pattern until we find matches
        for pattern in WhatsAppParser.PATTERNS:
            matches = list(re.finditer(pattern, content, re.MULTILINE))

            if matches:
                logger.info(f"Matched WhatsApp format with pattern: {pattern[:50]}...")

                for match in matches:
                    timestamp_str, sender, message = match.groups()

                    # Parse timestamp
                    try:
                        timestamp = date_parser.parse(timestamp_str)
                    except Exception as e:
                        logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
                        timestamp = datetime.now()

                    # Track participants
                    sender_clean = sender.strip()
                    participants.add(sender_clean)

                    # Add message
                    messages.append({
                        "timestamp": timestamp,
                        "sender": sender_clean,
                        "message": message.strip(),
                        "type": "whatsapp_message"
                    })

                break  # Found matching pattern, stop trying others

        if not messages:
            logger.warning("No WhatsApp messages found in content")
            return [], "No valid WhatsApp messages found", {}

        # Sort by timestamp
        messages.sort(key=lambda x: x["timestamp"])

        # Generate summary and metadata
        summary = WhatsAppParser._generate_conversation_summary(messages, participants)
        metadata = WhatsAppParser._generate_metadata(messages, participants)

        return messages, summary, metadata

    @staticmethod
    def _generate_conversation_summary(messages: List[Dict], participants: Set[str]) -> str:
        """
        Generate a summary of the conversation

        Args:
            messages: List of parsed messages
            participants: Set of participant names

        Returns:
            Summary text
        """
        if not messages:
            return "Empty conversation"

        total_messages = len(messages)
        first_message = messages[0]
        last_message = messages[-1]

        # Message counts per participant
        message_counts = {}
        for msg in messages:
            sender = msg["sender"]
            message_counts[sender] = message_counts.get(sender, 0) + 1

        # Build summary
        summary_parts = [
            f"WhatsApp conversation with {len(participants)} participant(s): {', '.join(sorted(participants))}",
            f"Total messages: {total_messages}",
            f"Date range: {first_message['timestamp'].strftime('%Y-%m-%d')} to {last_message['timestamp'].strftime('%Y-%m-%d')}",
            ""
        ]

        # Add message counts
        summary_parts.append("Message distribution:")
        for sender in sorted(message_counts.keys(), key=lambda x: message_counts[x], reverse=True):
            count = message_counts[sender]
            percentage = (count / total_messages) * 100
            summary_parts.append(f"  - {sender}: {count} messages ({percentage:.1f}%)")

        return "\n".join(summary_parts)

    @staticmethod
    def _generate_metadata(messages: List[Dict], participants: Set[str]) -> Dict:
        """
        Generate metadata about the conversation

        Args:
            messages: List of parsed messages
            participants: Set of participant names

        Returns:
            Metadata dictionary
        """
        if not messages:
            return {}

        # Calculate statistics
        message_counts = {}
        total_chars = 0

        for msg in messages:
            sender = msg["sender"]
            message_counts[sender] = message_counts.get(sender, 0) + 1
            total_chars += len(msg["message"])

        avg_message_length = total_chars / len(messages) if messages else 0

        return {
            "participants": list(participants),
            "participant_count": len(participants),
            "total_messages": len(messages),
            "message_counts": message_counts,
            "date_range": {
                "start": messages[0]["timestamp"].isoformat(),
                "end": messages[-1]["timestamp"].isoformat()
            },
            "average_message_length": round(avg_message_length, 2),
            "conversation_type": "whatsapp_chat"
        }

    @staticmethod
    def group_into_threads(messages: List[Dict], time_gap_hours: int = 4) -> List[List[Dict]]:
        """
        Group messages into conversation threads based on time gaps

        Args:
            messages: List of parsed WhatsApp messages
            time_gap_hours: Hours of silence to consider a new thread (default: 4)

        Returns:
            List of message threads (each thread is a list of messages)
        """
        if not messages:
            return []

        threads = []
        current_thread = [messages[0]]

        for i in range(1, len(messages)):
            current_msg = messages[i]
            previous_msg = messages[i-1]

            # Calculate time gap in hours
            time_gap = (current_msg["timestamp"] - previous_msg["timestamp"]).total_seconds() / 3600

            # Start new thread if gap is too large
            if time_gap > time_gap_hours:
                threads.append(current_thread)
                current_thread = [current_msg]
                logger.debug(f"New WhatsApp thread started after {time_gap:.1f}h gap")
            else:
                current_thread.append(current_msg)

        # Add the last thread
        if current_thread:
            threads.append(current_thread)

        logger.info(f"Grouped {len(messages)} messages into {len(threads)} conversation threads")
        return threads

    @staticmethod
    def format_thread_as_text(thread: List[Dict], thread_idx: int) -> str:
        """
        Format a conversation thread as readable text

        Args:
            thread: List of messages in the thread
            thread_idx: Thread index number

        Returns:
            Formatted text representation
        """
        if not thread:
            return ""

        # Calculate thread metadata
        participants = set(msg["sender"] for msg in thread)
        start_time = thread[0]["timestamp"]
        end_time = thread[-1]["timestamp"]
        duration = (end_time - start_time).total_seconds() / 3600  # hours

        # Build formatted output
        result = f"\n{'='*80}\n"
        result += f"CONVERSATION THREAD {thread_idx}\n"
        result += f"{'='*80}\n"
        result += f"Participants: {', '.join(sorted(participants))}\n"
        result += f"Messages: {len(thread)}\n"
        result += f"Time: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}\n"
        result += f"Duration: {duration:.1f} hours\n"
        result += f"{'-'*80}\n\n"

        # Add all messages
        for msg in thread:
            timestamp_str = msg["timestamp"].strftime('%Y-%m-%d %H:%M')
            result += f"[{timestamp_str}] {msg['sender']}: {msg['message']}\n"

        return result

    @staticmethod
    def is_whatsapp_export(content: str) -> bool:
        """
        Check if content appears to be a WhatsApp export

        Args:
            content: Text to check

        Returns:
            True if content matches WhatsApp export format
        """
        # Quick check: look for any WhatsApp pattern matches
        for pattern in WhatsAppParser.PATTERNS:
            if re.search(pattern, content):
                return True

        return False

    @staticmethod
    def format_messages_as_markdown(messages: List[Dict]) -> str:
        """
        Format parsed messages as readable markdown

        Args:
            messages: List of parsed message dictionaries

        Returns:
            Markdown-formatted conversation
        """
        if not messages:
            return "No messages"

        lines = ["# WhatsApp Conversation\n"]

        current_date = None
        for msg in messages:
            msg_date = msg["timestamp"].date()

            # Add date header when date changes
            if msg_date != current_date:
                current_date = msg_date
                lines.append(f"\n## {msg_date.strftime('%B %d, %Y')}\n")

            # Format message
            time_str = msg["timestamp"].strftime("%I:%M %p")
            sender = msg["sender"]
            message = msg["message"]

            lines.append(f"**{sender}** ({time_str}): {message}\n")

        return "\n".join(lines)
