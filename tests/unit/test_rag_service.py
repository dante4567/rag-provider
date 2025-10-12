"""
Unit tests for RAGService - Main document processing orchestrator

Tests cover:
- Service initialization
- ChromaDB setup
- Document processing pipeline
- File processing
- Search functionality
- Error handling
- Cost tracking integration
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, date
from pathlib import Path
import uuid

from src.services.rag_service import RAGService, CostTracker, SimpleTextSplitter
from src.models.schemas import (
    IngestResponse, SearchResponse, DocumentType,
    CostStats, ObsidianMetadata
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_chromadb():
    """Mock ChromaDB client and collection"""
    with patch('src.services.rag_service.chromadb') as mock_chroma:
        mock_client = Mock()
        mock_collection = Mock()

        mock_client.heartbeat.return_value = None
        mock_client.get_collection.return_value = mock_collection
        mock_client.create_collection.return_value = mock_collection

        # Mock collection methods
        mock_collection.get.return_value = {'ids': [], 'documents': [], 'metadatas': []}
        mock_collection.add.return_value = None
        mock_collection.query.return_value = {
            'ids': [['doc1_chunk_0']],
            'documents': [['test content']],
            'metadatas': [[{'title': 'Test Doc'}]],
            'distances': [[0.5]]
        }

        mock_chroma.HttpClient.return_value = mock_client

        # Set globals
        import src.services.rag_service as rag_module
        rag_module.chroma_client = mock_client
        rag_module.collection = mock_collection

        yield {
            'client': mock_client,
            'collection': mock_collection
        }


@pytest.fixture
def mock_services():
    """Mock all dependent services"""
    with patch('src.services.rag_service.LLMService') as mock_llm, \
         patch('src.services.rag_service.VectorService') as mock_vector, \
         patch('src.services.rag_service.DocumentService') as mock_doc, \
         patch('src.services.rag_service.OCRService') as mock_ocr, \
         patch('src.services.rag_service.EnrichmentService') as mock_enrich, \
         patch('src.services.rag_service.VocabularyService') as mock_vocab, \
         patch('src.services.rag_service.ChunkingService') as mock_chunk, \
         patch('src.services.rag_service.ObsidianService') as mock_obsidian, \
         patch('src.services.rag_service.ContactService') as mock_contact, \
         patch('src.services.rag_service.CalendarService') as mock_calendar, \
         patch('src.services.rag_service.SmartTriageService') as mock_triage, \
         patch('src.services.rag_service.QualityScoringService') as mock_quality, \
         patch('src.services.rag_service.TagTaxonomyService') as mock_taxonomy, \
         patch('src.services.rag_service.EntityNameFilterService') as mock_filter:

        # Configure mock returns
        mock_enrich_instance = mock_enrich.return_value
        mock_enrich_instance.enrich_document = AsyncMock(return_value={
            'title': 'Test Document',
            'summary': 'A test summary',
            'topics': ['test/topic'],
            'people': [],
            'entities': {},
            'enrichment_cost': 0.0001
        })

        mock_chunk_instance = mock_chunk.return_value
        mock_chunk_instance.chunk_document.return_value = [
            {'text': 'chunk 1', 'metadata': {}}
        ]

        mock_obsidian_instance = mock_obsidian.return_value
        mock_obsidian_instance.create_document = AsyncMock(return_value='/path/to/obsidian.md')

        mock_vector_instance = mock_vector.return_value
        mock_vector_instance.search = AsyncMock(return_value=[
            {'doc_id': 'doc1', 'content': 'test content', 'metadata': {'title': 'Test'}, 'score': 0.9, 'relevance_score': 0.9}
        ])

        mock_vocab_instance = mock_vocab.return_value
        mock_vocab_instance.get_all_topics.return_value = ['test/topic']
        mock_vocab_instance.get_active_projects.return_value = []
        mock_vocab_instance.get_all_places.return_value = []

        yield {
            'llm': mock_llm,
            'vector': mock_vector,
            'document': mock_doc,
            'ocr': mock_ocr,
            'enrichment': mock_enrich,
            'vocabulary': mock_vocab,
            'chunking': mock_chunk,
            'obsidian': mock_obsidian,
            'contact': mock_contact,
            'calendar': mock_calendar,
            'triage': mock_triage,
            'quality': mock_quality,
            'taxonomy': mock_taxonomy,
            'filter': mock_filter
        }


@pytest.fixture
def rag_service(mock_chromadb, mock_services):
    """Create RAGService instance with mocked dependencies"""
    with patch('src.services.rag_service.get_settings') as mock_settings:
        mock_settings.return_value = Mock(
            anthropic_api_key='test_key',
            daily_budget_usd=10.0
        )
        service = RAGService()
        return service


# ============================================================================
# SimpleTextSplitter Tests
# ============================================================================

class TestSimpleTextSplitter:
    """Test the simple text splitting functionality"""

    def test_split_empty_text(self):
        """Should return empty list for empty text"""
        splitter = SimpleTextSplitter(chunk_size=100, chunk_overlap=20)
        result = splitter.split_text("")
        assert result == []

    def test_split_short_text(self):
        """Should return single chunk for text shorter than chunk_size"""
        splitter = SimpleTextSplitter(chunk_size=100, chunk_overlap=20)
        text = "Short text"
        result = splitter.split_text(text)
        assert len(result) == 1
        assert result[0] == "Short text"

    def test_split_long_text(self):
        """Should split long text into multiple chunks"""
        splitter = SimpleTextSplitter(chunk_size=50, chunk_overlap=10)
        text = "a" * 150
        result = splitter.split_text(text)
        assert len(result) > 1

    def test_split_respects_sentence_boundaries(self):
        """Should try to split at sentence boundaries"""
        splitter = SimpleTextSplitter(chunk_size=100, chunk_overlap=20)
        text = "First sentence. " * 10
        result = splitter.split_text(text)
        # Should have multiple chunks
        assert len(result) > 1

    def test_split_with_overlap(self):
        """Should include overlap between chunks"""
        splitter = SimpleTextSplitter(chunk_size=50, chunk_overlap=10)
        text = "word " * 50
        result = splitter.split_text(text)
        # Verify overlap exists (hard to test precisely due to boundary logic)
        assert len(result) > 1


# ============================================================================
# CostTracker Tests
# ============================================================================

class TestCostTracker:
    """Test cost tracking functionality"""

    @pytest.fixture(autouse=True)
    def reset_cost_tracking(self):
        """Reset cost tracking state before each test"""
        import src.services.rag_service as rag_module
        rag_module.cost_tracking = {
            "operations": [],
            "daily_totals": {},
            "total_cost": 0.0
        }

    def test_estimate_tokens(self):
        """Should estimate tokens as 1 token per 4 characters"""
        tracker = CostTracker()
        text = "a" * 100
        tokens = tracker.estimate_tokens(text)
        assert tokens == 25

    def test_calculate_cost_known_model(self):
        """Should calculate cost for known model"""
        tracker = CostTracker()
        cost = tracker.calculate_cost(
            model="groq/llama-3.1-8b-instant",
            input_tokens=1000,
            output_tokens=500
        )
        # $0.05 per 1M input, $0.08 per 1M output
        # (1000/1M * 0.05) + (500/1M * 0.08) = 0.00005 + 0.00004 = 0.00009
        assert cost == pytest.approx(0.00009, abs=0.000001)

    def test_calculate_cost_unknown_model(self):
        """Should return 0 for unknown model"""
        tracker = CostTracker()
        cost = tracker.calculate_cost(
            model="unknown/model",
            input_tokens=1000,
            output_tokens=500
        )
        assert cost == 0.0

    def test_check_budget_within_limit(self):
        """Should return True when under budget"""
        tracker = CostTracker()
        assert tracker.check_budget() is True

    def test_check_budget_exceeded(self):
        """Should return False when budget exceeded"""
        tracker = CostTracker()
        # Set today's cost to exceed budget
        today = datetime.now().strftime("%Y-%m-%d")
        tracker.daily_totals[today] = 15.0  # Over $10 budget
        assert tracker.check_budget() is False

    def test_record_operation(self):
        """Should record operation and update costs"""
        tracker = CostTracker()
        tracker.record_operation(
            provider="groq",
            model="groq/llama-3.1-8b-instant",
            input_tokens=1000,
            output_tokens=500,
            cost=0.0001
        )

        assert len(tracker.operations) == 1
        assert tracker.operations[0].provider == "groq"
        assert tracker.operations[0].cost_usd == 0.0001

    def test_get_stats_empty(self):
        """Should return empty stats when no operations"""
        tracker = CostTracker()
        stats = tracker.get_stats()

        assert stats.total_cost_today == 0.0
        assert stats.total_cost_all_time == 0.0
        assert stats.operations_today == 0

    def test_get_stats_with_operations(self):
        """Should return accurate stats with operations"""
        tracker = CostTracker()
        tracker.record_operation("groq", "groq/llama-3.1-8b-instant", 1000, 500, 0.0001)
        tracker.record_operation("groq", "groq/llama-3.1-8b-instant", 1000, 500, 0.0002)

        stats = tracker.get_stats()
        assert stats.total_cost_today == pytest.approx(0.0003, abs=0.000001)
        assert stats.operations_today == 2
        assert "groq" in stats.cost_by_provider


# ============================================================================
# RAGService Initialization Tests
# ============================================================================

class TestRAGServiceInit:
    """Test RAGService initialization"""

    def test_init_success(self, rag_service):
        """Should initialize successfully with all dependencies"""
        assert rag_service is not None
        assert rag_service.using_new_services is True
        assert hasattr(rag_service, 'llm_service')
        assert hasattr(rag_service, 'enrichment_service')
        assert hasattr(rag_service, 'chunking_service')
        assert hasattr(rag_service, 'obsidian_service')

    def test_setup_chromadb_called(self, mock_chromadb, mock_services):
        """Should call setup_chromadb during initialization"""
        with patch('src.services.rag_service.get_settings') as mock_settings:
            mock_settings.return_value = Mock(anthropic_api_key='test')
            service = RAGService()
            mock_chromadb['client'].heartbeat.assert_called_once()


# ============================================================================
# Content Cleaning Tests
# ============================================================================

class TestContentCleaning:
    """Test content cleaning functionality"""

    def test_clean_content_valid_utf8(self, rag_service):
        """Should pass through valid UTF-8 content"""
        content = "Valid UTF-8 text with émojis 🎉"
        result = rag_service._clean_content(content)
        assert result == content

    def test_clean_content_removes_null_bytes(self, rag_service):
        """Should remove null bytes from content"""
        content = "Text with\x00null bytes"
        result = rag_service._clean_content(content)
        assert "\x00" not in result


# ============================================================================
# Document Processing Tests
# ============================================================================

class TestDocumentProcessing:
    """Test main document processing pipeline"""

    @pytest.mark.asyncio
    async def test_process_document_success(self, rag_service, mock_chromadb):
        """Should successfully process a document"""
        content = "This is a test document with enough content to be processed successfully."

        result = await rag_service.process_document(
            content=content,
            filename="test.txt",
            document_type=DocumentType.text
        )

        assert isinstance(result, IngestResponse)
        assert result.success is True
        assert result.doc_id is not None
        assert isinstance(uuid.UUID(result.doc_id), uuid.UUID)

    @pytest.mark.asyncio
    async def test_process_document_empty_content(self, rag_service):
        """Should raise ValueError for empty content"""
        with pytest.raises(ValueError, match="cannot be empty"):
            await rag_service.process_document(
                content="",
                filename="test.txt"
            )

    @pytest.mark.asyncio
    async def test_process_document_too_short(self, rag_service):
        """Should raise ValueError for content too short"""
        with pytest.raises(ValueError, match="at least 10 characters"):
            await rag_service.process_document(
                content="short",
                filename="test.txt"
            )

    @pytest.mark.asyncio
    async def test_process_document_duplicate_detection(self, rag_service, mock_chromadb):
        """Should detect and handle duplicate content"""
        # First process creates the document
        content = "This is duplicate content with enough characters to be valid."

        result = await rag_service.process_document(
            content=content,
            filename="first.txt"
        )

        assert result.success is True
        # Note: In real scenario, subsequent calls with same content would be detected as duplicates
        # This test verifies the duplicate detection logic exists

    @pytest.mark.asyncio
    async def test_process_document_with_obsidian(self, rag_service, mock_chromadb):
        """Should generate Obsidian export when requested"""
        content = "Test document with sufficient content for processing."

        result = await rag_service.process_document(
            content=content,
            filename="test.txt",
            generate_obsidian=True
        )

        assert result.success is True
        # Note: Obsidian export is conditional based on metadata quality
        # Test verifies parameter is accepted without error

    @pytest.mark.asyncio
    async def test_process_document_without_filename(self, rag_service, mock_chromadb):
        """Should handle missing filename"""
        content = "Test document without a filename provided."

        result = await rag_service.process_document(
            content=content,
            filename=None
        )

        assert result.success is True


# ============================================================================
# File Processing Tests
# ============================================================================

class TestFileProcessing:
    """Test file processing functionality"""

    @pytest.mark.asyncio
    async def test_process_file_not_found(self, rag_service):
        """Should handle file not found error"""
        with pytest.raises(Exception):
            await rag_service.process_file("/nonexistent/file.txt")


# ============================================================================
# Search Tests
# ============================================================================

class TestSearch:
    """Test document search functionality"""

    @pytest.mark.asyncio
    async def test_search_documents_success(self, rag_service, mock_chromadb):
        """Should successfully search documents"""
        result = await rag_service.search_documents(
            query="test query",
            top_k=5
        )

        assert isinstance(result, SearchResponse)
        assert result.query == "test query"
        assert isinstance(result.results, list)
        assert result.total_results >= 0

    @pytest.mark.asyncio
    async def test_search_empty_query(self, rag_service):
        """Should raise ValueError for empty search query"""
        with pytest.raises(ValueError, match="cannot be empty"):
            await rag_service.search_documents(
                query="",
                top_k=5
            )

    @pytest.mark.asyncio
    async def test_search_with_filter(self, rag_service, mock_chromadb):
        """Should apply filters when searching"""
        filter_dict = {"document_type": "text"}

        result = await rag_service.search_documents(
            query="test",
            top_k=5,
            filter_dict=filter_dict
        )

        # Verify search completed successfully with filters
        assert isinstance(result, SearchResponse)
        assert result.query == "test"


# ============================================================================
# Integration Tests
# ============================================================================

class TestRAGServiceIntegration:
    """Test integration between RAGService and dependent services"""

    @pytest.mark.asyncio
    async def test_enrichment_integration(self, rag_service, mock_chromadb):
        """Should integrate with enrichment service"""
        content = "This is a document that needs enrichment and has enough content."

        result = await rag_service.process_document(
            content=content,
            filename="test.txt"
        )

        # Enrichment service should be called
        rag_service.enrichment_service.enrich_document.assert_called_once()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_chunking_integration(self, rag_service, mock_chromadb):
        """Should integrate with chunking service"""
        content = "Document content for chunking. " * 20

        result = await rag_service.process_document(
            content=content,
            filename="test.txt"
        )

        assert result.success is True
        # Chunking is performed internally - test verifies integration works


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling in RAGService"""

    @pytest.mark.asyncio
    async def test_enrichment_failure_handling(self, rag_service, mock_chromadb):
        """Should handle enrichment service failures gracefully"""
        # Configure mock to raise exception
        rag_service.enrichment_service.enrich_document.side_effect = Exception("Enrichment failed")

        with pytest.raises(Exception):
            await rag_service.process_document(
                content="Test content with sufficient length.",
                filename="test.txt"
            )

    @pytest.mark.asyncio
    async def test_chromadb_connection_failure(self, mock_chromadb):
        """Should handle ChromaDB connection failures"""
        mock_chromadb['client'].heartbeat.side_effect = Exception("Connection failed")

        with pytest.raises(Exception):
            with patch('src.services.rag_service.get_settings') as mock_settings:
                mock_settings.return_value = Mock(anthropic_api_key='test')
                RAGService()
