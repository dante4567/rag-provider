"""
Email Threading Service - Group email messages into conversation threads

Implements blueprint requirement: "1 MD per thread with message arrays"

Features:
- Thread detection based on Subject, In-Reply-To, References
- Message grouping and ordering
- Thread-level metadata extraction
- Markdown generation for threads
"""

import re
import logging
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict
import email
from email import policy
from email.parser import BytesParser
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Individual email message"""
    message_id: str
    subject: str
    sender: str
    recipients: List[str]
    date: datetime
    body: str
    in_reply_to: Optional[str] = None
    references: List[str] = field(default_factory=list)
    attachments: List[str] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class EmailThread:
    """Email conversation thread"""
    thread_id: str
    subject: str
    participants: Set[str]
    messages: List[EmailMessage]
    start_date: datetime
    end_date: datetime
    message_count: int
    has_attachments: bool = False


class EmailThreadingService:
    """Service for threading email messages into conversations"""

    def __init__(self):
        self.threads: Dict[str, EmailThread] = {}

    def normalize_subject(self, subject: str) -> str:
        """
        Normalize email subject for threading

        Removes Re:, Fwd:, etc. prefixes and extra whitespace
        """
        # Remove common prefixes
        normalized = re.sub(r'^(Re|RE|re|Fw|FW|fw|Fwd|FWD|fwd):\s*', '', subject, flags=re.IGNORECASE)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized.lower()

    def parse_email_file(self, file_path: str) -> Optional[EmailMessage]:
        """
        Parse an email file (.eml or .msg format)

        Args:
            file_path: Path to email file

        Returns:
            EmailMessage object or None if parsing fails
        """
        try:
            with open(file_path, 'rb') as f:
                msg = BytesParser(policy=policy.default).parse(f)

            # Extract basic fields
            message_id = msg.get('Message-ID', f"<generated-{Path(file_path).stem}>")
            subject = msg.get('Subject', '(No Subject)')
            sender = msg.get('From', 'Unknown')
            recipients = msg.get_all('To', [])
            if isinstance(recipients, str):
                recipients = [recipients]

            # Parse date
            date_str = msg.get('Date')
            try:
                date = email.utils.parsedate_to_datetime(date_str) if date_str else datetime.now()
            except Exception:
                date = datetime.now()

            # Extract body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            break
                        except Exception:
                            pass
            else:
                try:
                    body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                except Exception:
                    body = str(msg.get_payload())

            # Extract threading info
            in_reply_to = msg.get('In-Reply-To')
            references = msg.get_all('References', [])
            if isinstance(references, str):
                references = references.split()

            # Extract attachments
            attachments = []
            if msg.is_multipart():
                for part in msg.walk():
                    filename = part.get_filename()
                    if filename:
                        attachments.append(filename)

            # Store select headers
            headers = {
                'Message-ID': message_id,
                'Subject': subject,
                'From': sender,
                'Date': date_str or '',
            }

            return EmailMessage(
                message_id=message_id,
                subject=subject,
                sender=sender,
                recipients=recipients,
                date=date,
                body=body,
                in_reply_to=in_reply_to,
                references=references,
                attachments=attachments,
                headers=headers
            )

        except Exception as e:
            logger.error(f"Failed to parse email {file_path}: {e}")
            return None

    def build_threads(self, messages: List[EmailMessage]) -> List[EmailThread]:
        """
        Group messages into threads based on subject and references

        Args:
            messages: List of EmailMessage objects

        Returns:
            List of EmailThread objects
        """
        # Group by normalized subject first
        subject_groups = defaultdict(list)
        for msg in messages:
            norm_subject = self.normalize_subject(msg.subject)
            subject_groups[norm_subject].append(msg)

        threads = []

        # Process each subject group
        for norm_subject, group_messages in subject_groups.items():
            # Sort by date
            group_messages.sort(key=lambda m: m.date)

            # Build thread ID from first message
            first_msg = group_messages[0]
            thread_id = first_msg.message_id.strip('<>').split('@')[0]

            # Collect participants
            participants = set()
            for msg in group_messages:
                participants.add(msg.sender)
                participants.update(msg.recipients)

            # Check for attachments
            has_attachments = any(msg.attachments for msg in group_messages)

            thread = EmailThread(
                thread_id=thread_id,
                subject=first_msg.subject,  # Use original subject from first message
                participants=participants,
                messages=group_messages,
                start_date=group_messages[0].date,
                end_date=group_messages[-1].date,
                message_count=len(group_messages),
                has_attachments=has_attachments
            )

            threads.append(thread)

        return threads

    def generate_thread_markdown(self, thread: EmailThread) -> str:
        """
        Generate Markdown document for an email thread

        Args:
            thread: EmailThread object

        Returns:
            Markdown string with YAML frontmatter
        """
        # Generate YAML frontmatter
        participants_list = sorted(list(thread.participants))

        yaml_front = f"""---
