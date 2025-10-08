"""
Entity Deduplication Service - Cross-reference entity mentions

Recognizes that different mentions refer to the same entity:
- "Dr. Weber" = "Thomas Weber" = "Prof. Dr. Weber"
- "Schmidt" = "Rechtsanwalt Schmidt" = "RA Schmidt"
- "Meyer & Partner" = "Meyer und Partner GmbH"

Uses fuzzy matching, title normalization, and cross-document entity resolution.
"""

from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """Represents a deduplicated entity across multiple mentions"""
    canonical_name: str  # Primary name to use
    aliases: Set[str] = field(default_factory=set)  # All variations seen
    entity_type: str = "person"  # person, organization, place
    roles: Set[str] = field(default_factory=set)  # Extracted roles
    titles: Set[str] = field(default_factory=set)  # Academic/professional titles
    mentions_count: int = 0  # How many times mentioned
    source_docs: Set[str] = field(default_factory=set)  # Which documents
    confidence: float = 1.0  # Deduplication confidence (0-1)


class EntityDeduplicationService:
    """Deduplicate and cross-reference entity mentions"""

    # Titles to normalize/remove for matching
    TITLES = {
        # German academic
        'dr.', 'dr', 'prof.', 'prof', 'dipl.-ing.', 'dipl.ing', 'ing.',
        'mag.', 'msc.', 'ba.', 'ma.', 'phd',
        # German professional
        'rechtsanwalt', 'rechtsanwältin', 'ra', 'ra.',
        'richterin', 'richter',
        'verfahrensbeistand', 'verfahrensbevollmächtigter',
        'staatsanwalt', 'staatsanwältin',
        # English
        'mr.', 'mr', 'mrs.', 'mrs', 'ms.', 'ms', 'miss',
        'dr.', 'dr', 'prof.', 'prof', 'attorney', 'atty',
        # Suffixes
        'jr.', 'jr', 'sr.', 'sr', 'ii', 'iii', 'iv'
    }

    # Common organization legal forms to normalize
    ORG_SUFFIXES = {
        'gmbh', 'ag', 'kg', 'ohg', 'gbr', 'ug',
        'inc', 'inc.', 'llc', 'ltd', 'ltd.', 'corp', 'corp.',
        '&', 'und', 'and', 'partner', 'partners'
    }

    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize entity deduplication service

        Args:
            similarity_threshold: Minimum similarity score (0-1) to consider entities same
        """
        self.similarity_threshold = similarity_threshold
        self.entities: Dict[str, Entity] = {}  # canonical_name -> Entity
        self.alias_to_canonical: Dict[str, str] = {}  # alias -> canonical_name

    def normalize_name(
        self,
        name: str,
        entity_type: str = "person",
        extract_titles: bool = False
    ) -> Tuple[str, Set[str], Set[str]]:
        """
        Normalize entity name for matching

        Args:
            name: Original entity name
            entity_type: Type of entity (person, organization, place)
            extract_titles: If True, return extracted titles separately

        Returns:
            Tuple of (normalized_name, extracted_titles, extracted_roles)
        """
        if not name or not name.strip():
            return "", set(), set()

        original = name.strip()
        name_lower = original.lower()

        extracted_titles = set()
        extracted_roles = set()

        # Extract titles for people
        if entity_type == "person":
            for title in self.TITLES:
                # Match title as whole word
                pattern = r'\b' + re.escape(title) + r'\b'
                if re.search(pattern, name_lower):
                    extracted_titles.add(title)
                    # Remove from name
                    name_lower = re.sub(pattern, ' ', name_lower)

        # Extract organization suffixes
        elif entity_type == "organization":
            for suffix in self.ORG_SUFFIXES:
                pattern = r'\b' + re.escape(suffix) + r'\b'
                if re.search(pattern, name_lower):
                    # Keep suffixes in normalized form, but standardize
                    pass

        # Remove punctuation for comparison (but keep hyphens in names)
        normalized = re.sub(r'[,\.;:]', '', name_lower)

        # Clean up whitespace (AFTER removing titles/punctuation)
        normalized = ' '.join(normalized.split()).strip()

        return normalized, extracted_titles, extracted_roles

    def compute_similarity(self, name1: str, name2: str) -> float:
        """
        Compute similarity between two names

        Uses:
        - Exact match after normalization → 1.0
        - Substring match (one contains the other) → 0.9
        - Sequence similarity → 0.0-1.0

        Args:
            name1: First name (normalized)
            name2: Second name (normalized)

        Returns:
            Similarity score (0-1)
        """
        # Exact match
        if name1 == name2:
            return 1.0

        # One is substring of the other (e.g., "Weber" vs "Thomas Weber")
        if name1 in name2 or name2 in name1:
            # High score for substring match (word boundary check)
            # If one name is contained as a complete word in the other
            shorter = min(len(name1), len(name2))
            longer = max(len(name1), len(name2))

            # Boost score - substring match is strong evidence
            base_score = shorter / longer
            # Scale from 0.85-0.95 range (below exact match but high)
            return 0.85 + (base_score * 0.1)

        # Token overlap (for multi-word names)
        tokens1 = set(name1.split())
        tokens2 = set(name2.split())

        if tokens1 and tokens2:
            overlap = tokens1 & tokens2
            union = tokens1 | tokens2
            jaccard = len(overlap) / len(union)

            # If significant overlap, boost score
            if jaccard > 0.5:
                return 0.7 + (jaccard * 0.3)  # 0.7-1.0 range

        # Sequence similarity (Levenshtein-like)
        return SequenceMatcher(None, name1, name2).ratio()

    def add_entity(
        self,
        name: str,
        entity_type: str = "person",
        document_id: Optional[str] = None,
        force_new: bool = False
    ) -> Entity:
        """
        Add entity mention and deduplicate

        Args:
            name: Entity name as mentioned in document
            entity_type: Type of entity
            document_id: Source document ID
            force_new: Force creation of new entity (skip deduplication)

        Returns:
            Entity object (existing or newly created)
        """
        # Normalize name
        normalized, titles, roles = self.normalize_name(name, entity_type, extract_titles=True)

        if not normalized:
            logger.warning(f"Cannot add empty entity: '{name}'")
            return None

        # Check if already seen this exact alias
        if name in self.alias_to_canonical:
            canonical = self.alias_to_canonical[name]
            entity = self.entities[canonical]
            entity.mentions_count += 1
            if document_id:
                entity.source_docs.add(document_id)
            logger.debug(f"Found existing alias: '{name}' → '{canonical}'")
            return entity

        # Try to find matching entity (unless force_new)
        if not force_new:
            best_match, best_score = self._find_best_match(normalized, entity_type)

            if best_match and best_score >= self.similarity_threshold:
                # Merge with existing entity
                entity = self.entities[best_match]
                entity.aliases.add(name)
                entity.titles.update(titles)
                entity.roles.update(roles)
                entity.mentions_count += 1
                if document_id:
                    entity.source_docs.add(document_id)

                # Update alias mapping
                self.alias_to_canonical[name] = best_match

                logger.info(
                    f"Merged entity: '{name}' → '{best_match}' "
                    f"(similarity: {best_score:.2f})"
                )
                return entity

        # Create new entity
        entity = Entity(
            canonical_name=name,  # Use first seen name as canonical
            aliases={name},
            entity_type=entity_type,
            roles=roles,
            titles=titles,
            mentions_count=1,
            source_docs={document_id} if document_id else set(),
            confidence=1.0
        )

        self.entities[name] = entity
        self.alias_to_canonical[name] = name

        logger.info(f"Created new entity: '{name}' ({entity_type})")
        return entity

    def _find_best_match(
        self,
        normalized_name: str,
        entity_type: str
    ) -> Tuple[Optional[str], float]:
        """
        Find best matching existing entity

        Args:
            normalized_name: Normalized name to match
            entity_type: Entity type

        Returns:
            Tuple of (canonical_name, similarity_score) or (None, 0.0)
        """
        best_canonical = None
        best_score = 0.0

        # Only compare with entities of the same type
        for canonical, entity in self.entities.items():
            if entity.entity_type != entity_type:
                continue

            # Normalize canonical name
            canonical_norm, _, _ = self.normalize_name(canonical, entity_type)

            # Compute similarity
            score = self.compute_similarity(normalized_name, canonical_norm)

            if score > best_score:
                best_score = score
                best_canonical = canonical

        return best_canonical, best_score

    def get_entity(self, name: str) -> Optional[Entity]:
        """
        Get entity by any alias

        Args:
            name: Entity name or alias

        Returns:
            Entity object or None
        """
        canonical = self.alias_to_canonical.get(name)
        if canonical:
            return self.entities.get(canonical)
        return None

    def resolve_name(self, name: str) -> str:
        """
        Resolve name to canonical form

        Args:
            name: Entity name or alias

        Returns:
            Canonical name (or original if not found)
        """
        return self.alias_to_canonical.get(name, name)

    def get_all_entities(self, entity_type: Optional[str] = None) -> List[Entity]:
        """
        Get all entities, optionally filtered by type

        Args:
            entity_type: Filter by entity type (None = all)

        Returns:
            List of Entity objects
        """
        entities = list(self.entities.values())

        if entity_type:
            entities = [e for e in entities if e.entity_type == entity_type]

        # Sort by mentions count (most mentioned first)
        entities.sort(key=lambda e: e.mentions_count, reverse=True)

        return entities

    def merge_entities(
        self,
        name1: str,
        name2: str,
        preferred_canonical: Optional[str] = None
    ) -> Optional[Entity]:
        """
        Manually merge two entities

        Args:
            name1: First entity name
            name2: Second entity name
            preferred_canonical: Which name to use as canonical (default: name1)

        Returns:
            Merged entity or None if entities not found
        """
        entity1 = self.get_entity(name1)
        entity2 = self.get_entity(name2)

        if not entity1 or not entity2:
            logger.error(f"Cannot merge: entity not found ({name1}, {name2})")
            return None

        if entity1 == entity2:
            logger.warning(f"Entities already merged: {name1} = {name2}")
            return entity1

        # Determine canonical name
        canonical = preferred_canonical or entity1.canonical_name

        # Merge entity2 into entity1
        entity1.canonical_name = canonical
        entity1.aliases.update(entity2.aliases)
        entity1.titles.update(entity2.titles)
        entity1.roles.update(entity2.roles)
        entity1.mentions_count += entity2.mentions_count
        entity1.source_docs.update(entity2.source_docs)
        entity1.confidence = min(entity1.confidence, 0.95)  # Manual merge = slightly lower confidence

        # Update all aliases to point to canonical
        for alias in entity1.aliases:
            self.alias_to_canonical[alias] = canonical

        # Remove entity2
        old_canonical = entity2.canonical_name
        if old_canonical in self.entities:
            del self.entities[old_canonical]

        # Update entity1 in dict
        if canonical != entity1.canonical_name:
            # Canonical name changed
            old_key = next(k for k, v in self.entities.items() if v == entity1)
            del self.entities[old_key]
            self.entities[canonical] = entity1

        logger.info(f"Manually merged: '{name1}' + '{name2}' → '{canonical}'")
        return entity1

    def get_statistics(self) -> Dict:
        """
        Get deduplication statistics

        Returns:
            Dictionary with stats
        """
        total_entities = len(self.entities)
        total_aliases = len(self.alias_to_canonical)
        avg_aliases = total_aliases / total_entities if total_entities > 0 else 0

        by_type = defaultdict(int)
        for entity in self.entities.values():
            by_type[entity.entity_type] += 1

        return {
            'total_entities': total_entities,
            'total_aliases': total_aliases,
            'avg_aliases_per_entity': round(avg_aliases, 2),
            'entities_by_type': dict(by_type),
            'deduplication_rate': round((total_aliases - total_entities) / total_aliases * 100, 1) if total_aliases > 0 else 0
        }

    def export_entity_mappings(self) -> Dict[str, List[str]]:
        """
        Export entity mappings for review

        Returns:
            Dictionary mapping canonical names to lists of aliases
        """
        mappings = {}
        for canonical, entity in self.entities.items():
            if len(entity.aliases) > 1:
                mappings[canonical] = sorted(list(entity.aliases))

        return mappings


# Singleton instance
_entity_dedup_service: Optional[EntityDeduplicationService] = None


def get_entity_deduplication_service(
    similarity_threshold: float = 0.85
) -> EntityDeduplicationService:
    """
    Get singleton EntityDeduplicationService instance

    Args:
        similarity_threshold: Minimum similarity for entity matching

    Returns:
        EntityDeduplicationService instance
    """
    global _entity_dedup_service
    if _entity_dedup_service is None:
        _entity_dedup_service = EntityDeduplicationService(
            similarity_threshold=similarity_threshold
        )
        logger.info(
            f"Initialized EntityDeduplicationService "
            f"(threshold: {similarity_threshold})"
        )
    return _entity_dedup_service


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    service = EntityDeduplicationService(similarity_threshold=0.85)

    # Test cases: variations of the same person
    test_people = [
        ("Dr. Weber", "person", "doc1"),
        ("Thomas Weber", "person", "doc2"),
        ("Prof. Dr. Weber", "person", "doc3"),
        ("Weber", "person", "doc4"),
        ("Schmidt", "person", "doc5"),
        ("Rechtsanwalt Schmidt", "person", "doc6"),
        ("RA Schmidt", "person", "doc7"),
        ("Dr. Schmidt", "person", "doc8"),  # Different person?
        ("Meyer", "person", "doc9"),
        ("Dr. Meyer", "person", "doc10"),
    ]

    print("\n=== Entity Deduplication Test ===\n")

    for name, entity_type, doc_id in test_people:
        entity = service.add_entity(name, entity_type, doc_id)
        print(f"Added: '{name}' → Canonical: '{entity.canonical_name}'")

    print("\n=== Final Entity Mappings ===\n")
    mappings = service.export_entity_mappings()
    for canonical, aliases in mappings.items():
        print(f"'{canonical}': {aliases}")

    print("\n=== Statistics ===\n")
    stats = service.get_statistics()
    for key, value in stats.items():
        print(f"{key}: {value}")
