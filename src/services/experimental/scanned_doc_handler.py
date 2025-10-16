"""
ScannedDocHandler - Preprocessing for OCR'd documents (PDFs, images)

Key challenges:
- OCR errors and artifacts (random characters, broken words)
- Poor table formatting (columns misaligned)
- Header/footer duplication on every page
- Low confidence text regions
- Mixed content (text + tables + forms)

Strategy:
- Detect and flag low-quality OCR (lots of gibberish)
- Preserve table structures (don't break formatting)
- Remove repeated headers/footers
- Flag handwritten/unclear sections
- Extract structured data (forms, invoices)
"""

import re
import logging
from typing import Dict, Any
from collections import Counter

from .base_handler import DocumentTypeHandler

logger = logging.getLogger(__name__)


class ScannedDocHandler(DocumentTypeHandler):
    """Handler for scanned/OCR'd documents"""

    # OCR artifacts and noise patterns
    OCR_NOISE_PATTERNS = [
        r'[^\w\s\-.,;:!?()\[\]{}@#$%&*+=<>\'\"\/\\]+',  # Unusual characters
        r'\b[A-Za-z]{20,}\b',  # Suspiciously long words (likely OCR errors)
        r'[|]{2,}',  # Multiple pipes (table artifacts)
        r'[_]{5,}',  # Long underscores (form fields)
    ]

    # Common header/footer patterns
    HEADER_FOOTER_PATTERNS = [
        r'Page \d+ of \d+',
        r'Seite \d+ von \d+',
        r'^\d+\s*$',  # Lone page numbers
        r'^-+\s*$',  # Horizontal lines
        r'(Confidential|Vertraulich|Private).*?(Document|Dokument)',
    ]

    def preprocess(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        Clean OCR'd content:
        1. Detect OCR quality
        2. Remove repeated headers/footers
        3. Preserve table structures
        4. Flag low-confidence regions
        """
        original_length = len(text)

        # Check OCR quality (before cleaning)
        ocr_quality = self._assess_ocr_quality(text)
        metadata['ocr_quality'] = ocr_quality

        if ocr_quality < 0.5:
            logger.warning(f"⚠️  Low OCR quality ({ocr_quality:.2f}) - document may need re-scanning")

        # Preserve table regions (look for alignment patterns)
        # Tables typically have consistent spacing and vertical alignment
        lines = text.split('\n')

        # Remove repeated headers/footers
        # Find lines that appear on multiple "pages" (separated by form feeds)
        pages = text.split('\f')
        if len(pages) > 1:
            # Find common lines across pages (likely headers/footers)
            repeated_lines = self._find_repeated_lines(pages)

            # Remove these repeated lines
            cleaned_lines = []
            for line in lines:
                if line.strip() not in repeated_lines:
                    cleaned_lines.append(line)

            text = '\n'.join(cleaned_lines)
            logger.info(f"📄 Removed {len(repeated_lines)} repeated header/footer lines")

        # Clean excessive whitespace (but preserve table alignment)
        # Don't collapse spaces inside potential table rows
        cleaned_lines = []
        for line in text.split('\n'):
            # If line looks like a table row (multiple aligned columns), preserve spacing
            if re.search(r'\s{3,}', line) and len(line.split()) >= 3:
                cleaned_lines.append(line)  # Preserve table row
            else:
                cleaned_lines.append(' '.join(line.split()))  # Normal text cleanup

        text = '\n'.join(cleaned_lines)

        # Remove excessive blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        cleaned_length = len(text)
        retention_pct = (cleaned_length / original_length * 100) if original_length > 0 else 0

        logger.info(f"📄 Scanned doc cleaned: {original_length} → {cleaned_length} chars ({retention_pct:.1f}% retained)")

        return text

    def _assess_ocr_quality(self, text: str) -> float:
        """
        Assess OCR quality based on:
        - Ratio of dictionary words to total words
        - Presence of OCR artifacts
        - Average word length (too long = errors)
        """
        words = re.findall(r'\b\w+\b', text)
        if not words:
            return 0.0

        # Check for suspicious patterns
        artifact_count = 0
        for pattern in self.OCR_NOISE_PATTERNS:
            artifact_count += len(re.findall(pattern, text))

        # Long words are often OCR errors
        long_word_count = sum(1 for w in words if len(w) > 20)

        # Single-character "words" (OCR fragments)
        single_char_count = sum(1 for w in words if len(w) == 1)

        # Calculate quality score (0.0 = poor, 1.0 = excellent)
        total_words = len(words)
        artifact_ratio = artifact_count / total_words if total_words > 0 else 1.0
        long_word_ratio = long_word_count / total_words if total_words > 0 else 0.0
        single_char_ratio = single_char_count / total_words if total_words > 0 else 0.0

        quality = 1.0 - min(1.0, artifact_ratio + long_word_ratio + single_char_ratio)

        return quality

    def _find_repeated_lines(self, pages: list) -> set:
        """Find lines that appear in multiple pages (headers/footers)"""
        if len(pages) < 2:
            return set()

        # Get first 5 and last 5 lines from each page
        header_lines = []
        footer_lines = []

        for page in pages:
            lines = [l.strip() for l in page.split('\n') if l.strip()]
            if len(lines) >= 5:
                header_lines.extend(lines[:5])
                footer_lines.extend(lines[-5:])

        # Find lines appearing in >50% of pages
        threshold = len(pages) * 0.5
        repeated = set()

        for lines in [header_lines, footer_lines]:
            counter = Counter(lines)
            for line, count in counter.items():
                if count >= threshold and len(line) < 100:  # Not too long
                    repeated.add(line)

        return repeated

    def extract_metadata(self, text: str, existing_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract scanned document metadata:
        - OCR quality score
        - Has tables
        - Has forms (detected by underscores, checkboxes)
        - Document structure (header/body/footer)
        """
        metadata = {}

        # OCR quality already set in preprocess
        # (metadata dict is same object)

        # Detect tables (multiple aligned columns)
        has_tables = bool(re.search(r'.+\s{3,}.+\s{3,}.+', text))
        metadata['has_tables'] = has_tables

        # Detect forms (underscores for fill-in fields, checkboxes)
        has_forms = bool(re.search(r'_{5,}|☐|☑|\[\s?\]', text))
        metadata['has_forms'] = has_forms

        # Detect checkboxes/options
        checkbox_count = len(re.findall(r'☐|☑|\[\s?\]', text))
        metadata['checkbox_count'] = checkbox_count

        # Detect signature lines
        has_signature = bool(re.search(r'(Signature|Unterschrift).*?_+', text, re.IGNORECASE))
        metadata['has_signature'] = has_signature

        return metadata

    def get_chunking_strategy(self, metadata: Dict[str, Any]) -> str:
        """
        Scanned documents should preserve:
        - Tables as single chunks
        - Forms as single chunks
        - Otherwise semantic chunking
        """
        has_tables = metadata.get('has_tables', False)
        has_forms = metadata.get('has_forms', False)

        if has_forms:
            return 'whole'  # Keep forms intact
        elif has_tables:
            return 'section'  # Split by sections but preserve tables
        else:
            return 'semantic'  # Normal semantic chunking

    def get_summary_prompt(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        Scanned documents need summaries focused on:
        1. Document type (invoice, form, letter, certificate)
        2. Key parties (sender, recipient, issuer)
        3. Important dates and amounts
        4. Purpose or outcome
        """
        has_forms = metadata.get('has_forms', False)
        has_tables = metadata.get('has_tables', False)
        ocr_quality = metadata.get('ocr_quality', 1.0)

        prompt = """2-3 sentence summary capturing:
   - Document type (invoice, receipt, form, letter, certificate, etc.)
   - Key parties involved (sender, recipient, organization)
   - Main purpose or outcome"""

        if has_forms:
            prompt += "\n   - Form fields and their purposes"

        if has_tables:
            prompt += "\n   - Key information from tables (amounts, dates, items)"

        prompt += "\n   - Important amounts, dates, or reference numbers"

        if ocr_quality < 0.7:
            prompt += "\n   - Note: OCR quality is low, focus on clearly readable information"

        return prompt