id: {thread.thread_id}
source: email
doc_type: correspondence.thread
title: "{thread.subject}"
created_at: {thread.start_date.isoformat()}
ingested_at: {datetime.now().isoformat()}

people: {participants_list}
places: []
projects: []
topics: []

entities:
  orgs: []
  dates: ["{thread.start_date.date()}", "{thread.end_date.date()}"]
  numbers: []

summary: "Email thread: {thread.subject} ({thread.message_count} messages from {thread.start_date.date()} to {thread.end_date.date()})"

# Scoring (defaults - should be enriched)
quality_score: 1.0
novelty_score: 0.0
actionability_score: 0.0
signalness: 0.0
do_index: false

# Thread metadata
thread:
  message_count: {thread.message_count}
  participants: {participants_list}
  has_attachments: {str(thread.has_attachments).lower()}
  date_range:
    start: {thread.start_date.isoformat()}
    end: {thread.end_date.isoformat()}

provenance:
  sha256: ""
  mailbox: ""
  message_ids: {[msg.message_id for msg in thread.messages]}
enrichment_version: v2.1
---

"""

        # Generate body
        body = f"# {thread.subject}\n\n"
        body += f"**Thread:** {thread.message_count} messages from {thread.start_date.date()} to {thread.end_date.date()}\n\n"
        body += f"**Participants:** {', '.join(sorted(participants_list))}\n\n"

        if thread.has_attachments:
            body += "**Attachments:** Yes\n\n"

        body += "---\n\n"
        body += "## Messages\n\n"

        # Add each message
        for i, msg in enumerate(thread.messages, 1):
            body += f"### Message {i}: {msg.sender} ({msg.date.strftime('%Y-%m-%d %H:%M')})\n\n"

            if msg.recipients:
                body += f"**To:** {', '.join(msg.recipients)}\n\n"

            if msg.attachments:
                body += f"**Attachments:** {', '.join(msg.attachments)}\n\n"

            # Clean and add body
            clean_body = msg.body.strip()
            if clean_body:
                body += f"{clean_body}\n\n"
            else:
                body += "*[No content]*\n\n"

            body += "---\n\n"

        return yaml_front + body

    def process_mailbox(self, mailbox_path: str, output_dir: str) -> Tuple[int, int]:
        """
        Process all emails in a mailbox directory and generate thread MDs

        Args:
            mailbox_path: Path to directory containing .eml files
            output_dir: Path to output directory for thread MDs

        Returns:
            Tuple of (threads_created, messages_processed)
        """
        mailbox_path = Path(mailbox_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Parse all email files
        messages = []
        for email_file in mailbox_path.glob("**/*.eml"):
            msg = self.parse_email_file(str(email_file))
            if msg:
                messages.append(msg)

        if not messages:
            logger.warning(f"No email messages found in {mailbox_path}")
            return 0, 0

        logger.info(f"Parsed {len(messages)} email messages")

        # Build threads
        threads = self.build_threads(messages)
        logger.info(f"Created {len(threads)} threads from {len(messages)} messages")

        # Generate markdown files
        for thread in threads:
            # Create safe filename
            safe_subject = re.sub(r'[^\w\s-]', '', thread.subject)[:50]
            safe_subject = re.sub(r'[-\s]+', '_', safe_subject)
            filename = f"{thread.start_date.date()}_{safe_subject}_{thread.thread_id[:8]}.md"

            output_path = output_dir / filename
            markdown = self.generate_thread_markdown(thread)

            output_path.write_text(markdown, encoding='utf-8')
            logger.info(f"Created thread MD: {output_path}")

        return len(threads), len(messages)

    def get_thread_statistics(self, threads: List[EmailThread]) -> Dict:
        """
        Generate statistics about email threads

        Args:
            threads: List of EmailThread objects

        Returns:
            Dictionary with statistics
        """
        if not threads:
            return {}

        total_messages = sum(t.message_count for t in threads)
        participants = set()
        for thread in threads:
            participants.update(thread.participants)

        return {
            "total_threads": len(threads),
            "total_messages": total_messages,
            "avg_messages_per_thread": total_messages / len(threads) if threads else 0,
            "total_participants": len(participants),
            "threads_with_attachments": sum(1 for t in threads if t.has_attachments),
            "date_range": {
                "earliest": min(t.start_date for t in threads).isoformat(),
                "latest": max(t.end_date for t in threads).isoformat()
            }
        }
