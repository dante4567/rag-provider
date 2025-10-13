"""
Smart Document Triage & Knowledge Graph Service

Intelligent processing that:
- Detects duplicates using multiple fingerprints (hash, metadata, fuzzy matching)
- Resolves entity aliases (Anika Teckentrup = Anika Kreuzer)
- Maintains personal knowledge base (addressbook, milestones, dates)
- Triages documents (junk/duplicate/actionable/archival/reference)
- Extracts actionable insights (dates, tasks, contact updates)
- Cross-references with existing knowledge
- Suggests actions ("Update addressbook: X married Y on DATE")
"""

import hashlib
import logging
import re
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict
import Levenshtein  # For fuzzy string matching

logger = logging.getLogger(__name__)


@dataclass
class DocumentFingerprint:
    """Multiple fingerprints for duplicate detection"""
    content_hash: str  # Full content SHA-256
    fuzzy_hash: str  # SimHash for near-duplicates
    metadata_hash: str  # Hash of key metadata fields
    title_normalized: str  # Normalized title
    first_100_chars: str  # First 100 chars (for quick comparison)
    word_count: int
    entity_signature: str  # Hash of extracted entities


@dataclass
class TriageDecision:
    """Triage decision with reasoning"""
    category: str  # junk, duplicate, actionable, archival, reference, personal
    confidence: float  # 0-1
    reasoning: List[str]  # Why this decision
    actions_suggested: List[str]  # What to do
    related_documents: List[str]  # Related doc IDs
    knowledge_updates: List[Dict]  # Updates to knowledge base


@dataclass
class EntityAlias:
    """Entity alias resolution"""
    canonical_name: str
    aliases: List[str]
    entity_type: str  # person, organization, location
    metadata: Dict  # Additional info


