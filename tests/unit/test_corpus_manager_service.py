"""
Unit tests for CorpusManagerService

Tests two corpus views (canonical vs full)
"""
import pytest
from src.services.corpus_manager_service import (
    CorpusManagerService,
    CorpusView
)


class TestCorpusManagerService:
    """Test the CorpusManagerService class"""

    @pytest.fixture
    def service(self):
        """Create CorpusManagerService instance"""
        return CorpusManagerService(
            canonical_min_quality=0.6,
            canonical_min_signalness=0.5
        )

    def test_init_default(self):
        """Test initialization with default thresholds"""
        service = CorpusManagerService()
        assert service.canonical_min_quality == 0.6
        assert service.canonical_min_signalness == 0.5

    def test_high_quality_goes_to_both_corpora(self, service):
        """Test high-quality document goes to both canonical and full"""
        metadata = {
            "quality_score": 0.85,
            "signalness": 0.75,
            "do_index": True,
            "is_duplicate": False
        }

        views = service.get_corpus_for_document(metadata)

        assert CorpusView.CANONICAL in views
        assert CorpusView.FULL in views
        assert len(views) == 2

    def test_low_quality_only_full(self, service):
        """Test low-quality document only goes to full corpus"""
        metadata = {
            "quality_score": 0.3,
            "signalness": 0.2,
            "do_index": True,
            "is_duplicate": False
        }

        views = service.get_corpus_for_document(metadata)

        assert CorpusView.CANONICAL not in views
        assert CorpusView.FULL in views
        assert len(views) == 1

    def test_duplicate_only_full(self, service):
        """Test duplicate document only goes to full corpus"""
        metadata = {
            "quality_score": 0.95,
            "signalness": 0.85,
            "do_index": True,
            "is_duplicate": True  # Marked as duplicate
        }

        views = service.get_corpus_for_document(metadata)

        assert CorpusView.CANONICAL not in views
        assert CorpusView.FULL in views

    def test_do_index_false_only_full(self, service):
        """Test do_index=False goes only to full"""
        metadata = {
            "quality_score": 0.95,
            "signalness": 0.85,
            "do_index": False,  # Explicitly excluded
            "is_duplicate": False
        }

        views = service.get_corpus_for_document(metadata)

        assert CorpusView.CANONICAL not in views
        assert CorpusView.FULL in views

    def test_should_add_to_canonical_yes(self, service):
        """Test should_add_to_canonical returns True for good doc"""
        metadata = {
            "quality_score": 0.8,
            "signalness": 0.7,
            "do_index": True,
            "is_duplicate": False
        }

        result = service.should_add_to_canonical(metadata)
        assert result is True

    def test_should_add_to_canonical_no_quality(self, service):
        """Test should_add_to_canonical returns False for low quality"""
        metadata = {
            "quality_score": 0.3,  # Too low
            "signalness": 0.7,
            "do_index": True,
            "is_duplicate": False
        }

        result = service.should_add_to_canonical(metadata)
        assert result is False

    def test_add_document_tracking(self, service):
        """Test document tracking in corpus views"""
        service.add_document_to_view("doc1", CorpusView.CANONICAL)
        service.add_document_to_view("doc2", CorpusView.FULL)

        assert service.is_document_in_view("doc1", CorpusView.CANONICAL)
        assert not service.is_document_in_view("doc2", CorpusView.CANONICAL)
        assert service.is_document_in_view("doc2", CorpusView.FULL)

    def test_remove_document(self, service):
        """Test removing document from corpus view"""
        service.add_document_to_view("doc1", CorpusView.CANONICAL)
        assert service.is_document_in_view("doc1", CorpusView.CANONICAL)

        service.remove_document_from_view("doc1", CorpusView.CANONICAL)
        assert not service.is_document_in_view("doc1", CorpusView.CANONICAL)

    def test_get_stats(self, service):
        """Test statistics retrieval"""
        service.add_document_to_view("doc1", CorpusView.CANONICAL)
        service.add_document_to_view("doc2", CorpusView.CANONICAL)

        stats = service.get_stats(CorpusView.CANONICAL)

        assert stats["view"] == "canonical"
        assert stats["total_documents"] == 2

    def test_get_collection_name(self, service):
        """Test collection name generation"""
        canonical_name = service.get_collection_name(CorpusView.CANONICAL, "docs")
        full_name = service.get_collection_name(CorpusView.FULL, "docs")

        assert canonical_name == "docs_canonical"
        assert full_name == "docs_full"

    def test_suggest_view_default(self, service):
        """Test view suggestion defaults to canonical"""
        view = service.suggest_view_for_query("search")
        assert view == CorpusView.CANONICAL

    def test_suggest_view_audit(self, service):
        """Test view suggestion for audit uses full"""
        view = service.suggest_view_for_query("audit")
        assert view == CorpusView.FULL

    def test_suggest_view_compliance(self, service):
        """Test view suggestion for compliance uses full"""
        view = service.suggest_view_for_query("compliance")
        assert view == CorpusView.FULL

    def test_suggest_view_user_preference(self, service):
        """Test user preference overrides suggestion"""
        # User wants full even for search
        view = service.suggest_view_for_query(
            "search",
            user_preference=CorpusView.FULL
        )
        assert view == CorpusView.FULL

    def test_multiple_documents(self, service):
        """Test managing multiple documents"""
        docs = [
            ("doc1", {"quality_score": 0.9, "signalness": 0.8, "do_index": True, "is_duplicate": False}),
            ("doc2", {"quality_score": 0.4, "signalness": 0.3, "do_index": True, "is_duplicate": False}),
            ("doc3", {"quality_score": 0.8, "signalness": 0.7, "do_index": True, "is_duplicate": False}),
        ]

        for doc_id, metadata in docs:
            views = service.get_corpus_for_document(metadata)
            for view in views:
                service.add_document_to_view(doc_id, view)

        # Check counts
        assert len(service.canonical_doc_ids) == 2  # doc1, doc3
        assert len(service.full_doc_ids) == 3  # all docs

    def test_edge_case_exact_threshold(self, service):
        """Test document at exact quality threshold"""
        metadata = {
            "quality_score": 0.6,  # Exactly at threshold
            "signalness": 0.5,     # Exactly at threshold
            "do_index": True,
            "is_duplicate": False
        }

        result = service.should_add_to_canonical(metadata)
        # At threshold should pass (>=, not >)
        assert result is True
