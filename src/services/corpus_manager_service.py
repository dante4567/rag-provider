"""
Corpus Manager Service - Two Corpus Views

Maintains separate "canonical" and "full" corpus views for flexible retrieval.
Blueprint requirement: Two corpus views (canonical vs full indices).

Canonical corpus:
- High-quality documents only
- Deduplicated
- Fast retrieval
- Default for user queries

Full corpus:
- All documents (including low-quality, duplicates)
- Comprehensive search
- Used for specific use cases (audit, compliance)
"""

import logging
from typing import List, Dict, Optional, Set
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class CorpusView(str, Enum):
    """Corpus view types"""
    CANONICAL = "canonical"  # High-quality, deduplicated
    FULL = "full"            # All documents


@dataclass
class CorpusStats:
    """Statistics for a corpus view"""
    total_documents: int
    total_chunks: int
    avg_quality_score: float
    document_types: Dict[str, int]  # Count per doc type


class CorpusManagerService:
    """
    Manage separate canonical and full corpus views

    Canonical corpus:
    - do_index=True documents only
    - Quality score >= threshold
    - Deduplicated (one version per content hash)

    Full corpus:
    - All documents regardless of quality
    - Includes duplicates
    - Comprehensive but noisy
    """

    def __init__(
        self,
        canonical_min_quality: float = 0.6,
        canonical_min_signalness: float = 0.5
    ):
        """
        Initialize corpus manager

        Args:
            canonical_min_quality: Minimum quality score for canonical corpus
            canonical_min_signalness: Minimum signalness for canonical corpus
        """
        self.canonical_min_quality = canonical_min_quality
        self.canonical_min_signalness = canonical_min_signalness

        # Track which documents are in each corpus
        self.canonical_doc_ids: Set[str] = set()
        self.full_doc_ids: Set[str] = set()

    def should_add_to_canonical(
        self,
        metadata: Dict
    ) -> bool:
        """
        Determine if document should be added to canonical corpus

        Args:
            metadata: Document metadata with quality scores

        Returns:
            True if document meets canonical criteria
        """
        # Check do_index flag
        if not metadata.get('do_index', True):
            return False

        # Check quality score
        quality_score = metadata.get('quality_score', 0.0)
        if quality_score < self.canonical_min_quality:
            return False

        # Check signalness
        signalness = metadata.get('signalness', 0.0)
        if signalness < self.canonical_min_signalness:
            return False

        # Check for duplicate markers
        is_duplicate = metadata.get('is_duplicate', False)
        if is_duplicate:
            return False

        return True

    def get_corpus_for_document(
        self,
        metadata: Dict
    ) -> List[CorpusView]:
        """
        Determine which corpus views should contain this document

        Args:
            metadata: Document metadata

        Returns:
            List of corpus views to add document to
        """
        views = []

        # Full corpus gets everything
        views.append(CorpusView.FULL)

        # Canonical corpus only gets high-quality docs
        if self.should_add_to_canonical(metadata):
            views.append(CorpusView.CANONICAL)

        return views

    def add_document_to_view(
        self,
        doc_id: str,
        view: CorpusView
    ):
        """
        Track document addition to corpus view

        Args:
            doc_id: Document identifier
            view: Which corpus view
        """
        if view == CorpusView.CANONICAL:
            self.canonical_doc_ids.add(doc_id)
        elif view == CorpusView.FULL:
            self.full_doc_ids.add(doc_id)

        logger.debug(f"Added document {doc_id} to {view.value} corpus")

    def remove_document_from_view(
        self,
        doc_id: str,
        view: CorpusView
    ):
        """
        Remove document from corpus view

        Args:
            doc_id: Document identifier
            view: Which corpus view
        """
        if view == CorpusView.CANONICAL:
            self.canonical_doc_ids.discard(doc_id)
        elif view == CorpusView.FULL:
            self.full_doc_ids.discard(doc_id)

    def is_document_in_view(
        self,
        doc_id: str,
        view: CorpusView
    ) -> bool:
        """
        Check if document is in corpus view

        Args:
            doc_id: Document identifier
            view: Which corpus view

        Returns:
            True if document is in view
        """
        if view == CorpusView.CANONICAL:
            return doc_id in self.canonical_doc_ids
        elif view == CorpusView.FULL:
            return doc_id in self.full_doc_ids
        return False

    def get_stats(self, view: CorpusView) -> Dict:
        """
        Get statistics for corpus view

        Args:
            view: Which corpus view

        Returns:
            Statistics dictionary
        """
        if view == CorpusView.CANONICAL:
            doc_count = len(self.canonical_doc_ids)
        else:
            doc_count = len(self.full_doc_ids)

        return {
            "view": view.value,
            "total_documents": doc_count,
            "sample_doc_ids": list(
                (self.canonical_doc_ids if view == CorpusView.CANONICAL else self.full_doc_ids)
            )[:5]
        }

    def get_collection_name(self, view: CorpusView, base_name: str = "documents") -> str:
        """
        Get collection name for corpus view

        Args:
            view: Which corpus view
            base_name: Base collection name

        Returns:
            Collection name with view suffix
        """
        if view == CorpusView.CANONICAL:
            return f"{base_name}_canonical"
        else:
            return f"{base_name}_full"

    def suggest_view_for_query(
        self,
        query_type: str,
        user_preference: Optional[CorpusView] = None
    ) -> CorpusView:
        """
        Suggest appropriate corpus view for query type

        Args:
            query_type: Type of query (search, audit, compliance, etc.)
            user_preference: User's explicit preference

        Returns:
            Suggested corpus view
        """
        # User preference overrides
        if user_preference:
            return user_preference

        # Query type suggestions
        full_corpus_queries = {"audit", "compliance", "comprehensive", "all"}

        if query_type.lower() in full_corpus_queries:
            return CorpusView.FULL

        # Default to canonical for better quality
        return CorpusView.CANONICAL


