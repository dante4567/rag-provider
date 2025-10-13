"""
Tag Taxonomy Service - Evolving Hierarchical Tags

Manages an evolving tag hierarchy that:
- Learns from existing tags in the system
- Avoids overly generic tags
- Suggests specific, contextual tags
- Maintains consistency across documents
- Supports SmartNotes/Zettelkasten workflow patterns
"""

import logging
import re
from typing import List, Dict, Set, Tuple, Optional
from collections import Counter, defaultdict
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class TagTaxonomyService:
    """Manages evolving tag taxonomy with awareness of existing tags"""

    def __init__(self, collection=None):
        self.collection = collection
        self.tag_cache = {}  # Cache of existing tags
        self.last_refresh = None

        # Base taxonomy (SmartNotes methodology - always available)
        self.base_taxonomy = {
            # Workflow stages
            "workflow": {
                "input": ["cont/in/read", "cont/in/extract", "cont/in/add"],
                "process": ["cont/zk/connect", "cont/zk/proceed", "cont/zk/sort", "cont/zk/differentiate"],
                "output": ["output/idea", "output/develop", "output/outline"]
            },
            # Content types
            "type": {
                "note_types": ["literature", "permanent", "fleeting", "reference"],
                "navigation": ["hub", "hub/moc", "index", "map"]
            },
            # Project management
            "project": {
                "status": ["project/active", "project/idle", "project/finished", "project/archived"]
            }
        }

    async def refresh_tag_cache(self, force: bool = False):
        """Refresh cache of existing tags from ChromaDB"""
        if not self.collection:
            return

        # Refresh every 5 minutes or when forced
        if not force and self.last_refresh:
            elapsed = (datetime.now() - self.last_refresh).seconds
            if elapsed < 300:
                return

        try:
            # Get all documents with tags
            all_docs = self.collection.get(include=["metadatas"])

            tag_frequency = Counter()
            tag_co_occurrence = defaultdict(Counter)
            domain_tags = defaultdict(set)

            for metadata in all_docs.get("metadatas", []):
                if not metadata:
                    continue

                # Parse tags from comma-separated string
                tags_str = metadata.get("tags", "")
                doc_tags = [t.strip() for t in tags_str.split(",") if t.strip()]

                domain = metadata.get("domain", "general")

                # Track frequency
                for tag in doc_tags:
                    tag_frequency[tag] += 1
                    domain_tags[domain].add(tag)

                # Track co-occurrence (which tags appear together)
                for i, tag1 in enumerate(doc_tags):
                    for tag2 in doc_tags[i+1:]:
                        tag_co_occurrence[tag1][tag2] += 1
                        tag_co_occurrence[tag2][tag1] += 1

            self.tag_cache = {
                "frequency": dict(tag_frequency),
                "co_occurrence": dict(tag_co_occurrence),
                "by_domain": dict(domain_tags),
                "total_docs": len(all_docs.get("ids", [])),
                "unique_tags": len(tag_frequency)
            }

            self.last_refresh = datetime.now()

            logger.info(f"Refreshed tag cache: {self.tag_cache['unique_tags']} unique tags across {self.tag_cache['total_docs']} documents")

        except Exception as e:
            logger.error(f"Failed to refresh tag cache: {e}")

    def get_existing_tags_for_context(self, domain: str = None, limit: int = 50) -> List[str]:
        """Get existing tags to provide as context to LLM"""
        if not self.tag_cache or not self.tag_cache.get("frequency"):
            return []

        # If domain specified, prioritize domain-specific tags
        if domain and domain in self.tag_cache.get("by_domain", {}):
            domain_tags = list(self.tag_cache["by_domain"][domain])
            # Sort by frequency
            domain_tags.sort(key=lambda t: self.tag_cache["frequency"].get(t, 0), reverse=True)
            return domain_tags[:limit]

        # Otherwise return most frequent tags
        sorted_tags = sorted(
            self.tag_cache["frequency"].items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [tag for tag, freq in sorted_tags[:limit]]

    def get_tag_statistics(self) -> Dict:
        """Get statistics about tag usage"""
        if not self.tag_cache:
            return {}

        freq = self.tag_cache.get("frequency", {})
        if not freq:
            return {}

        frequencies = list(freq.values())

        return {
            "total_unique_tags": len(freq),
            "total_documents": self.tag_cache.get("total_docs", 0),
            "avg_frequency": sum(frequencies) / len(frequencies) if frequencies else 0,
            "most_used": sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10],
            "domains": list(self.tag_cache.get("by_domain", {}).keys())
        }

    def suggest_similar_tags(self, proposed_tag: str, threshold: float = 0.7) -> List[Tuple[str, float]]:
        """Find similar existing tags to avoid duplicates"""
        if not self.tag_cache or not self.tag_cache.get("frequency"):
            return []

        existing_tags = list(self.tag_cache["frequency"].keys())
        similar = []

        proposed_lower = proposed_tag.lower().replace("-", " ").replace("_", " ")
        proposed_parts = set(proposed_lower.split("/"))

        for existing_tag in existing_tags:
            existing_lower = existing_tag.lower().replace("-", " ").replace("_", " ")
            existing_parts = set(existing_lower.split("/"))

            # Exact match
            if proposed_lower == existing_lower:
                similar.append((existing_tag, 1.0))
                continue

            # Check if one is substring of other
            if proposed_lower in existing_lower or existing_lower in proposed_lower:
                similar.append((existing_tag, 0.9))
                continue

            # Check hierarchical similarity (shared path components)
            common_parts = proposed_parts & existing_parts
            if common_parts:
                similarity = len(common_parts) / max(len(proposed_parts), len(existing_parts))
                if similarity >= threshold:
                    similar.append((existing_tag, similarity))

        # Sort by similarity
        similar.sort(key=lambda x: x[1], reverse=True)
        return similar[:5]

    def validate_and_deduplicate_tags(self, proposed_tags: List[str], domain: str = None) -> List[str]:
        """Validate tags and merge with existing similar ones"""
        validated = []

        for tag in proposed_tags:
            # Skip empty or too generic
            if not tag or len(tag) < 2:
                continue

            # Normalize
            tag = tag.strip().lower()
            if tag.startswith("#"):
                tag = tag[1:]

            # Check for similar existing tags
            similar = self.suggest_similar_tags(tag, threshold=0.85)

            if similar and similar[0][1] >= 0.95:
                # Use existing tag instead (near-duplicate)
                existing_tag = similar[0][0]
                if existing_tag not in validated:
                    validated.append(existing_tag)
                    logger.debug(f"Merged tag '{tag}' → '{existing_tag}' (similarity: {similar[0][1]:.2f})")
            else:
                # Use proposed tag (sufficiently unique)
                if tag not in validated:
                    validated.append(tag)

        return validated

    def enrich_tags_with_hierarchy(self, tags: List[str], domain: str = None) -> List[str]:
        """Add hierarchical structure to flat tags"""
        enriched = set(tags)  # Start with original tags

        # Add base taxonomy tags based on context
        for tag in tags:
            tag_lower = tag.lower()

            # If it's a content type without hierarchy, add it
            if tag_lower in ["literature", "permanent", "fleeting", "reference"]:
                if tag not in enriched:
                    enriched.add(tag)

            # Add workflow stage if detected
            if "read" in tag_lower and "cont/in/read" not in enriched:
                enriched.add("cont/in/read")

        return list(enriched)

    def get_tag_suggestions_for_llm(self, domain: str = None, content_preview: str = None) -> str:
        """Generate tag suggestions text for LLM prompt"""
        existing_tags = self.get_existing_tags_for_context(domain=domain, limit=30)

        # Base taxonomy
        base_examples = [
            "cont/in/read", "cont/in/extract", "literature", "permanent",
            "hub", "project/active", "cont/zk/connect"
        ]

        if existing_tags:
            # Combine base + existing (most frequent)
            suggestion_text = f"""
**Existing tags in the system** (use these when relevant to maintain consistency):
{', '.join(existing_tags[:20])}

**Base workflow tags** (always available):
- Input: cont/in/read, cont/in/extract, cont/in/add
- Process: cont/zk/connect, cont/zk/proceed
- Output: output/idea, output/develop
- Types: literature, permanent, fleeting, hub, hub/moc
- Projects: project/active, project/idle, project/finished

**Tag Guidelines**:
1. Create APPROPRIATE tags that accurately describe this specific document
2. Use existing tags ONLY if they truly fit the content (check list above)
3. Don't force-fit existing tags - create new ones when needed
4. Use hierarchical structure: category/subcategory (e.g., "psychology/cognitive", "tech/ai/ml")
5. Avoid overly generic single-word tags (e.g., prefer "health/mental" over just "health")
6. Domain-specific tags are encouraged (e.g., "legal/custody", "school/administration")
"""
        else:
            suggestion_text = f"""
**Base workflow tags**:
- Input: cont/in/read, cont/in/extract, cont/in/add
- Process: cont/zk/connect, cont/zk/proceed
- Output: output/idea, output/develop
- Types: literature, permanent, fleeting, hub, hub/moc
- Projects: project/active, project/idle

**Tag Guidelines**:
1. Use hierarchical structure: category/subcategory
2. Create specific, descriptive tags (avoid generic single words)
3. Domain-specific tags encouraged (e.g., "psychology/adhd", "tech/automation")
"""

        return suggestion_text
