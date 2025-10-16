"""
Enrichment Service V2 - Controlled Vocabulary & Advanced Features

Major improvements:
- Controlled vocabulary (no invented tags)
- Entities vs Topics separation
- Suggested tags for review
- Recency scoring
- Better title extraction
- Document type routing
"""

import hashlib
import json
import re
import math
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from src.services.llm_service import LLMService
from src.services.vocabulary_service import VocabularyService
from src.services.entity_deduplication_service import get_entity_deduplication_service
from src.models.schemas import DocumentType, SemanticDocumentType
from src.services.document_type_handlers import (
    EmailHandler,
    ChatLogHandler,
    ScannedDocHandler,
    InvoiceHandler,
    ManualHandler,
)

# Self-improvement loop imports
import logging

logger = logging.getLogger(__name__)


class EnrichmentService:
    """Enhanced enrichment with controlled vocabulary (formerly V2)"""

    def __init__(self, llm_service: LLMService, vocab_service: Optional[VocabularyService] = None):
        self.llm_service = llm_service

        # Load vocabulary service
        if vocab_service:
            self.vocab = vocab_service
        else:
            # Try to load from default location
            try:
                self.vocab = VocabularyService("vocabulary")
            except Exception as e:
                logger.warning(f"Could not load vocabulary service: {e}")
                self.vocab = None

        # Load entity deduplication service
        self.entity_dedup = get_entity_deduplication_service(similarity_threshold=0.85)

        # Initialize document type handlers for type-specific processing
        self.email_handler = EmailHandler()
        self.chat_log_handler = ChatLogHandler()
        self.scanned_doc_handler = ScannedDocHandler()
        self.invoice_handler = InvoiceHandler()
        self.manual_handler = ManualHandler()

    def generate_content_hash(self, content: str) -> str:
        """Generate SHA-256 hash for deduplication"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def extract_dates_from_content(self, content: str) -> List[str]:
        """
        Extract dates from content using regex patterns

        Patterns supported:
        - YYYY-MM-DD (ISO format)
        - DD.MM.YYYY (German format)
        - DD/MM/YYYY
        - Month DD, YYYY
        """
        dates = set()

        # ISO format: 2025-10-07, 2024-01-20
        iso_pattern = r'\b(\d{4}-\d{2}-\d{2})\b'
        for match in re.finditer(iso_pattern, content):
            dates.add(match.group(1))

        # German format: 07.10.2025, 22.08.2025
        german_pattern = r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b'
        for match in re.finditer(german_pattern, content):
            day, month, year = match.groups()
            # Convert to ISO format
            try:
                iso_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                # Validate date
                datetime.strptime(iso_date, '%Y-%m-%d')
                dates.add(iso_date)
            except ValueError:
                pass  # Invalid date, skip

        # Slash format: 10/07/2025
        slash_pattern = r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b'
        for match in re.finditer(slash_pattern, content):
            day, month, year = match.groups()
            try:
                iso_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                datetime.strptime(iso_date, '%Y-%m-%d')
                dates.add(iso_date)
            except ValueError:
                pass

        return sorted(list(dates))

    def extract_numbers_from_content(self, content: str) -> List[str]:
        """
        Extract significant numbers from content

        Patterns:
        - Case numbers (e.g., "310 F 141/25")
        - Phone numbers (e.g., "+49-123-456-789")
        - Amounts with currency (e.g., "€1,500", "$10,472")
        - Percentages (e.g., "79%", "64.5%")
        - Account numbers, IBANs
        - Times (e.g., "18:00", "7:00 Uhr")
        """
        numbers = set()

        # Case numbers: 310 F 141/25, 12-63 Nr. 2
        case_pattern = r'\b(\d{1,4}\s*[A-Z]?\s*\d{1,4}/\d{2,4})\b'
        for match in re.finditer(case_pattern, content):
            numbers.add(match.group(1))

        # BASS/regulation numbers: 12-63 Nr. 2
        reg_pattern = r'\b(\d{1,3}-\d{1,3}\s*Nr\.\s*\d+)\b'
        for match in re.finditer(reg_pattern, content):
            numbers.add(match.group(1))

        # Phone numbers: +49-123-456-789, +49 123 456 789
        phone_pattern = r'\+?\d{1,3}[\s-]?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}'
        for match in re.finditer(phone_pattern, content):
            numbers.add(match.group(0))

        # Currency amounts: €1,500 or $10,472
        currency_pattern = r'[€$£]\s*[\d,]+(?:\.\d{2})?'
        for match in re.finditer(currency_pattern, content):
            numbers.add(match.group(0))

        # Percentages: 79%, 64.5%
        percentage_pattern = r'\b(\d{1,3}(?:\.\d+)?%)\b'
        for match in re.finditer(percentage_pattern, content):
            numbers.add(match.group(1))

        # IBANs: DE89370400440532013000
        iban_pattern = r'\b([A-Z]{2}\d{2}[A-Z0-9]{12,30})\b'
        for match in re.finditer(iban_pattern, content):
            numbers.add(match.group(1))

        # Account numbers: 1234-5678-9012
        account_pattern = r'\b(\d{4}-\d{4}-\d{4})\b'
        for match in re.finditer(account_pattern, content):
            numbers.add(match.group(1))

        # Times: 18:00, 7:00 Uhr
        time_pattern = r'\b(\d{1,2}:\d{2}(?:\s*(?:Uhr|AM|PM|am|pm))?)\b'
        for match in re.finditer(time_pattern, content):
            numbers.add(match.group(1))

        # Limit to reasonable number of extractions (avoid spam)
        numbers_list = sorted(list(numbers))
        return numbers_list[:50]  # Max 50 numbers

    def extract_people_from_content(self, content: str) -> List[Dict[str, str]]:
        """
        Fallback: Extract people from content using regex patterns

        Patterns:
        - Names with titles (Dr., Prof., Mr., Mrs., etc.)
        - Names with roles in parentheses: "John Smith (Manager)"
        - Email addresses → extract name before @
        - Phone with name context: "Contact John at +49..."
        """
        people = []
        seen_names = set()

        # Pattern: Title + Name (e.g., "Dr. Maria Schmidt", "Prof. Weber")
        title_pattern = r'\b(?:Dr\.|Prof\.|Mr\.|Mrs\.|Ms\.|Herr|Frau|Rechtsanwalt|Richterin?)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*)\b'
        for match in re.finditer(title_pattern, content):
            name = match.group(0).strip()
            if name not in seen_names and len(name) > 3:
                people.append({"name": name})
                seen_names.add(name)

        # Pattern: Name (Role) - e.g., "John Smith (Manager)", "Anna Lins (daughter)"
        role_pattern = r'\b([A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+)\s*\(([^)]+)\)'
        for match in re.finditer(role_pattern, content):
            name = match.group(1).strip()
            role = match.group(2).strip()
            if name not in seen_names:
                people.append({"name": name, "role": role})
                seen_names.add(name)

        # Pattern: Email → extract name
        email_pattern = r'\b([a-zA-Z0-9._%+-]+)@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
        for match in re.finditer(email_pattern, content):
            email = match.group(0)
            # Extract potential name from email (first.last@domain → First Last)
            local_part = match.group(1)
            if '.' in local_part:
                parts = local_part.split('.')
                name = ' '.join(p.capitalize() for p in parts if len(p) > 1)
                if name not in seen_names and len(name) > 3:
                    people.append({"name": name, "email": email})
                    seen_names.add(name)

        # Limit results
        return people[:20]  # Max 20 people

    def calculate_recency_score(self, created_at: Optional[date] = None) -> float:
        """
        Calculate recency score with exponential decay

        - Today = 1.0
        - 1 month ago = 0.9
        - 6 months ago = 0.6
        - 1 year ago = 0.4
        - 2 years ago = 0.2
        - 5+ years ago = 0.05
        """
        if not created_at:
            created_at = date.today()

        today = date.today()
        age_days = (today - created_at).days

        # Exponential decay: score = e^(-lambda * age_days)
        # lambda = 0.003 gives ~6 month half-life
        decay_rate = 0.003
        score = math.exp(-decay_rate * age_days)

        return max(0.05, min(1.0, score))  # Clamp to [0.05, 1.0]

    def extract_title_from_content(self, content: str, filename: str) -> str:
        """
        Extract title using multiple strategies with document type detection

        1. Legal document patterns (court decisions, case numbers)
        2. Invoice/financial patterns
        3. School/education patterns
        4. Markdown headings
        5. Title: field
        6. First meaningful sentence
        7. Cleaned filename fallback
        """
        # Strategy 0a: Legal court decision pattern
        # Pattern: "Amtsgericht [City]" or "Landgericht [City]"
        court_match = re.search(r'(Amtsgericht|Landgericht|Oberlandesgericht)\s+([A-ZÄÖÜ][a-zäöüß]+)', content[:1000])
        case_number_match = re.search(r'(\d{1,4}\s*[A-Z]?\s*\d{1,4}/\d{2,4})', content[:1000])
        if court_match and case_number_match:
            court_name = court_match.group(1) + " " + court_match.group(2)
            case_num = case_number_match.group(1).strip()
            return self.sanitize_title(f"{court_name} - {case_num}")

        # Strategy 0b: Invoice pattern
        invoice_match = re.search(r'Invoice\s*#?\s*(\d{4}-\d+|\d+)', content[:500], re.IGNORECASE)
        if invoice_match:
            invoice_num = invoice_match.group(1)
            # Try to find client/vendor
            client_match = re.search(r'(?:Client|Customer|For):\s*([A-Z][a-zA-Z\s&]+)', content[:500])
            if client_match:
                client = client_match.group(1).strip()[:30]
                return self.sanitize_title(f"Invoice {invoice_num} - {client}")
            return self.sanitize_title(f"Invoice {invoice_num}")

        # Strategy 0c: School enrollment/education pattern
        school_patterns = [
            (r'Einschulung\s+(\d{4}[/-]\d{2,4})', "Einschulung"),
            (r'Schuleingangsuntersuchung', "Schuleingangsuntersuchung"),
            (r'OGS[-\s]+(Anmeldung|Vertrag|Betreuung)', "OGS"),
        ]
        for pattern, prefix in school_patterns:
            match = re.search(pattern, content[:500], re.IGNORECASE)
            if match:
                if match.groups():
                    return self.sanitize_title(f"{prefix} {match.group(1)}")
                return self.sanitize_title(prefix)

        # Strategy 0d: Email Subject line (emails, newsletters)
        # Pattern: "Subject: ..." at start of content (from email parsing)
        subject_match = re.search(r'^Subject:\s*(.+)$', content[:500], re.MULTILINE | re.IGNORECASE)
        if subject_match:
            subject = subject_match.group(1).strip()
            # Remove common email prefixes
            subject = re.sub(r'^(Re:|RE:|Fwd:|FWD:|Fw:)\s*', '', subject, flags=re.IGNORECASE).strip()
            words = subject.split()
            if 3 <= len(words) <= 20:
                return self.sanitize_title(subject)

        # Strategy 1: Markdown heading (handle both with and without newlines)
        heading_match = re.search(r'^#\s+([^\n#]+)', content, re.MULTILINE)
        if heading_match:
            title = heading_match.group(1).strip()
            if 3 <= len(title.split()) <= 20:
                return self.sanitize_title(title)

        # Fallback: If newlines are stripped, look for first # up to next #
        heading_match_alt = re.search(r'#\s+([^#]+?)(?:\s*#{2,}|$)', content)
        if heading_match_alt:
            title = heading_match_alt.group(1).strip()
            words = title.split()
            if 3 <= len(words) < 20:
                if len(words) > 15:
                    words = words[:15]
                return self.sanitize_title(' '.join(words))

        # Strategy 2: Title: field
        title_field = re.search(r'^Title:\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if title_field:
            title = title_field.group(1).strip()
            if 3 <= len(title.split()) <= 20:
                return self.sanitize_title(title)

        # Strategy 3: First meaningful sentence (not too short, not too long)
        sentences = re.split(r'[.!?]\s+', content[:500])
        for sentence in sentences:
            words = sentence.strip().split()
            if 7 <= len(words) <= 15:
                return self.sanitize_title(sentence.strip())

        # Strategy 4: Clean up filename
        title = Path(filename).stem
        # Remove upload UUIDs
        title = re.sub(r'upload_[a-f0-9-]{30,}', '', title, flags=re.IGNORECASE)
        # Remove common prefixes
        title = re.sub(r'^(document|file|untitled|scan)[-_\s]*', '', title, flags=re.IGNORECASE)

        # Remove email ID suffixes (e.g., "-72851", "-9087")
        title = re.sub(r'-\d{4,5}$', '', title)

        # Remove date prefixes for emails (YYYYMMDD- pattern)
        title = re.sub(r'^\d{8}-', '', title)

        # Replace separators with spaces
        title = title.replace('_', ' ').replace('-', ' ')
        title = re.sub(r'\s+', ' ', title).strip()

        return self.sanitize_title(title) if title else "Document"

    def sanitize_title(self, title: str, max_length: int = 100) -> str:
        """Clean and normalize title"""
        # Remove extra whitespace
        sanitized = re.sub(r'\s+', ' ', title).strip()

        # Remove special characters that cause issues (but keep content inside brackets)
        # First extract content from brackets/parens
        sanitized = re.sub(r'[\[\(]([^\]\)]+)[\]\)]', r'\1', sanitized)
        # Then remove remaining special chars
        sanitized = re.sub(r'[<>:"/\\|?*]', '', sanitized)

        # Clean up extra whitespace and dashes from removals
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        sanitized = re.sub(r'^[-:\s]+|[-:\s]+$', '', sanitized)

        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip()

        return sanitized or "Document"

    async def classify_semantic_document_type(
        self,
        content: str,
        filename: str,
        title: str
    ) -> str:
        """
        Classify document into semantic type using keyword matching + LLM fallback

        Returns: semantic document type string (e.g., "legal/law", "form/questionnaire")
        """
        # Fast keyword-based classification first
        content_lower = content[:2000].lower()
        filename_lower = filename.lower()

        # Legal documents
        if any(word in content_lower for word in ['urteil', 'beschluss', 'gericht', 'richter', 'klage']):
            if 'urteil' in content_lower or 'beschluss' in content_lower:
                return SemanticDocumentType.legal_court_decision.value
        if any(word in content_lower for word in ['schulgesetz', 'bass', '§', 'artikel', 'gesetz']):
            return SemanticDocumentType.legal_law.value
        if 'vertrag' in content_lower and 'vereinbarung' in content_lower:
            return SemanticDocumentType.legal_contract.value

        # Forms
        if 'fragebogen' in filename_lower or 'questionnaire' in content_lower:
            return SemanticDocumentType.form_questionnaire.value
        if 'checkliste' in filename_lower or 'checklist' in content_lower or 'zeitstrahl' in filename_lower:
            return SemanticDocumentType.form_checklist.value
        if 'anmeldung' in filename_lower or 'application' in content_lower:
            return SemanticDocumentType.form_application.value

        # Education
        if 'transcript' in filename_lower:
            return SemanticDocumentType.education_transcript.value
        if any(word in content_lower for word in ['course', 'lecture', 'lesson', 'curriculum']):
            return SemanticDocumentType.education_course_material.value

        # Reference materials
        if 'broschüre' in filename_lower or 'brochure' in content_lower:
            return SemanticDocumentType.reference_brochure.value
        if 'faq' in filename_lower:
            return SemanticDocumentType.reference_faq.value
        if any(word in filename_lower for word in ['leitfaden', 'guide', 'handbuch']):
            return SemanticDocumentType.reference_guide.value
        if any(word in filename_lower for word in ['verzeichnis', 'standorte', 'liste', 'directory']):
            return SemanticDocumentType.reference_directory.value
        if any(word in content_lower for word in ['bericht', 'report', 'empfehlungen', 'expertenbeirat']):
            return SemanticDocumentType.reference_report.value

        # Communication
        if any(word in content_lower for word in ['meeting notes', 'besprechung', 'protokoll']):
            return SemanticDocumentType.communication_meeting_notes.value

        # Financial
        if 'rechnung' in content_lower or 'invoice' in content_lower:
            return SemanticDocumentType.financial_invoice.value
        if 'quittung' in content_lower or 'receipt' in content_lower or 'beleg' in content_lower:
            return SemanticDocumentType.financial_receipt.value

        # Government/Policy
        if any(word in content_lower for word in ['verordnung', 'erlass', 'regulation']):
            return SemanticDocumentType.government_regulation.value
        if 'policy' in content_lower or 'richtlinie' in content_lower:
            return SemanticDocumentType.government_policy.value

        # If no keyword match, use LLM for classification from controlled vocabulary
        allowed_types = self.vocab.get_all_document_types() if self.vocab else []

        # Format types list for LLM prompt
        types_list = "\n".join([f"- {t}" for t in allowed_types])

        prompt = f"""Classify this document into ONE semantic type from the controlled vocabulary below.