class SmartTriageService:
    """Intelligent document triage and knowledge management"""

    def __init__(self, collection=None):
        self.collection = collection

        # Personal knowledge base (would be loaded from storage)
        self.personal_kb = {
            "people": {
                # Known people with aliases and metadata
                "Anika Teckentrup": {
                    "aliases": ["Anika Kreuzer", "Anika T.", "Anika K."],
                    "relationship": "family",
                    "maiden_name": "Kreuzer",
                    "married_name": "Teckentrup",
                    "marriage_date": "2018-06-15",  # Example
                    "known_addresses": [],
                    "known_emails": [],
                    "known_phone_numbers": []
                },
                "Daniel Teckentrup": {
                    "aliases": ["Daniel T.", "DT"],
                    "relationship": "self",
                    "ssn": "***-**-****",  # Masked, stored securely
                    "date_of_birth": "****-**-**",
                    "milestones": []
                }
            },
            "organizations": {},
            "locations": {},
            "important_dates": {},  # Birthdays, anniversaries, etc.
            "categories": {
                # Document categorization rules
                "junk": ["spam", "advertisement", "promotional"],
                "personal": ["family", "medical", "financial"],
                "work": ["invoice", "contract", "agreement"],
                "reference": ["manual", "documentation", "guide"]
            }
        }

        # Document fingerprint cache
        self.fingerprint_cache = {}

    def generate_fingerprint(self, content: str, metadata: Dict, entities: Dict) -> DocumentFingerprint:
        """Generate multiple fingerprints for duplicate detection"""

        # 1. Full content hash
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        # 2. Fuzzy hash (SimHash approximation using word frequency)
        words = re.findall(r'\w+', content.lower())
        word_freq = defaultdict(int)
        for word in words[:1000]:  # First 1000 words
            word_freq[word] += 1
        # Simple hash based on most frequent words
        top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:50]
        fuzzy_hash = hashlib.md5(str(top_words).encode()).hexdigest()

        # 3. Metadata hash (key fields only)
        meta_str = f"{metadata.get('title', '')}{metadata.get('domain', '')}{metadata.get('created_at', '')}"
        metadata_hash = hashlib.md5(meta_str.encode()).hexdigest()

        # 4. Normalized title
        title_normalized = re.sub(r'[^a-z0-9]', '', metadata.get('title', '').lower())

        # 5. First 100 chars
        first_100 = content[:100].strip()

        # 6. Word count
        word_count = len(content.split())

        # 7. Entity signature (hash of all entities)
        entity_list = []
        for ent_type, ent_values in entities.items():
            if isinstance(ent_values, list):
                entity_list.extend(str(v) for v in ent_values)
        entity_signature = hashlib.md5(','.join(sorted(entity_list)).encode()).hexdigest()

        return DocumentFingerprint(
            content_hash=content_hash,
            fuzzy_hash=fuzzy_hash,
            metadata_hash=metadata_hash,
            title_normalized=title_normalized,
            first_100_chars=first_100,
            word_count=word_count,
            entity_signature=entity_signature
        )

    def find_duplicates(self, fingerprint: DocumentFingerprint, threshold: float = 0.85) -> List[Tuple[str, float, str]]:
        """Find duplicate/near-duplicate documents"""

        if not self.collection:
            return []

        duplicates = []

        try:
            # Search by content hash (exact duplicates)
            exact_matches = self.collection.get(
                where={"content_hash": fingerprint.content_hash},
                limit=10
            )

            if exact_matches and exact_matches.get('ids'):
                for doc_id in exact_matches['ids']:
                    duplicates.append((doc_id, 1.0, "exact_content_hash"))

            # Search by fuzzy hash (near-duplicates)
            fuzzy_matches = self.collection.get(
                where={"fuzzy_hash": fingerprint.fuzzy_hash},
                limit=10
            )

            if fuzzy_matches and fuzzy_matches.get('ids'):
                for doc_id, meta in zip(fuzzy_matches['ids'], fuzzy_matches.get('metadatas', [])):
                    if doc_id not in [d[0] for d in duplicates]:
                        # Check word count similarity
                        word_diff = abs(fingerprint.word_count - meta.get('word_count', 0))
                        if word_diff < 100:  # Within 100 words
                            duplicates.append((doc_id, 0.9, "fuzzy_hash_match"))

            # Search by title similarity
            if fingerprint.title_normalized:
                all_docs = self.collection.get(include=["metadatas"], limit=100)
                for doc_id, meta in zip(all_docs.get('ids', []), all_docs.get('metadatas', [])):
                    if doc_id in [d[0] for d in duplicates]:
                        continue

                    other_title = re.sub(r'[^a-z0-9]', '', meta.get('title', '').lower())
                    if other_title and len(other_title) > 5:
                        similarity = Levenshtein.ratio(fingerprint.title_normalized, other_title)
                        if similarity >= threshold:
                            duplicates.append((doc_id, similarity, "title_similarity"))

        except Exception as e:
            logger.error(f"Duplicate search error: {e}")

        return duplicates[:5]  # Top 5 matches

    def resolve_entity_aliases(self, entities: Dict) -> Dict:
        """Resolve entity names to canonical forms using personal KB"""

        resolved = {}

        # Resolve people
        people = entities.get("people", [])
        resolved_people = []

        for person in people:
            person_name = person.get("name") if isinstance(person, dict) else str(person)

            # Check against known aliases
            canonical = person_name
            for known_person, person_data in self.personal_kb.get("people", {}).items():
                if person_name in person_data.get("aliases", []) or person_name == known_person:
                    canonical = known_person
                    break

            resolved_people.append({
                "name": canonical,
                "original": person_name,
                "resolved": canonical != person_name,
                "kb_entry": canonical in self.personal_kb.get("people", {})
            })

        resolved["people"] = resolved_people

        # Similarly resolve organizations, locations
        resolved["organizations"] = entities.get("organizations", [])
        resolved["locations"] = entities.get("locations", [])

        return resolved

    def triage_document(
        self,
        content: str,
        metadata: Dict,
        entities: Dict,
        fingerprint: DocumentFingerprint
    ) -> TriageDecision:
        """Main triage logic - decide what to do with this document"""

        reasoning = []
        actions = []
        category = "unknown"
        confidence = 0.5
        related_docs = []
        kb_updates = []

        # === STEP 1: Check for duplicates ===
        duplicates = self.find_duplicates(fingerprint)
        if duplicates:
            most_similar = duplicates[0]
            if most_similar[1] >= 0.95:
                category = "duplicate"
                confidence = most_similar[1]
                reasoning.append(f"Exact/near-duplicate of {most_similar[0][:30]}... ({most_similar[2]})")
                actions.append(f"Skip processing - duplicate of existing document {most_similar[0][:30]}")
                related_docs.append(most_similar[0])
                return TriageDecision(category, confidence, reasoning, actions, related_docs, kb_updates)

        # === STEP 2: Detect junk/spam ===
        junk_keywords = ["advertisement", "promotion", "unsubscribe", "click here", "special offer"]
        junk_count = sum(1 for keyword in junk_keywords if keyword in content.lower())
        if junk_count >= 2:
            category = "junk"
            confidence = min(0.9, 0.5 + (junk_count * 0.1))
            reasoning.append(f"Contains {junk_count} spam/junk indicators")
            actions.append("Mark for deletion or quarantine")
            return TriageDecision(category, confidence, reasoning, actions, related_docs, kb_updates)

        # === STEP 3: Detect personal/actionable documents ===

        # Check for wedding/marriage invitations
        if any(word in content.lower() for word in ["hochzeit", "wedding", "heiraten", "marry", "married"]):
            # Extract date if possible
            date_patterns = [
                r'\d{1,2}\.\d{1,2}\.\d{4}',  # DD.MM.YYYY
                r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            ]
            dates_found = []
            for pattern in date_patterns:
                dates_found.extend(re.findall(pattern, content))

            if dates_found:
                reasoning.append("Wedding/marriage document detected with date")
                actions.append(f"Potential wedding date: {dates_found[0]}")

                # Check if any known people are mentioned
                for person_name in self.personal_kb.get("people", {}).keys():
                    if person_name.lower() in content.lower():
                        kb_updates.append({
                            "type": "marriage_event",
                            "person": person_name,
                            "date": dates_found[0],
                            "action": "Consider updating addressbook with marriage info"
                        })
                        actions.append(f"⚠️ Update addressbook: {person_name} may have married on {dates_found[0]}")

                category = "personal_actionable"
                confidence = 0.85
                return TriageDecision(category, confidence, reasoning, actions, related_docs, kb_updates)

        # Check for invoices/bills
        if any(word in content.lower() for word in ["invoice", "rechnung", "payment", "betrag", "total"]):
            reasoning.append("Invoice/bill detected")
            actions.append("Extract amount and due date")
            category = "financial_actionable"
            confidence = 0.8

            # Try to extract amount
            amount_patterns = [r'\€\s*\d+[,\.]\d{2}', r'\d+[,\.]\d{2}\s*\€']
            amounts = []
            for pattern in amount_patterns:
                amounts.extend(re.findall(pattern, content))
            if amounts:
                actions.append(f"Amount found: {amounts[0]}")

            return TriageDecision(category, confidence, reasoning, actions, related_docs, kb_updates)

        # Check for upcoming events/dates
        events_found = self._extract_upcoming_events(content, metadata)
        if events_found:
            reasoning.append(f"Found {len(events_found)} upcoming events/dates")
            for event in events_found:
                actions.append(f"📅 {event['date']}: {event['description']}")
            category = "reference_with_dates"
            confidence = 0.75
            return TriageDecision(category, confidence, reasoning, actions, related_docs, kb_updates)

        # === STEP 4: Categorize based on domain ===
        domain = metadata.get("domain", "general")
        complexity = metadata.get("complexity", "intermediate")
        significance = metadata.get("significance_score", 0.5)

        if domain == "legal":
            category = "legal_reference"
            confidence = 0.7
            reasoning.append("Legal document - likely important")
            actions.append("Archive for future reference")

        elif domain == "health" or domain == "psychology":
            category = "personal_health"
            confidence = 0.75
            reasoning.append("Health/medical information")
            actions.append("Archive in health records")

        elif domain == "technology":
            if complexity == "advanced" and significance > 0.7:
                category = "technical_reference_high_value"
                confidence = 0.8
                reasoning.append("High-value technical documentation")
                actions.append("Add to technical knowledge base")
            else:
                category = "technical_reference"
                confidence = 0.6

        else:
            # Default: archival
            category = "archival"
            confidence = 0.5
            reasoning.append("General document - archival")
            actions.append("Standard processing and archival")

        return TriageDecision(category, confidence, reasoning, actions, related_docs, kb_updates)

    def _extract_upcoming_events(self, content: str, metadata: Dict) -> List[Dict]:
        """Extract upcoming events and dates"""
        events = []

        # Date patterns
        date_patterns = [
            (r'(\d{1,2}\.\d{1,2}\.\d{4})', '%d.%m.%Y'),  # DD.MM.YYYY
            (r'(\d{4}-\d{2}-\d{2})', '%Y-%m-%d'),  # YYYY-MM-DD
        ]

        for pattern, date_format in date_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                date_str = match.group(1)
                try:
                    event_date = datetime.strptime(date_str, date_format)

                    # Only include future dates or recent past (last 30 days)
                    if event_date >= datetime.now() - timedelta(days=30):
                        # Try to extract context (50 chars before and after)
                        context_start = max(0, match.start() - 50)
                        context_end = min(len(content), match.end() + 50)
                        context = content[context_start:context_end].strip()

                        events.append({
                            "date": date_str,
                            "parsed_date": event_date.isoformat(),
                            "description": context[:100],
                            "is_future": event_date > datetime.now()
                        })

                except ValueError:
                    continue

        return events[:5]  # Top 5 events

    def generate_triage_summary(self, decision: TriageDecision) -> str:
        """Generate human-readable triage summary"""

        summary = f"""
📋 **TRIAGE DECISION: {decision.category.upper().replace('_', ' ')}**
   Confidence: {decision.confidence:.0%}

**Reasoning**:
{chr(10).join(f'  - {r}' for r in decision.reasoning)}

**Suggested Actions**:
{chr(10).join(f'  ✓ {a}' for a in decision.actions_suggested)}
"""

        if decision.knowledge_updates:
            summary += "\n**Knowledge Base Updates**:\n"
            for update in decision.knowledge_updates:
                summary += f"  🔄 {update.get('action', 'Update needed')}\n"

        if decision.related_documents:
            summary += f"\n**Related Documents**: {len(decision.related_documents)} found\n"

        return summary
