"""
Fast Annotation Service using Flashtext

Uses Aho-Corasick algorithm for 1000x faster dictionary matching compared to regex.
Pre-indexes vocabulary for instant concept detection.

Workflow:
1. Fast dictionary match (flashtext) → candidate concepts
2. Context extraction (±2 sentences)
3. Confidence scoring
4. Return annotations with offsets and confidence

This augments (not replaces) LLM enrichment:
- Fast matching finds known terms
- LLM validates and finds novel concepts
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from flashtext import KeywordProcessor

logger = logging.getLogger(__name__)


@dataclass
class Annotation:
    """A concept annotation with metadata"""
    concept_id: str
    label_used: str  # Which altLabel matched
    offsets: Tuple[int, int]  # Character positions (start, end)
    confidence: float  # 0.0-1.0
    context: str  # ±2 sentences around match


class FastAnnotationService:
    """
    Fast dictionary-based annotation using Aho-Corasick algorithm.

    Performance: ~1000x faster than regex for large vocabularies
    - Regex: O(n * m) where m = number of patterns
    - Aho-Corasick: O(n + k) where k = number of matches

    Usage:
        annotator = FastAnnotationService()
        annotator.load_vocabulary(topics, places, people)

        annotations = annotator.annotate(text)
        for ann in annotations:
            print(f"{ann.concept_id}: '{ann.label_used}' at {ann.offsets} (conf={ann.confidence})")
    """

    def __init__(self, case_sensitive: bool = False):
        """
        Initialize fast annotator.

        Args:
            case_sensitive: Whether matching should be case-sensitive
        """
        self.processor = KeywordProcessor(case_sensitive=case_sensitive)
        self.concept_metadata = {}  # concept_id -> {prefLabel, altLabel, scopeNote, etc}
        self.loaded = False

        logger.info(f"FastAnnotationService initialized (case_sensitive={case_sensitive})")

    def load_vocabulary(
        self,
        topics: Optional[List[str]] = None,
        places: Optional[List[str]] = None,
        people: Optional[List[str]] = None,
        custom_concepts: Optional[List[Dict]] = None
    ):
        """
        Load vocabulary for fast matching.

        Args:
            topics: List of topic strings (e.g., ["technology/ai", "legal/court"])
            places: List of place strings
            people: List of people strings
            custom_concepts: List of concept dicts with id, prefLabel, altLabel
        """
        # Clear existing keywords
        self.processor = KeywordProcessor(case_sensitive=False)
        self.concept_metadata = {}

        # Load simple string vocabularies (current YAML format)
        if topics:
            for topic in topics:
                concept_id = self._generate_id(topic)
                self.processor.add_keyword(topic, concept_id)
                self.concept_metadata[concept_id] = {
                    "prefLabel": topic,
                    "altLabel": [],
                    "type": "topic"
                }

        if places:
            for place in places:
                concept_id = self._generate_id(place)
                self.processor.add_keyword(place, concept_id)
                self.concept_metadata[concept_id] = {
                    "prefLabel": place,
                    "altLabel": [],
                    "type": "place"
                }

        if people:
            for person in people:
                concept_id = self._generate_id(person)
                self.processor.add_keyword(person, concept_id)
                self.concept_metadata[concept_id] = {
                    "prefLabel": person,
                    "altLabel": [],
                    "type": "person"
                }

        # Load enhanced concepts (SKOS format with altLabel)
        if custom_concepts:
            for concept in custom_concepts:
                concept_id = concept.get("id", self._generate_id(concept["prefLabel"]))

                # Add prefLabel
                pref_label = concept["prefLabel"]
                self.processor.add_keyword(pref_label, concept_id)

                # Add all altLabels
                alt_labels = concept.get("altLabel", [])
                for alt in alt_labels:
                    self.processor.add_keyword(alt, concept_id)

                # Store metadata
                self.concept_metadata[concept_id] = {
                    "prefLabel": pref_label,
                    "altLabel": alt_labels,
                    "scopeNote": concept.get("scopeNote", ""),
                    "broader": concept.get("broader", []),
                    "narrower": concept.get("narrower", []),
                    "type": concept.get("type", "custom")
                }

        self.loaded = True
        logger.info(f"✅ Loaded {len(self.concept_metadata)} concepts for fast matching")

    def _generate_id(self, label: str) -> str:
        """Generate concept ID from label"""
        import hashlib
        # Use first 8 chars of hash as ID
        return f"c_{hashlib.md5(label.encode()).hexdigest()[:8]}"

    def annotate(self, text: str, context_window: int = 2) -> List[Annotation]:
        """
        Annotate text with concept matches.

        Args:
            text: Text to annotate
            context_window: Number of sentences before/after match for context

        Returns:
            List of Annotation objects
        """
        if not self.loaded:
            logger.warning("Vocabulary not loaded, returning empty annotations")
            return []

        # Extract keywords with positions
        keywords_found = self.processor.extract_keywords(text, span_info=True)

        annotations = []
        for keyword, start, end in keywords_found:
            # keyword is the concept_id returned by processor
            concept_id = keyword

            # Find which label was actually used (reconstruct from text)
            label_used = text[start:end]

            # Extract context (±N sentences)
            context = self._extract_context(text, start, end, context_window)

            # Calculate confidence
            confidence = self._calculate_confidence(
                concept_id=concept_id,
                label_used=label_used,
                context=context
            )

            annotations.append(Annotation(
                concept_id=concept_id,
                label_used=label_used,
                offsets=(start, end),
                confidence=confidence,
                context=context
            ))

        logger.info(f"📍 Fast annotation found {len(annotations)} concept matches")
        return annotations

    def _extract_context(self, text: str, start: int, end: int, window: int) -> str:
        """Extract ±N sentences around match"""
        # Simple sentence splitting (could be improved with spaCy)
        sentences = text.split('. ')

        # Find which sentence contains the match
        current_pos = 0
        match_sentence_idx = 0

        for idx, sentence in enumerate(sentences):
            sentence_end = current_pos + len(sentence) + 2  # +2 for '. '
            if current_pos <= start < sentence_end:
                match_sentence_idx = idx
                break
            current_pos = sentence_end

        # Get ±window sentences
        start_idx = max(0, match_sentence_idx - window)
        end_idx = min(len(sentences), match_sentence_idx + window + 1)

        context_sentences = sentences[start_idx:end_idx]
        return '. '.join(context_sentences)

    def _calculate_confidence(self, concept_id: str, label_used: str, context: str) -> float:
        """
        Calculate confidence score for annotation.

        Factors:
        - Exact match (prefLabel) = higher confidence
        - Alt label match = slightly lower
        - Context relevance = boost
        - Common stopwords = lower confidence

        Returns:
            Confidence 0.0-1.0
        """
        if concept_id not in self.concept_metadata:
            return 0.5  # Default

        metadata = self.concept_metadata[concept_id]
        confidence = 0.7  # Base confidence

        # Boost for prefLabel match
        if label_used.lower() == metadata["prefLabel"].lower():
            confidence += 0.2

        # Boost for longer matches (more specific)
        word_count = len(label_used.split())
        if word_count >= 3:
            confidence += 0.1
        elif word_count == 1:
            confidence -= 0.1  # Single words are ambiguous

        # Penalize if it's a common word (stopword check)
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        if label_used.lower() in stopwords:
            confidence = 0.1  # Very low confidence

        # Cap at 0.95 (never 100% certain without disambiguation)
        confidence = min(0.95, max(0.1, confidence))

        return confidence

    def get_statistics(self) -> Dict:
        """Get statistics about loaded vocabulary"""
        if not self.loaded:
            return {"loaded": False}

        total_keywords = len(self.processor)
        concept_types = {}

        for concept_id, metadata in self.concept_metadata.items():
            concept_type = metadata.get("type", "unknown")
            concept_types[concept_type] = concept_types.get(concept_type, 0) + 1

        return {
            "loaded": True,
            "total_concepts": len(self.concept_metadata),
            "total_keywords": total_keywords,  # Includes altLabels
            "concepts_by_type": concept_types,
            "avg_labels_per_concept": total_keywords / len(self.concept_metadata) if self.concept_metadata else 0
        }


# Singleton instance
_fast_annotation_service = None


def get_fast_annotation_service() -> FastAnnotationService:
    """Get or create fast annotation service singleton"""
    global _fast_annotation_service

    if _fast_annotation_service is None:
        _fast_annotation_service = FastAnnotationService(case_sensitive=False)

    return _fast_annotation_service
