"""
Base Document Type Handler

Abstract base class for document type-specific processing.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class DocumentTypeHandler(ABC):
    """
    Base class for document type-specific handlers.

    Each document type (email, scanned PDF, invoice, manual, etc.) should
    implement this interface to provide specialized preprocessing, metadata
    extraction, and chunking strategies.

    The Four Stages:
    1. Preprocess: Clean and normalize raw text
    2. Extract Metadata: Pull type-specific structured data
    3. Chunk Strategy: Determine optimal chunking approach
    4. Summarize: Generate type-appropriate summaries
    """

    def __init__(self):
        self.logger = logger

    @abstractmethod
    def preprocess(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        Clean and normalize text for this document type.

        Examples:
        - Email: Remove reply chains, forwarding headers, signatures
        - Scanned: Validate OCR quality, preserve table structure
        - Chat: Parse into structured messages

        Args:
            text: Raw document text
            metadata: Existing metadata that may inform preprocessing

        Returns:
            Cleaned, normalized text ready for enrichment
        """
        pass

    @abstractmethod
    def extract_metadata(self, text: str, existing_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract type-specific structured metadata.

        Examples:
        - Email: Thread context, participants, subject
        - Invoice: Vendor, amount, line items
        - Manual: Sections, procedures, warnings

        Args:
            text: Document text (may be preprocessed)
            existing_metadata: Metadata from file parsing

        Returns:
            Dictionary of extracted metadata fields
        """
        pass

    @abstractmethod
    def get_chunking_strategy(self, metadata: Dict[str, Any]) -> str:
        """
        Determine optimal chunking strategy for this document type.

        Strategies:
        - 'semantic': Chunk by semantic boundaries (headings, paragraphs)
        - 'fixed': Fixed-size chunks (fallback)
        - 'section': One chunk per document section
        - 'thread': Group related messages together (emails/chats)
        - 'message': One message = one chunk
        - 'session': Group by conversational session (chats)

        Args:
            metadata: Document metadata

        Returns:
            Strategy name as string
        """
        pass

    @abstractmethod
    def get_summary_prompt(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        Generate type-specific summary prompt for LLM.

        Different document types need different summarization approaches:
        - Email: "Summarize the key decision or action item from this thread"
        - Invoice: "Extract vendor, total amount, and key line items"
        - Manual: "Summarize the main procedure or instruction"
        - Report: "Summarize key findings and recommendations"

        Args:
            text: Document text
            metadata: Document metadata

        Returns:
            Specialized summary prompt
        """
        pass

    def should_chunk_together(self, chunks: List[str], metadata: Dict[str, Any]) -> bool:
        """
        Decide if multiple chunks should be kept together.

        Override for types where context is critical (e.g., email threads,
        multi-turn conversations).

        Args:
            chunks: List of chunk texts
            metadata: Document metadata

        Returns:
            True if chunks should be combined
        """
        return False

    def validate_preprocessing(self, original: str, processed: str) -> bool:
        """
        Validate that preprocessing didn't remove critical content.

        Override to add type-specific validation rules.

        Args:
            original: Original text
            processed: Preprocessed text

        Returns:
            True if preprocessing is valid
        """
        # Basic sanity check: processed shouldn't be too much shorter
        if len(processed) < len(original) * 0.3:
            self.logger.warning(f"Preprocessing removed >70% of content ({len(original)} → {len(processed)} chars)")
            return False
        return True