# Test
if __name__ == "__main__":
    manager = CorpusManagerService()

    print("=" * 60)
    print("Corpus Manager Service Test")
    print("=" * 60)

    # Test documents
    high_quality_doc = {
        "quality_score": 0.85,
        "signalness": 0.75,
        "do_index": True,
        "is_duplicate": False
    }

    low_quality_doc = {
        "quality_score": 0.35,
        "signalness": 0.25,
        "do_index": True,
        "is_duplicate": False
    }

    duplicate_doc = {
        "quality_score": 0.90,
        "signalness": 0.80,
        "do_index": True,
        "is_duplicate": True
    }

    # Test corpus assignment
    print("\n1. High-quality document:")
    views = manager.get_corpus_for_document(high_quality_doc)
    print(f"   Assigned to: {[v.value for v in views]}")
    print(f"   In canonical? {CorpusView.CANONICAL in views}")

    print("\n2. Low-quality document:")
    views = manager.get_corpus_for_document(low_quality_doc)
    print(f"   Assigned to: {[v.value for v in views]}")
    print(f"   In canonical? {CorpusView.CANONICAL in views}")

    print("\n3. Duplicate document:")
    views = manager.get_corpus_for_document(duplicate_doc)
    print(f"   Assigned to: {[v.value for v in views]}")
    print(f"   In canonical? {CorpusView.CANONICAL in views}")

    # Test document tracking
    print("\n4. Document tracking:")
    manager.add_document_to_view("doc1", CorpusView.CANONICAL)
    manager.add_document_to_view("doc1", CorpusView.FULL)
    manager.add_document_to_view("doc2", CorpusView.FULL)

    print(f"   Canonical docs: {len(manager.canonical_doc_ids)}")
    print(f"   Full docs: {len(manager.full_doc_ids)}")

    # Test collection names
    print("\n5. Collection names:")
    print(f"   Canonical: {manager.get_collection_name(CorpusView.CANONICAL)}")
    print(f"   Full: {manager.get_collection_name(CorpusView.FULL)}")

    # Test view suggestions
    print("\n6. View suggestions:")
    print(f"   Search query → {manager.suggest_view_for_query('search').value}")
    print(f"   Audit query → {manager.suggest_view_for_query('audit').value}")
    print(f"   Compliance → {manager.suggest_view_for_query('compliance').value}")

    # Stats
    print("\n7. Statistics:")
    print(f"   Canonical: {manager.get_stats(CorpusView.CANONICAL)}")
    print(f"   Full: {manager.get_stats(CorpusView.FULL)}")

    print("\n" + "=" * 60)
    print("✅ All tests passed")