Document title: {title}
Filename: {filename}
Content preview: {content[:800]}

Choose ONLY ONE from these document types:
{types_list}

Return ONLY the document type string (e.g., "legal/court-decision"), nothing else."""

        try:
            # Use Groq 3.3 70B for classification (Oct 2025: Anthropic out of credits)
            response, _, _ = await self.llm_service.call_llm(
                prompt=prompt,
                model_id="groq/llama-3.3-70b-versatile",
                temperature=0.0
            )
            doc_type = response.strip().lower()

            # Validate against vocabulary
            if self.vocab and self.vocab.is_valid_document_type(doc_type):
                return doc_type

            # Try fuzzy matching
            if self.vocab:
                suggested = self.vocab.suggest_document_type(doc_type)
                if suggested != doc_type:
                    logger.info(f"Document type fuzzy matched: {doc_type} → {suggested}")
                    return suggested

        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")

        return SemanticDocumentType.unknown.value

    def filter_people_by_document_type(
        self,
        people: List[Dict],
        document_type: str,
        content: str
    ) -> List[Dict]:
        """
        Filter and prioritize people based on document type context

        Examples:
        - Reports with 28 authors → Keep max 5 primary authors
        - Meeting notes → Keep all attendees
        - Legal docs → Keep parties, lawyers, judges
        - Forms → Keep form subject (person filling it out)
        """
        if not people:
            return []

        # For reports: Limit to first 5 authors if there are many
        if document_type.startswith('reference/report') or document_type.startswith('government/'):
            if len(people) > 10:
                # Likely author list - keep first few
                logger.debug(f"Report with {len(people)} people → keeping first 5 primary authors")
                return people[:5]

        # For legal documents: Prioritize parties, lawyers, judges
        if document_type.startswith('legal/'):
            # Filter people with roles like judge, lawyer, plaintiff, defendant
            priority_roles = ['richter', 'anwalt', 'kläger', 'beklagt', 'judge', 'lawyer', 'attorney']
            priority_people = [
                p for p in people
                if any(role in str(p.get('role', '')).lower() for role in priority_roles)
            ]
            if priority_people:
                logger.debug(f"Legal doc: keeping {len(priority_people)} parties/lawyers/judges from {len(people)} total")
                return priority_people[:10]

        # For educational materials: Keep instructors, not all mentioned names
        if document_type.startswith('education/'):
            # In transcripts/course materials, often mentions many historical figures
            # Keep people with explicit roles (instructor, professor) or mentioned multiple times
            instructor_people = [
                p for p in people
                if any(role in str(p.get('role', '')).lower() for role in ['instructor', 'professor', 'teacher', 'dozent'])
            ]
            if instructor_people:
                logger.debug(f"Educational doc: keeping {len(instructor_people)} instructors from {len(people)} total")
                return instructor_people[:5]
            # If no explicit instructors, keep max 5
            if len(people) > 5:
                logger.debug(f"Educational doc: limiting to 5 key people from {len(people)} total")
                return people[:5]

        # For brochures/marketing: Usually don't need person extraction
        if document_type.startswith('reference/brochure'):
            # Keep only people with explicit contact info or roles
            contact_people = [
                p for p in people
                if p.get('email') or p.get('phone') or p.get('role')
            ]
            if len(contact_people) < len(people):
                logger.debug(f"Brochure: keeping {len(contact_people)} contacts from {len(people)} mentioned people")
                return contact_people

        # For forms/questionnaires: Keep all (these are important people)
        if document_type.startswith('form/'):
            # Forms contain relevant people (form subjects)
            logger.debug(f"Form: keeping all {len(people)} people (relevant)")
            return people

        # For meeting notes: Keep all attendees
        if document_type.startswith('communication/meeting'):
            logger.debug(f"Meeting notes: keeping all {len(people)} attendees")
            return people

        # Default: Limit to reasonable number
        if len(people) > 15:
            logger.debug(f"Default: limiting to 15 people from {len(people)} total")
            return people[:15]

        return people

    def deduplicate_people(
        self,
        people: List[Dict],
        document_id: str
    ) -> List[Dict]:
        """
        Deduplicate people entities using EntityDeduplicationService

        Args:
            people: List of person objects with 'name' field
            document_id: Source document ID for tracking

        Returns:
            Deduplicated list of people with canonical names
        """
        if not people:
            return []

        deduplicated = []
        seen_canonical = set()

        for person in people:
            name = person.get("name", "")
            if not name:
                continue

            # Add entity to deduplication service (it handles matching)
            entity = self.entity_dedup.add_entity(
                name=name,
                entity_type="person",
                document_id=document_id
            )

            if entity:
                canonical = entity.canonical_name

                # Skip if we've already added this canonical entity
                if canonical in seen_canonical:
                    logger.debug(f"Skipping duplicate: '{name}' → '{canonical}' (already added)")
                    continue

                seen_canonical.add(canonical)

                # Use canonical name but preserve other fields
                deduplicated_person = person.copy()
                deduplicated_person["name"] = canonical
                deduplicated_person["aliases"] = list(entity.aliases) if len(entity.aliases) > 1 else None
                deduplicated_person["mention_count"] = entity.mentions_count

                deduplicated.append(deduplicated_person)

        logger.info(f"Deduplicated {len(people)} people → {len(deduplicated)} unique entities")
        return deduplicated

    async def enrich_document(
        self,
        content: str,
        filename: str,
        document_type: DocumentType,
        created_at: Optional[date] = None,
        existing_metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Main enrichment function with controlled vocabulary

        Returns enriched metadata compatible with ChromaDB
        """
        existing_metadata = existing_metadata or {}

        # Generate content hash
        content_hash = self.generate_content_hash(content)

        # Extract title first (don't rely on LLM for this)
        extracted_title = self.extract_title_from_content(content, filename)

        # Classify semantic document type
        semantic_doc_type = await self.classify_semantic_document_type(
            content, filename, extracted_title
        )
        logger.info(f"Document type: {semantic_doc_type}")

        # Calculate recency score
        recency_score = self.calculate_recency_score(created_at)

        # Build controlled vocabulary prompt
        prompt = self._build_controlled_enrichment_prompt(
            content=content,
            filename=filename,
            document_type=document_type,
            extracted_title=extracted_title,
            metadata=existing_metadata
        )

        try:
            # Use Groq Llama 3.3 70B for enrichment (ultra-fast, free, excellent quality)
            # Oct 2025: Anthropic out of credits, Groq 3.3 70B best free model available
            from src.models.enrichment_models import EnrichmentResponse

            llm_response, cost, model_used = await self.llm_service.call_llm_structured(
                prompt=prompt,
                response_model=EnrichmentResponse,
                model_id="groq/llama-3.3-70b-versatile",  # Oct 2025: Best free model (70B, 128k context)
                temperature=0.1
            )

            # Debug: Log structured LLM response
            logger.info("=" * 80)
            logger.info(f"🔍 LLM RESPONSE DEBUG:")
            logger.info(f"  - Title: {llm_response.title}")
            logger.info(f"  - Topics: {llm_response.topics}")
            logger.info(f"  - People: {len(llm_response.entities.people)}")
            logger.info(f"  - Organizations: {llm_response.entities.organizations}")
            logger.info(f"  - Technologies: {llm_response.entities.technologies}")  # KEY DEBUG LINE
            logger.info(f"  - Summary: {llm_response.summary[:100]}...")
            logger.info("=" * 80)

            # Convert Pydantic model to dict for backwards compatibility
            llm_data = llm_response.model_dump()

            # Debug: Log parsed data
            logger.debug("[DEBUG] Converted to Dict:")
            logger.debug(f"  - Topics: {llm_data.get('topics', [])}")
            logger.debug(f"  - People: {llm_data.get('entities', {}).get('people', [])}")
            logger.debug(f"  - Dates: {llm_data.get('entities', {}).get('dates', [])}")
            logger.debug(f"  - Empty? {len(llm_data) == 0}")

            # Extract dates, numbers, and people using regex (in addition to LLM extraction)
            regex_dates = self.extract_dates_from_content(content)
            regex_numbers = self.extract_numbers_from_content(content)
            regex_people = self.extract_people_from_content(content)

            # Merge LLM entities with regex extractions
            llm_entities = llm_data.get("entities", {})
            llm_dates = llm_entities.get("dates", [])
            llm_numbers = llm_entities.get("numbers", [])
            llm_people = llm_entities.get("people", [])

            # FALLBACK: Use regex-extracted people if LLM returned none
            if not llm_people:
                logger.debug(f"[FALLBACK] LLM returned no people, using regex extraction: {len(regex_people)} found")
                llm_people = regex_people

            # Filter people by document type (context-aware)
            llm_people = self.filter_people_by_document_type(
                llm_people, semantic_doc_type, content
            )

            # Deduplicate people entities (NEW: cross-reference resolution)
            llm_people = self.deduplicate_people(llm_people, filename)

            # Combine and deduplicate dates (handle both dict and string formats)
            all_dates = []
            seen_dates = set()

            for d in llm_dates + regex_dates:
                # Extract date string (dict or string)
                date_str = d.get('date', d) if isinstance(d, dict) else d
                if date_str not in seen_dates:
                    seen_dates.add(date_str)
                    all_dates.append(d)  # Keep original format (dict or string)

            # Deduplicate numbers (simple strings/numbers)
            all_numbers = list(set(llm_numbers + regex_numbers))

            # Update entities with merged data (preserve all fields!)
            llm_entities["people"] = llm_people[:20]  # Max 20 people
            llm_entities["dates"] = sorted(all_dates, key=lambda x: x.get('date', x) if isinstance(x, dict) else x)[:30]  # Max 30 dates
            llm_entities["numbers"] = sorted(all_numbers)[:50]  # Max 50 numbers
            # IMPORTANT: Preserve organizations, places, technologies from LLM response
            # (they were already extracted, don't lose them!)
            llm_data["entities"] = llm_entities

            logger.info(f"🔍 AFTER ENTITY MERGING:")
            logger.info(f"  - People: {len(llm_entities.get('people', []))}")
            logger.info(f"  - Dates: {len(llm_entities.get('dates', []))}")
            logger.info(f"  - Technologies: {llm_entities.get('technologies', [])}") # KEY DEBUG

            # Validate and clean with controlled vocabulary
            validated = self._validate_with_vocabulary(llm_data, created_at)

            logger.info(f"🔍 AFTER VALIDATION:")
            logger.info(f"  - Technologies: {validated.get('entities', {}).get('technologies', [])}")  # KEY DEBUG

            # Build enriched metadata
            enriched = self._build_enriched_metadata(
                validated_data=validated,
                content_hash=content_hash,
                filename=filename,
                document_type=document_type,
                extracted_title=extracted_title,
                recency_score=recency_score,
                content=content,
                existing_metadata=existing_metadata,
                enrichment_cost=cost
            )

            logger.info(f"🔍 FINAL METADATA (in enriched):")
            logger.info(f"  - Technologies: {enriched.get('entities', {}).get('technologies', [])}") # KEY DEBUG

            # Add semantic document type to metadata
            enriched["semantic_document_type"] = semantic_doc_type

            # Debug: Check if people/dates are in enriched metadata
            logger.debug("[DEBUG] enriched metadata BEFORE return:")
            logger.debug(f"  - people: {enriched.get('people', 'NOT IN DICT')}")
            logger.debug(f"  - dates: {enriched.get('dates', 'NOT IN DICT')}")
            logger.debug(f"  - dates_detailed: {enriched.get('dates_detailed', 'NOT IN DICT')}\n")

            return enriched

        except Exception as e:
            logger.error(f"Enrichment V2 failed: {str(e)}", exc_info=True)

            # Fallback
            return self._fallback_metadata(
                content=content,
                content_hash=content_hash,
                filename=filename,
                document_type=document_type,
                extracted_title=extracted_title,
                recency_score=recency_score,
                existing_metadata=existing_metadata
            )

    def _get_summary_instructions(self, document_type: DocumentType, metadata: Optional[Dict] = None) -> str:
        """
        Generate type-specific summary instructions.

        Different document types need different summarization approaches:
        - Email: Focus on decisions, action items, outcomes
        - Chat: Questions asked, solutions provided, code examples
        - Invoice: Extract vendor, amount, key line items
        - Manual: Capture main procedure or instruction
        - Scanned: Document type, parties, amounts, dates
        - Report: Key findings and recommendations
        - Default: 2-3 sentence general summary

        Args:
            document_type: Type of document
            metadata: Optional metadata that may contain handler-specific info

        Returns:
            Type-specific instructions for summary generation
        """
        # Check if a handler was applied and use its summary instructions
        if metadata and 'handler_applied' in metadata:
            handler_type = metadata['handler_applied']

            if handler_type == 'email':
                return self.email_handler.get_summary_prompt("", metadata)
            elif handler_type == 'chat_log':
                return self.chat_log_handler.get_summary_prompt("", metadata)
            elif handler_type == 'scanned_doc':
                return self.scanned_doc_handler.get_summary_prompt("", metadata)
            elif handler_type == 'invoice':
                return self.invoice_handler.get_summary_prompt("", metadata)
            elif handler_type == 'manual':
                return self.manual_handler.get_summary_prompt("", metadata)

        # Fallback to document type-based instructions
        if document_type == DocumentType.email:
            return """2-3 sentence summary focusing on:
   - The key decision or outcome (not just "discussion about X")
   - Action items or next steps
   - Important dates or deadlines
   - Be specific and actionable (e.g., "Decided to postpone project until March" not "Email discussing project timeline")"""

        elif document_type == DocumentType.llm_chat:
            return """2-3 sentence summary focusing on:
   - The main question(s) or problem being solved
   - The solution or approach discussed
   - Key code examples or implementations provided (if any)
   - Be specific about outcomes and actionable insights"""

        elif document_type == DocumentType.scanned:
            return """2-3 sentence summary capturing:
   - Document type (invoice, receipt, letter, form, etc.)
   - Key parties involved (vendor, customer, sender, recipient)
   - Main purpose or outcome
   - Important amounts, dates, or reference numbers"""

        elif document_type == DocumentType.text:
            # Could be manual, report, documentation, etc.
            return """2-3 sentence summary capturing:
   - Main topic or purpose
   - Key instructions, findings, or recommendations
   - Important warnings, requirements, or constraints (if present)"""

        elif document_type == DocumentType.office:
            return """2-3 sentence summary capturing:
   - Document purpose (presentation, report, spreadsheet analysis)
   - Main points, findings, or recommendations
   - Key data, conclusions, or next steps"""

        else:
            # Default for other types
            return "2-3 sentence summary of main content"

    def _build_controlled_enrichment_prompt(
        self,
        content: str,
        filename: str,
        document_type: DocumentType,
        extracted_title: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """Build enrichment prompt with controlled vocabulary"""

        # Get vocabulary lists
        all_topics = self.vocab.get_all_topics() if self.vocab else []
        all_places = self.vocab.get_all_places() if self.vocab else []

        # Truncate content (increased to 32000 for Groq 3.3 70B's 128k context window)
        # Using ~32k to allow room for prompt + vocabulary + response
        content_sample = content[:32000]
        if len(content) > 32000:
            content_sample += "\n\n[...content truncated...]"

        # Show ALL topics to LLM (no truncation - let LLM see full vocabulary)
        topic_examples = all_topics if all_topics else []

        prompt = f"""Extract metadata from this document using CONTROLLED VOCABULARIES.

⚠️⚠️⚠️ CRITICAL RULES ⚠️⚠️⚠️
1. Extract ONLY from the document content below - NOT from these instructions
2. If an entity type has zero matches in the document, return empty array []
3. DO NOT copy entities from previous documents or examples
4. DO NOT hallucinate or invent information
5. USE ONLY the controlled vocabulary provided

**Filename**: {filename}
**Type**: {document_type}
**Extracted Title**: {extracted_title}

**Content**:
{content_sample}

IMPORTANT: Use ONLY the provided controlled vocabulary. Do not invent new tags.

Extract the following (return as JSON):

1. **title**: Generate a clear, descriptive title (10-80 characters)
   - Review the extracted title: "{extracted_title}"
   - If it's good and descriptive, use it
   - If it's generic/poor (e.g., "Here are the key points", "Untitled", filename), create a better one from content
   - Format examples: "Q3 Launch: AI Integration Plan", "Legal Motion: Custody Modification", "ChatGPT: RAG Architecture Discussion"
   - Be specific and informative, not generic

2. **summary**: {self._get_summary_instructions(document_type, metadata)}

3. **topics**: Array of topics from this CONTROLLED list:
   {json.dumps(topic_examples)}

   CLASSIFICATION GUIDE (with examples):
   - AI/ML/LLM discussions → "technology/ai", "technology/machine-learning", "technology/llm", "technology/nlp"
   - RAG/embeddings/vector DBs → "technology/rag", "technology/embeddings", "technology/database"
   - Court documents, legal → "legal/court/decision", "legal/family", "legal/custody"
   - School enrollment → "education/school/enrollment", "education/school/ogs"
   - Financial → "business/accounting", "business/finance"
   - Technical docs/APIs → "technology/documentation", "technology/api"
   - Meetings → "meeting/notes", "meeting/agenda"
   - Privacy/data → "education/privacy", "education/data-protection"

   Only use topics from the controlled list above. Generate 8-15 relevant topics per document.
   Prefer specific topics (e.g., "technology/machine-learning") over generic ones (e.g., "technology/software").
   Include both broad and specific tags to enable flexible searching (e.g., "technology/ai", "technology/llm", "technology/rag").

4. **suggested_topics**: Array of NEW topics you think should be added to vocabulary
   (These will be reviewed by user, not used directly)

5. **entities**: Extract ONLY entities that are EXPLICITLY mentioned in the text:
   - organizations: Company/organization names that EXPLICITLY APPEAR in the document text above
   - people: Extract people as STRUCTURED OBJECTS ONLY if they are EXPLICITLY named in the document above.

     ⚠️ CRITICAL: DO NOT invent, hallucinate, or copy people from examples! ⚠️
     ⚠️ If NO people are mentioned by name, return an EMPTY people array [] ⚠️

     For each person EXPLICITLY named in the document, extract:
     * name: Full name EXACTLY as it appears in the document (REQUIRED)
     * role: Their role/function ONLY if stated in document
     * email: Email address ONLY if stated in document
     * phone: Phone number ONLY if stated in document
     * address: Physical address ONLY if stated in document
     * organization: Organization ONLY if stated in document
     * birth_date: Date of birth in YYYY-MM-DD ONLY if stated in document
     * relationships: Family/professional connections ONLY if stated in document
       Format: [{{"type": "father/mother/son/daughter/colleague/manager", "person": "Name"}}]

     Skip generic roles without specific names: "the lawyer", "a teacher", "User", "Assistant"

   - dates: Extract dates as STRUCTURED OBJECTS ONLY if EXPLICITLY mentioned in the document:
     * date: Date in ISO format YYYY-MM-DD (REQUIRED)
     * type: One of: "deadline", "meeting", "birthday", "event", "appointment"
     * description: Brief context about what this date represents

     ⚠️ Only extract dates that are ACTUALLY IN THE DOCUMENT - not from examples! ⚠️

   - numbers: Significant numbers that APPEAR in the document (case numbers, amounts, percentages)
     ⚠️ NOT phone/bank numbers (those belong in people/organization objects) ⚠️

   - technologies: List of all technologies/tools/platforms mentioned (e.g., OpenAI, ChromaDB, Docker, Python, RAG, embeddings, LLM, GPT-4, React, FastAPI, PostgreSQL, AWS, Kubernetes, machine learning, neural networks, etc.)
     Extract any technology names you see in the document content.

   ⚠️⚠️⚠️ FINAL WARNING ⚠️⚠️⚠️
   Extract ONLY from the document content shown above.
   Do NOT invent, hallucinate, or copy entities from instruction examples.
   If an entity type has no matches in the document, return an empty array [].

6. **places**: Places from content that match this list:
   {json.dumps(all_places[:15] if all_places else [])}
   Only use exact matches found in the text.

7. **quality_indicators**: Assess these (0-1 scores):
   - ocr_quality: How clean is the text? (1.0 = perfect, 0.5 = some issues, 0.0 = gibberish)
   - content_completeness: Is content complete? (1.0 = complete, 0.5 = partial, 0.0 = fragment)

Return ONLY this JSON structure (no markdown, no explanations):
{{
  "title": "Clear Descriptive Title (10-80 chars)",
  "summary": "Brief summary of the actual document content",
  "topics": ["topic1", "topic2"],
  "suggested_topics": ["new_topic_if_needed"],
  "entities": {{
    "organizations": ["ONLY_IF_MENTIONED_IN_DOCUMENT"],
    "people": [
      {{
        "name": "ONLY_USE_NAMES_FROM_DOCUMENT",
        "role": "ONLY_IF_MENTIONED",
        "email": "ONLY_IF_MENTIONED",
        "phone": "ONLY_IF_MENTIONED"
      }}
    ],
    "dates": [
      {{"date": "YYYY-MM-DD", "type": "deadline", "description": "ONLY_IF_MENTIONED"}}
    ],
    "numbers": ["ONLY_NUMBERS_FROM_DOCUMENT"],
    "technologies": ["ONLY_TECH_FROM_DOCUMENT"]
  }},
  "places": ["ONLY_PLACES_FROM_DOCUMENT"],
  "quality_indicators": {{
    "ocr_quality": 1.0,
    "content_completeness": 1.0
  }}
}}
"""
        return prompt

    def _parse_llm_response(self, response: str) -> Dict:
        """Parse LLM JSON response"""
        try:
            # Remove markdown code blocks
            cleaned = re.sub(r'^```json\n|\n```$', '', response.strip())
            cleaned = re.sub(r'^```\n|\n```$', '', cleaned.strip())
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return {}

    def _validate_with_vocabulary(self, llm_data: Dict, created_at: Optional[date]) -> Dict:
        """Validate extracted data against vocabulary, match projects"""

        validated = {}

        # Topics: Only keep valid ones
        proposed_topics = llm_data.get("topics", [])
        valid_topics = []
        invalid_topics = []

        if self.vocab:
            for topic in proposed_topics:
                if self.vocab.is_valid_topic(topic):
                    valid_topics.append(topic)
                else:
                    # Try to suggest closest match
                    suggested = self.vocab.suggest_topic(topic)
                    if self.vocab.is_valid_topic(suggested):
                        valid_topics.append(suggested)
                    else:
                        invalid_topics.append(topic)
        else:
            valid_topics = proposed_topics

        validated["topics"] = valid_topics
        validated["suggested_topics"] = llm_data.get("suggested_topics", []) + invalid_topics

        # Track suggested tags
        if self.vocab:
            for tag in validated["suggested_topics"]:
                self.vocab.track_suggestion(tag)

        # Places: Only keep valid ones
        proposed_places = llm_data.get("places", [])
        valid_places = []
        if self.vocab:
            valid_places = [p for p in proposed_places if self.vocab.is_valid_place(p)]
        else:
            valid_places = proposed_places

        validated["places"] = valid_places

        # Match projects based on topics
        matched_projects = []
        if self.vocab and valid_topics:
            matched_projects = self.vocab.match_projects_for_doc(valid_topics, created_at)

        validated["projects"] = matched_projects

        # Pass through other fields
        validated["summary"] = llm_data.get("summary", "")
        validated["entities"] = llm_data.get("entities", {})
        validated["quality_indicators"] = llm_data.get("quality_indicators", {})

        return validated

    def extract_enriched_lists(self, metadata: Dict) -> Dict:
        """Convert comma-separated strings OR lists in metadata to clean lists"""

        def to_list(value, field_name=""):
            """Convert CSV string or list to clean list"""
            if isinstance(value, list):
                return value
            elif isinstance(value, str):
                return [v.strip() for v in value.split(",") if v.strip()]
            else:
                return []

        # Handle people - can be list of objects or CSV string
        people_raw = metadata.get("people", metadata.get("people_roles", ""))
        if isinstance(people_raw, list):
            # List of person objects or strings
            people = [p.get("name") if isinstance(p, dict) else str(p) for p in people_raw]
        else:
            # CSV string
            people = to_list(people_raw)

        # Extract technologies from entities dict (new field!)
        entities = metadata.get("entities", {})
        technologies = entities.get("technologies", []) if isinstance(entities, dict) else []

        return {
            "tags": to_list(metadata.get("topics", "")),
            "key_points": [],  # Not stored in flat metadata
            "people": people,
            "organizations": to_list(metadata.get("organizations", "")),
            "locations": to_list(metadata.get("places", "")),
            "dates": to_list(metadata.get("dates", "")),
            "technologies": technologies if isinstance(technologies, list) else []  # FIX: Add technologies!
        }

    def _build_enriched_metadata(
        self,
        validated_data: Dict,
        content_hash: str,
        filename: str,
        document_type: DocumentType,
        extracted_title: str,
        recency_score: float,
        content: str,
        existing_metadata: Dict,
        enrichment_cost: float
    ) -> Dict:
        """Build flat metadata structure for ChromaDB"""

        # Get quality scores
        quality = validated_data.get("quality_indicators", {})
        ocr_quality = quality.get("ocr_quality", 0.8)
        completeness = quality.get("content_completeness", 1.0)

        # Calculate composite quality score
        quality_score = (ocr_quality * 0.6) + (completeness * 0.4)

        # Entities
        entities = validated_data.get("entities", {})

        # Handle structured dates (can be dicts or strings)
        dates_raw = entities.get("dates", [])
        dates_list = []  # Simple list for frontmatter
        dates_detailed = []  # Full objects with context

        for d in dates_raw:
            if isinstance(d, dict):
                dates_detailed.append(d)
                dates_list.append(d.get("date", ""))
            else:
                dates_list.append(d)
                dates_detailed.append({"date": d})

        # Define keys we're setting (to avoid duplicates from existing_metadata)
        # NOTE: Threading fields (thread_id, message_id, etc.) NOT in this list - they pass through from existing_metadata
        known_keys = {
            "content_hash", "content_hash_short", "filename", "document_type",
            "title", "summary", "topics", "places", "projects",
            "suggested_topics", "organizations", "people", "people_roles", "dates", "dates_detailed", "numbers", "contacts",
            "quality_score", "recency_score", "ocr_quality",
            "enrichment_version", "enrichment_date", "enrichment_cost",
            "word_count", "char_count", "created_at", "enriched", "entities"
        }

        # EXPLICIT: Preserve email threading metadata from existing_metadata
        threading_fields = ['thread_id', 'message_id', 'in_reply_to', 'references', 'sender', 'recipients', 'subject',
                           'thread_topic', 'thread_index', 'has_attachments', 'attachment_count', 'attachment_paths',
                           'is_attachment', 'parent_doc_id', 'parent_sender']

        metadata = {
            # === IDENTITY ===
            "content_hash": content_hash,
            "content_hash_short": content_hash[:16],
            "filename": filename,
            "document_type": str(document_type),

            # === TITLE & SUMMARY ===
            "title": extracted_title,
            "summary": validated_data.get("summary", "")[:500],

            # === CONTROLLED VOCABULARY ===
            "topics": ",".join(validated_data.get("topics", [])),  # Controlled
            "places": ",".join(validated_data.get("places", [])),  # Controlled
            "projects": ",".join(validated_data.get("projects", [])),  # Auto-matched

            # === SUGGESTED (for review) ===
            "suggested_topics": ",".join(validated_data.get("suggested_topics", [])),

            # === EXTRACTED ENTITIES (not controlled) ===
            "organizations": ",".join(entities.get("organizations", [])[:10]),
            "people": entities.get("people", [])[:20],  # NEW: list of person objects (not comma-separated)
            "people_roles": ",".join(entities.get("people_roles", [])[:10]),  # Legacy field
            "dates": dates_list[:30],  # NEW: list of date strings for frontmatter
            "dates_detailed": dates_detailed[:30],  # NEW: full date objects with context
            "numbers": ",".join(entities.get("numbers", [])[:50]),  # NEW: numbers
            "contacts": ",".join(entities.get("contacts", [])[:5]),

            # === ENTITIES DICT (for Obsidian frontmatter) ===
            "entities": {
                "people": entities.get("people", [])[:20],
                "organizations": entities.get("organizations", [])[:10],
                "places": entities.get("places", [])[:10],
                "dates": dates_list[:30],
                "dates_detailed": dates_detailed[:30],
                "numbers": entities.get("numbers", [])[:50],
                "technologies": entities.get("technologies", [])[:20]  # FIX: Add technologies!
            },

            # === SCORING ===
            "quality_score": round(quality_score, 3),
            "recency_score": round(recency_score, 3),
            "ocr_quality": round(ocr_quality, 3),

            # === PROVENANCE ===
            "enrichment_version": "2.0",
            "enrichment_date": datetime.now().isoformat(),
            "enrichment_cost": round(enrichment_cost, 6),

            # === STATS ===
            "word_count": len(content.split()),
            "char_count": len(content),

            # === TIMESTAMPS ===
            "created_at": datetime.now().isoformat(),
            "enriched": True,

            # === EMAIL THREADING (explicit preservation) ===
            **{k: existing_metadata.get(k, '') for k in threading_fields if k in existing_metadata},

            # Preserve other existing metadata (that aren't in our known keys)
            **{k: str(v) for k, v in existing_metadata.items()
               if isinstance(v, (str, int, float, bool, list)) and k not in known_keys and k not in threading_fields}
        }

        logger.info(f"📧 Threading preserved: thread_id={metadata.get('thread_id', 'MISSING')}, sender={metadata.get('sender', 'MISSING')[:30]}")

        return metadata

    async def critique_enrichment(
        self,
        content: str,
        enriched_metadata: Dict,
        filename: str
    ) -> Dict:
        """
        Critique enriched metadata using LLM-as-critic pattern

        Returns quality scores (0-5) for 7 rubrics:
        - schema_compliance: Required fields present, data types correct
        - entity_quality: Completeness and accuracy of extracted entities
        - topic_relevance: Appropriate controlled vocabulary usage
        - summary_quality: Conciseness, accuracy, key points captured
        - task_identification: Action items and deadlines extracted
        - privacy_assessment: PII detection and handling
        - chunking_suitability: Document structure analysis

        Plus overall quality score and improvement suggestions.
        """

        # Build critic prompt
        prompt = self._build_critic_prompt(content, enriched_metadata, filename)

        try:
            # Use Groq 3.3 70B for critic (Oct 2025: Anthropic out of credits)
            # 70B model provides good reasoning quality for critique
            critic_response, cost, model_used = await self.llm_service.call_llm(
                prompt=prompt,
                model_id="groq/llama-3.3-70b-versatile",
                temperature=0.0  # Deterministic scoring
            )

            # Parse critic response
            critique_data = self._parse_llm_response(critic_response)

            # Validate scores are in range 0-5
            scores = critique_data.get("scores", {})
            for key, value in scores.items():
                if not isinstance(value, (int, float)) or value < 0 or value > 5:
                    logger.warning(f"Invalid score for {key}: {value}, defaulting to 2.5")
                    scores[key] = 2.5

            # Calculate overall quality (weighted average)
            overall_quality = (
                scores.get("schema_compliance", 2.5) * 0.15 +
                scores.get("entity_quality", 2.5) * 0.25 +
                scores.get("topic_relevance", 2.5) * 0.20 +
                scores.get("summary_quality", 2.5) * 0.15 +
                scores.get("task_identification", 2.5) * 0.10 +
                scores.get("privacy_assessment", 2.5) * 0.10 +
                scores.get("chunking_suitability", 2.5) * 0.05
            )

            return {
                "scores": scores,
                "overall_quality": round(overall_quality, 2),
                "suggestions": critique_data.get("suggestions", []),
                "critic_model": model_used,
                "critic_cost": round(cost, 6),
                "critic_date": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Critic enrichment failed: {str(e)}")
            import traceback
            traceback.print_exc()

            # Fallback: neutral scores
            return {
                "scores": {
                    "schema_compliance": 2.5,
                    "entity_quality": 2.5,
                    "topic_relevance": 2.5,
                    "summary_quality": 2.5,
                    "task_identification": 2.5,
                    "privacy_assessment": 2.5,
                    "chunking_suitability": 2.5
                },
                "overall_quality": 2.5,
                "suggestions": ["Critic evaluation failed"],
                "critic_model": "fallback",
                "critic_cost": 0.0,
                "critic_date": datetime.now().isoformat()
            }

    def _build_critic_prompt(
        self,
        content: str,
        enriched_metadata: Dict,
        filename: str
    ) -> str:
        """Build critic prompt with 7-point rubric"""

        # Truncate content for context
        content_sample = content[:2000]
        if len(content) > 2000:
            content_sample += "\n\n[...truncated...]"

        # Format enriched metadata for review (hide complex fields)
        # Helper to handle both string and list formats
        def _to_list(value):
            if isinstance(value, list):
                return value
            elif isinstance(value, str) and value:
                return [v.strip() for v in value.split(",") if v.strip()]
            else:
                return []

        metadata_for_review = {
            "title": enriched_metadata.get("title", ""),
            "summary": enriched_metadata.get("summary", ""),
            "topics": _to_list(enriched_metadata.get("topics", [])),
            "people": enriched_metadata.get("people", [])[:5],  # Show first 5
            "organizations": _to_list(enriched_metadata.get("organizations", [])),
            "dates": enriched_metadata.get("dates", [])[:5],
            "places": _to_list(enriched_metadata.get("places", [])),
            "projects": _to_list(enriched_metadata.get("projects", [])),
            "quality_score": enriched_metadata.get("quality_score", 0.0)
        }

        prompt = f"""You are a quality critic for a RAG system. Evaluate the enrichment quality of this document.

**ORIGINAL DOCUMENT**
Filename: {filename}
Content (first 2000 chars):
{content_sample}

**ENRICHED METADATA** (generated by enrichment system):
{json.dumps(metadata_for_review, indent=2)}

**YOUR TASK**: Score the enrichment quality on 7 rubrics (0-5 scale):

1. **schema_compliance** (0-5):
   - 5: All required fields present (title, summary, topics), correct data types
   - 3: Most fields present, minor type issues
   - 1: Missing critical fields or major type errors
   - 0: Completely broken schema

2. **entity_quality** (0-5):
   - 5: All key entities extracted (people, orgs, dates), accurate and complete
   - 3: Most entities found, some minor omissions
   - 1: Many entities missing or inaccurate
   - 0: No entities or all wrong

3. **topic_relevance** (0-5):
   - 5: Topics perfectly match content, specific and relevant
   - 3: Topics mostly correct, could be more specific
   - 1: Topics generic or partially wrong
   - 0: Topics completely wrong or missing

4. **summary_quality** (0-5):
   - 5: Summary captures key points, concise (2-3 sentences), accurate
   - 3: Summary decent but misses some points or too long
   - 1: Summary vague, inaccurate, or way too long
   - 0: No summary or gibberish

5. **task_identification** (0-5):
   - 5: All action items and deadlines extracted
   - 3: Some tasks found, missing a few
   - 1: Tasks present but not extracted
   - 0: N/A (no tasks in document)

6. **privacy_assessment** (0-5):
   - 5: All PII identified, no privacy risks
   - 3: Most PII caught, minor risks
   - 1: Significant PII missed or exposed
   - 0: Critical privacy violation

7. **chunking_suitability** (0-5):
   - 5: Document structure clear, easy to chunk semantically
   - 3: Some structure, decent chunking possible
   - 1: Poor structure, hard to chunk well
   - 0: N/A (single paragraph document)

**SCORING GUIDELINES**:
- Be strict but fair
- Use 2.5 as neutral/acceptable baseline
- Score 4+ only for excellent quality
- Score 0 only if rubric is N/A or completely broken
- Consider the document type (legal docs need better entity extraction than brochures)

**SUGGESTIONS**: Provide 3-5 specific improvements (not generic advice).

Return ONLY this JSON structure (no markdown):
{{
  "scores": {{
    "schema_compliance": 4.5,
    "entity_quality": 3.5,
    "topic_relevance": 4.0,
    "summary_quality": 4.5,
    "task_identification": 0.0,
    "privacy_assessment": 4.0,
    "chunking_suitability": 3.5
  }},
  "suggestions": [
    "Add Dr. Schmidt's full contact details (email/phone visible in text)",
    "Extract deadline '15. Oktober' mentioned in paragraph 3",
    "Topics could be more specific: 'legal/court' → 'legal/court/family-custody'"
  ]
}}
"""
        return prompt

    def _fallback_metadata(
        self,
        content: str,
        content_hash: str,
        filename: str,
        document_type: DocumentType,
        extracted_title: str,
        recency_score: float,
        existing_metadata: Dict
    ) -> Dict:
        """Fallback metadata if enrichment fails"""

        return {
            "content_hash": content_hash,
            "content_hash_short": content_hash[:16],
            "filename": filename,
            "document_type": str(document_type),
            "title": extracted_title,
            "summary": content[:500],
            "topics": "",
            "places": "",
            "projects": "",
            "organizations": "",
            "quality_score": 0.5,
            "recency_score": round(recency_score, 3),
            "enrichment_version": "2.0",
            "enrichment_cost": 0.0,  # No LLM cost when fallback is used
            "enriched": False,
            "word_count": len(content.split()),
            "created_at": datetime.now().isoformat(),
            **{k: str(v) for k, v in existing_metadata.items() if isinstance(v, (str, int, float, bool))}
        }

    async def enrich_with_iteration(
        self,
        text: str,
        filename: str,
        max_iterations: int = 2,
        min_avg_score: float = 4.0,
        use_critic: bool = True
    ) -> Tuple[Dict, Optional[Dict]]:
        """
        Iterative enrichment with self-improvement loop

        Implements the full LLM-as-critic + LLM-as-editor pattern:
        1. Initial enrichment
        2. Critic scores it
        3. If score < threshold and iterations remaining:
           - Editor generates patch
           - Validate patch
           - Apply patch
           - Re-score with critic
        4. Return final enrichment + final critique

        Args:
            text: Document text to enrich
            filename: Original filename
            max_iterations: Maximum improvement iterations (default 2)
            min_avg_score: Minimum average score to accept (default 4.0)
            use_critic: Whether to use critic (default True)

        Returns:
            Tuple of (final_enrichment_metadata, final_critique_result)
        """
        from src.services.editor_service import EditorService
        from src.services.patch_service import PatchService
        from src.services.schema_validator import SchemaValidator

        # Initialize self-improvement components
        editor = EditorService(self.llm_service)
        patcher = PatchService()
        validator = SchemaValidator()

        # Initial enrichment
        logger.info("🌱 Starting iterative enrichment...")
        current_enrichment = await self.enrich_document(
            text, filename, document_type=None, existing_metadata={}
        )

        # If critic disabled, return immediately
        if not use_critic:
            logger.info("ℹ️ Critic disabled, returning initial enrichment")
            return current_enrichment, None

        final_critique = None

        for iteration in range(max_iterations):
            logger.info(f"🔄 Iteration {iteration + 1}/{max_iterations}")

            # Score current enrichment
            critique = await self.critique_enrichment(
                content=text,
                enriched_metadata=current_enrichment,
                filename=filename
            )
            final_critique = critique  # Store for return

            # Calculate average score
            scores_dict = critique["scores"]
            avg_score = sum(scores_dict.values()) / len(scores_dict)

            logger.info(f"📊 Average quality score: {avg_score:.2f}/5.0")

            # Check if we've met quality threshold
            if avg_score >= min_avg_score:
                logger.info(f"✅ Quality threshold reached: {avg_score:.2f} >= {min_avg_score}")
                break

            # Don't improve on last iteration (no point)
            if iteration == max_iterations - 1:
                logger.info(f"⚠️ Max iterations reached with score {avg_score:.2f}")
                break

            # Generate improvement patch
            logger.info("🔧 Generating improvement patch...")

            # Build controlled vocabulary context
            controlled_vocab = {}
            if self.vocab:
                controlled_vocab = {
                    "topics": self.vocab.get_all_topics(),
                    "projects": self.vocab.get_active_projects()  # Already returns list of strings
                }

            # Generate patch from critic suggestions
            patch = await editor.generate_patch(
                current_metadata=current_enrichment,
                critic_suggestions="\n".join(critique["suggestions"]),
                body_text=text,
                controlled_vocab=controlled_vocab
            )

            # Validate patch
            logger.info("✅ Validating patch against schema...")
            is_valid, errors = validator.validate_patch(
                current_enrichment,
                patch
            )

            if not is_valid and errors:
                logger.warning(f"⚠️ Patch validation warnings: {errors[:3]}")
                # Continue anyway with warnings

            # Apply patch
            try:
                logger.info("🔨 Applying patch...")
                patched_enrichment, diff = patcher.apply_patch(
                    original=current_enrichment,
                    patch=patch,
                    forbidden_paths=editor.FORBIDDEN_PATHS
                )

                # Log changes
                logger.info(f"📝 Patch applied:")
                logger.info(diff.get('summary', 'No changes'))

                # Update current enrichment
                current_enrichment = patched_enrichment

            except Exception as e:
                logger.error(f"❌ Failed to apply patch: {e}")
                # Continue with un-patched version
                break

        # Log final result
        if final_critique:
            scores_dict = final_critique["scores"]
            avg_score = sum(scores_dict.values()) / len(scores_dict)
            logger.info(f"🏁 Final quality score: {avg_score:.2f}/5.0")
            logger.info(f"   Iterations used: {iteration + 1}/{max_iterations}")

        return current_enrichment, final_critique

    def _get_controlled_vocabulary(self) -> Dict[str, List[str]]:
        """
        Get controlled vocabulary for editor context

        Returns:
            Dict with topics, projects, etc.
        """
        if not self.vocab:
            return {
                "topics": [],
                "projects": []
            }

        return {
            "topics": self.vocab.get_all_topics(),
            "projects": self.vocab.get_all_projects()
        }
