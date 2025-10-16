"""
ManualHandler - Preprocessing for technical documentation and manuals

Key challenges:
- Long hierarchical structure (chapters, sections, subsections)
- Code examples and technical diagrams
- Cross-references and table of contents
- Version-specific information
- Procedures and step-by-step instructions

Strategy:
- Preserve heading hierarchy for context
- Keep code examples intact
- Preserve numbered procedures
- Remove redundant ToC (we'll rebuild from headings)
- Extract version and product information
"""

import re
import logging
from typing import Dict, Any, List

from .base_handler import DocumentTypeHandler

logger = logging.getLogger(__name__)


class ManualHandler(DocumentTypeHandler):
    """Handler for technical documentation, manuals, and guides"""

    # Heading patterns (markdown and plain text)
    HEADING_PATTERNS = [
        r'^#{1,6}\s+.+$',  # Markdown headings
        r'^[A-Z][A-Za-z\s]+\n[=\-]+$',  # Underlined headings
        r'^\d+\.\s+[A-Z].+$',  # Numbered chapters (1. Introduction)
        r'^\d+\.\d+\s+.+$',  # Subsections (1.1 Overview)
    ]

    # Table of Contents patterns (to remove)
    TOC_PATTERNS = [
        r'(?:Table\s+of\s+Contents?|Contents?|Inhaltsverzeichnis).*?(?=\n\n[A-Z]|\n#{1,3}\s)',
        r'(?:Chapter|Section)\s+\d+.*?Page\s+\d+',
    ]

    # Code block preservation
    CODE_PATTERNS = [
        r'```[\s\S]*?```',  # Markdown code blocks
        r'    \w.*?(?:\n    |\n\n)',  # Indented code (4 spaces)
        r'(?:Example|Beispiel):.*?(?=\n\n[A-Z#])',  # Example sections
    ]

    # Version information
    VERSION_PATTERNS = [
        r'[Vv]ersion\s*:?\s*(\d+\.\d+(?:\.\d+)?)',
        r'[Rr]elease\s*:?\s*(\d+\.\d+(?:\.\d+)?)',
        r'[Dd]ate\s*:?\s*(\d{4}-\d{2}-\d{2}|\d{2}[./]\d{2}[./]\d{4})',
    ]

    # Procedure/instruction markers
    PROCEDURE_MARKERS = [
        r'(?:Step|Schritt)\s+\d+:',
        r'^\d+\)\s+',  # 1) Do this, 2) Do that
        r'^\d+\.\s+(?:[A-Z]|To\s)',  # 1. Click here, 2. Enter value
    ]

    def preprocess(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        Clean manual/documentation content:
        1. Remove redundant ToC (we can rebuild from headings)
        2. Preserve code blocks and examples
        3. Preserve heading hierarchy
        4. Remove page numbers and running headers
        5. Keep procedures intact
        """
        original_length = len(text)

        # Preserve code blocks first (so ToC removal doesn't touch them)
        code_blocks = []
        def preserve_code(match):
            code_blocks.append(match.group(0))
            return f"<<<CODE_BLOCK_{len(code_blocks)-1}>>>"

        for pattern in self.CODE_PATTERNS:
            text = re.sub(pattern, preserve_code, text, flags=re.MULTILINE | re.DOTALL)

        # Remove Table of Contents (usually early in document)
        for pattern in self.TOC_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE)

        # Remove page numbers and running headers
        # Common patterns: "Page 42", "Chapter 3 - Overview"
        text = re.sub(r'^Page\s+\d+.*?$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)  # Lone page numbers

        # Remove repeated copyright/footer text
        # Usually appears at bottom of each page
        copyright_pattern = r'(?:Copyright|©|\(c\)).*?(?:All rights reserved|Alle Rechte vorbehalten).*?(?=\n\n|\Z)'
        copyright_matches = list(re.finditer(copyright_pattern, text, re.IGNORECASE | re.DOTALL))

        if len(copyright_matches) > 2:  # Repeated on multiple pages
            # Keep only first occurrence, remove rest
            first_match = copyright_matches[0]
            for match in copyright_matches[1:]:
                text = text.replace(match.group(0), '')

        # Restore code blocks
        for i, code in enumerate(code_blocks):
            text = text.replace(f"<<<CODE_BLOCK_{i}>>>", code)

        # Clean excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        cleaned_length = len(text)
        retention_pct = (cleaned_length / original_length * 100) if original_length > 0 else 0

        logger.info(f"📖 Manual cleaned: {original_length} → {cleaned_length} chars ({retention_pct:.1f}% retained)")

        return text

    def extract_metadata(self, text: str, existing_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract manual-specific metadata:
        - Version/release number
        - Product name
        - Document date
        - Chapter/section count
        - Has procedures/instructions
        - Has code examples
        - Technical level (beginner/advanced)
        """
        metadata = {}

        # Extract version information
        for pattern in self.VERSION_PATTERNS:
            match = re.search(pattern, text[:2000], re.MULTILINE)  # Look in first 2000 chars
            if match:
                if 'version' not in metadata:
                    metadata['version'] = match.group(1)
                elif 'date' in match.group(0).lower() and 'document_date' not in metadata:
                    metadata['document_date'] = match.group(1)

        # Count headings/sections
        heading_count = 0
        for pattern in self.HEADING_PATTERNS:
            heading_count += len(re.findall(pattern, text, re.MULTILINE))
        metadata['section_count'] = heading_count

        # Detect procedures/instructions
        has_procedures = False
        procedure_count = 0
        for pattern in self.PROCEDURE_MARKERS:
            matches = re.findall(pattern, text, re.MULTILINE)
            if matches:
                has_procedures = True
                procedure_count += len(matches)

        metadata['has_procedures'] = has_procedures
        metadata['procedure_step_count'] = procedure_count

        # Detect code examples
        code_blocks = re.findall(r'```[\s\S]*?```', text)
        metadata['has_code_examples'] = len(code_blocks) > 0
        metadata['code_example_count'] = len(code_blocks)

        # Extract programming languages from code fences
        languages = set()
        for block in code_blocks:
            match = re.match(r'```(\w+)', block)
            if match:
                languages.add(match.group(1))
        metadata['programming_languages'] = list(languages)

        # Detect technical level (heuristic based on keywords)
        beginner_keywords = ['introduction', 'getting started', 'basics', 'tutorial', 'beginner']
        advanced_keywords = ['architecture', 'internals', 'optimization', 'advanced', 'performance']

        text_lower = text[:5000].lower()  # Check first 5000 chars
        beginner_score = sum(1 for kw in beginner_keywords if kw in text_lower)
        advanced_score = sum(1 for kw in advanced_keywords if kw in text_lower)

        if beginner_score > advanced_score:
            metadata['technical_level'] = 'beginner'
        elif advanced_score > beginner_score:
            metadata['technical_level'] = 'advanced'
        else:
            metadata['technical_level'] = 'intermediate'

        # Detect product/system name (usually in title or first heading)
        first_heading_match = re.search(r'^#{1,2}\s+(.+)$', text, re.MULTILINE)
        if first_heading_match:
            potential_product = first_heading_match.group(1).strip()
            # Remove common prefixes
            potential_product = re.sub(r'^(?:User\s+)?(?:Manual|Guide|Documentation|Reference)\s*:?\s*', '', potential_product, flags=re.IGNORECASE)
            if len(potential_product) > 3 and len(potential_product) < 100:
                metadata['product_name'] = potential_product

        # Count cross-references (links to other sections)
        xref_count = len(re.findall(r'(?:see|refer to|described in)\s+(?:section|chapter)\s+\d+', text, re.IGNORECASE))
        metadata['cross_reference_count'] = xref_count

        return metadata

    def get_chunking_strategy(self, metadata: Dict[str, Any]) -> str:
        """
        Manuals should be chunked by section/chapter:
        - Preserve heading hierarchy
        - Keep procedures together
        - Split long sections
        """
        section_count = metadata.get('section_count', 0)
        has_procedures = metadata.get('has_procedures', False)

        if section_count > 20:
            return 'section'  # Split by sections (chapters)
        elif has_procedures:
            return 'section'  # Keep each procedure as a chunk
        else:
            return 'semantic'  # Normal semantic chunking

    def get_summary_prompt(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        Manual summaries should capture:
        1. Product/system being documented
        2. Main purpose (installation, configuration, API reference, etc.)
        3. Target audience (developers, admins, end users)
        4. Key topics covered
        5. Version if applicable
        """
        has_code = metadata.get('has_code_examples', False)
        has_procedures = metadata.get('has_procedures', False)
        technical_level = metadata.get('technical_level', 'unknown')
        version = metadata.get('version', None)
        product = metadata.get('product_name', None)

        prompt = """2-3 sentence summary capturing:"""

        if product:
            prompt += f"\n   - Product/system: {product}"
        else:
            prompt += "\n   - Product or system being documented"

        if version:
            prompt += f" (version {version})"

        prompt += "\n   - Main purpose (installation guide, API reference, user manual, etc.)"
        prompt += f"\n   - Target audience ({technical_level} level)"

        if has_procedures:
            prompt += "\n   - Key procedures or tasks covered"

        if has_code:
            prompt += "\n   - Programming languages and technologies used"

        prompt += "\n   - Main topics and chapter structure"

        return prompt
