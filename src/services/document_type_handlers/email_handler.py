"""
Email Document Type Handler

Specialized processing for email documents with:
- Reply chain removal (lines starting with >)
- Forwarding header cleanup
- Signature detection and removal
- Thread-aware chunking
- Type-specific summary generation
"""
import re
from typing import Dict, Any, List
from .base_handler import DocumentTypeHandler


class EmailHandler(DocumentTypeHandler):
    """
    Email-specific document processing.

    Handles the unique challenges of email:
    - Nested reply chains create noise
    - Forwarding headers clutter content
    - Thread context is crucial for understanding
    - Signatures and disclaimers add no value
    """

    # Common reply prefixes in multiple languages
    REPLY_PREFIXES = [
        r'^>+\s*',                    # Standard > reply markers
        r'^On .+ wrote:',             # "On Mon, Oct 16... John wrote:"
        r'^Am .+ schrieb:',           # German: "Am Montag... schrieb:"
        r'^Le .+ a écrit :',          # French
        r'^El .+ escribió:',          # Spanish
    ]

    # Forwarding headers
    FORWARD_PATTERNS = [
        r'^-+\s*Forwarded [Mm]essage\s*-+',
        r'^-+\s*Original [Mm]essage\s*-+',
        r'^-+\s*Weitergeleitete Nachricht\s*-+',  # German
        r'^Begin forwarded message:',
        r'^From:.*\nSent:.*\nTo:.*\nSubject:',  # Outlook-style
    ]

    # Signature patterns
    SIGNATURE_MARKERS = [
        r'^--\s*$',                   # Standard signature delimiter
        r'^___+$',                    # Underline separators
        r'^Sent from my (iPhone|iPad|Android)',
        r'^Get Outlook for (iOS|Android)',
        r'^Best regards,?\s*$',
        r'^Kind regards,?\s*$',
        r'^Cheers,?\s*$',
        r'^Thanks,?\s*$',
    ]

    # Legal/confidentiality footers
    FOOTER_PATTERNS = [
        r'This email.*confidential',
        r'CONFIDENTIALITY NOTICE',
        r'This message.*intended recipient',
        r'If you.*received.*in error',
    ]

    def preprocess(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        Clean email content for optimal indexing.

        Steps:
        1. Remove reply chains (quoted text from previous messages)
        2. Remove forwarding headers
        3. Detect and remove signatures
        4. Remove legal disclaimers
        5. Normalize whitespace

        Args:
            text: Raw email text
            metadata: Email metadata (may contain thread info)

        Returns:
            Cleaned email content
        """
        original_length = len(text)
        lines = text.split('\n')

        # Step 1: Remove reply chains
        cleaned_lines = []
        in_reply_block = False

        for line in lines:
            # Check if this line starts a reply block
            is_reply = any(re.match(pattern, line, re.IGNORECASE) for pattern in self.REPLY_PREFIXES)

            if is_reply:
                in_reply_block = True
                continue  # Skip this line

            # Check if we're exiting a reply block (line doesn't start with >)
            if in_reply_block and not line.strip().startswith('>'):
                in_reply_block = False

            if not in_reply_block:
                cleaned_lines.append(line)

        text = '\n'.join(cleaned_lines)

        # Step 2: Remove forwarding headers (often multi-line blocks)
        for pattern in self.FORWARD_PATTERNS:
            # Remove the header and the next 5 lines (From/Sent/To/Subject/etc)
            text = re.sub(
                pattern + r'.*?(\n.*?){0,5}\n',
                '\n',
                text,
                flags=re.MULTILINE | re.DOTALL | re.IGNORECASE
            )

        # Step 3: Detect and remove signatures
        # Find the first signature marker and remove everything after
        lines = text.split('\n')
        signature_start = None

        for i, line in enumerate(lines):
            if any(re.match(pattern, line, re.IGNORECASE) for pattern in self.SIGNATURE_MARKERS):
                signature_start = i
                break

        if signature_start is not None:
            # Keep content before signature
            text = '\n'.join(lines[:signature_start])
            self.logger.debug(f"Removed signature starting at line {signature_start}")

        # Step 4: Remove legal disclaimers/footers
        for pattern in self.FOOTER_PATTERNS:
            # Remove the disclaimer and everything after it
            text = re.sub(
                pattern + r'.*$',
                '',
                text,
                flags=re.MULTILINE | re.DOTALL | re.IGNORECASE
            )

        # Step 5: Normalize whitespace
        # Remove excessive blank lines (more than 2 consecutive)
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Remove trailing whitespace from each line
        text = '\n'.join(line.rstrip() for line in text.split('\n'))
        # Remove leading/trailing whitespace from entire text
        text = text.strip()

        # Validation
        cleaned_length = len(text)
        if not self.validate_preprocessing(text, text):
            self.logger.warning(
                f"Email preprocessing may have removed too much content "
                f"({original_length} → {cleaned_length} chars, "
                f"{100 * (1 - cleaned_length/original_length):.1f}% removed)"
            )

        self.logger.info(
            f"📧 Email cleaned: {original_length} → {cleaned_length} chars "
            f"({100 * cleaned_length/original_length:.1f}% retained)"
        )

        return text

    def extract_metadata(self, text: str, existing_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract email-specific metadata.

        Already extracted by document_service._process_email():
        - thread_id, message_id, sender, recipients, subject
        - in_reply_to, references

        Additional extraction:
        - Has inline replies (detected by removed content)
        - Estimated reply depth
        - Action items (if text contains "TODO", "ACTION", etc.)

        Args:
            text: Cleaned email text
            existing_metadata: Metadata from email parser

        Returns:
            Enhanced metadata dict
        """
        enhanced = {}

        # Detect action items
        action_keywords = ['todo', 'action item', 'please', 'can you', 'need to', 'must', 'should']
        has_action = any(keyword in text.lower() for keyword in action_keywords)
        if has_action:
            enhanced['has_action_items'] = True

        # Detect urgency markers
        urgency_keywords = ['urgent', 'asap', 'immediately', 'deadline', 'critical']
        is_urgent = any(keyword in text.lower() for keyword in urgency_keywords)
        if is_urgent:
            enhanced['is_urgent'] = True

        # Detect if email was heavily quoted (lots of removed content)
        # This is useful for prioritizing original content vs. heavily-quoted emails
        if existing_metadata.get('original_length'):
            removal_ratio = 1 - (len(text) / existing_metadata['original_length'])
            if removal_ratio > 0.5:
                enhanced['high_quote_ratio'] = True

        return enhanced

    def get_chunking_strategy(self, metadata: Dict[str, Any]) -> str:
        """
        Determine chunking strategy for emails.

        Strategy:
        - If part of thread: 'thread' (group with related messages)
        - Single email: 'message' (entire email as one chunk)

        For very long emails (>2000 tokens), may fall back to 'semantic'
        chunking, but this is rare for emails.

        Args:
            metadata: Email metadata

        Returns:
            'thread' or 'message'
        """
        # Check if email is part of a thread
        thread_id = metadata.get('thread_id')
        has_thread_context = thread_id and metadata.get('in_reply_to')

        if has_thread_context:
            return 'thread'

        return 'message'

    def get_summary_prompt(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        Generate email-specific summary prompt.

        Emails should be summarized to capture:
        - Key decision or action item (not just "discussion about X")
        - Outcome or next steps
        - Important dates or deadlines

        Args:
            text: Email content
            metadata: Email metadata

        Returns:
            Specialized prompt for email summarization
        """
        sender = metadata.get('sender', 'Unknown')
        subject = metadata.get('subject', 'No subject')
        is_thread = metadata.get('in_reply_to') or metadata.get('references')

        if is_thread:
            # Thread summary: Focus on outcome
            prompt = f"""Summarize this email thread.

Subject: {subject}
From: {sender}

Focus on:
1. The key decision or outcome (not just "discussion about X")
2. Action items or next steps
3. Important dates or deadlines mentioned

Be specific and actionable. Start with the outcome (e.g., "Decided to postpone project until March" not "Email discussing project timeline").

Email content:
{text}

Summary (1-2 sentences):"""
        else:
            # Single email: Capture main point
            prompt = f"""Summarize this email message.

Subject: {subject}
From: {sender}

Capture:
1. The main request, question, or information being shared
2. Any action required from the recipient
3. Important context or deadlines

Summary (1-2 sentences):"""

        return prompt

    def should_chunk_together(self, chunks: List[str], metadata: Dict[str, Any]) -> bool:
        """
        For email threads, keep messages together for context.

        Args:
            chunks: List of chunk texts
            metadata: Email metadata

        Returns:
            True if this is a thread and chunks should be combined
        """
        # Keep thread messages together if thread has <5 messages
        thread_id = metadata.get('thread_id')
        if thread_id and len(chunks) < 5:
            return True

        return False

    def detect_language(self, text: str) -> str:
        """
        Simple language detection based on common words.

        Returns:
            Language code: 'en', 'de', 'fr', 'es', or 'unknown'
        """
        # Count common words per language
        lang_markers = {
            'en': ['the', 'and', 'is', 'are', 'was', 'were', 'have', 'has'],
            'de': ['der', 'die', 'das', 'und', 'ist', 'sind', 'haben', 'mit'],
            'fr': ['le', 'la', 'les', 'et', 'est', 'sont', 'avec', 'dans'],
            'es': ['el', 'la', 'los', 'las', 'y', 'es', 'son', 'con']
        }

        text_lower = text.lower()
        scores = {}

        for lang, markers in lang_markers.items():
            score = sum(1 for marker in markers if f' {marker} ' in text_lower)
            scores[lang] = score

        detected = max(scores, key=scores.get)
        return detected if scores[detected] > 0 else 'unknown'
