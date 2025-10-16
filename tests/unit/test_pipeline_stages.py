"""
Unit tests for individual pipeline stages

Tests each stage in isolation with mocked dependencies.
"""

import pytest
from unittest.mock import AsyncMock, Mock, MagicMock
from src.pipeline.base import StageResult, StageContext
from src.pipeline.models import (
    RawDocument,
    EnrichedDocument,
    ChunkedDocument,
    StoredDocument,
    ExportedDocument,
    Chunk
)
from src.pipeline.stages import (
    EnrichmentStage,
    QualityGateStage,
    ChunkingStage,
    StorageStage,
    ExportStage
)
from src.models.schemas import DocumentType, ComplexityLevel


@pytest.mark.asyncio
class TestEnrichmentStage:
    """Test suite for EnrichmentStage"""

    async def test_enrichment_stage_success(self):
        """Test successful enrichment"""
        # Mock service
        mock_service = Mock()
        mock_service.enrich_document = AsyncMock(return_value={
            "title": "Test Document",
            "summary": "Test summary",
            "tags": ["test", "document"],
            "document_type": "text"
        })
        mock_service.extract_enriched_lists = Mock(return_value={
            "people": ["Alice", "Bob"],
            "organizations": ["ACME Corp"],
            "locations": [],
            "technologies": [],
            "tags": ["test"],
            "dates": []
        })

        stage = EnrichmentStage(enrichment_service=mock_service)
        context = StageContext(doc_id="doc_123", filename="test.txt")
        raw_doc = RawDocument(content="Test content", filename="test.txt")

        result, output = await stage.process(raw_doc, context)

        assert result == StageResult.CONTINUE
        assert isinstance(output, EnrichedDocument)
        assert output.content == "Test content"
        assert output.people == ["Alice", "Bob"]
        assert output.organizations == ["ACME Corp"]
        assert mock_service.enrich_document.called

    async def test_enrichment_stage_error_handling(self):
        """Test enrichment error handling"""
        mock_service = Mock()
        mock_service.enrich_document = AsyncMock(side_effect=Exception("LLM error"))

        stage = EnrichmentStage(enrichment_service=mock_service)
        context = StageContext(doc_id="doc_123", filename="test.txt")
        raw_doc = RawDocument(content="Test content")

        result, output = await stage.process(raw_doc, context)

        assert result == StageResult.ERROR
        assert output is None


@pytest.mark.asyncio
class TestQualityGateStage:
    """Test suite for QualityGateStage"""

    async def test_quality_gate_passes_high_quality(self):
        """Test that high quality documents pass the gate"""
        mock_service = Mock()
        mock_service.score_document = Mock(return_value={
            "quality_score": 0.85,
            "novelty_score": 0.75,
            "actionability_score": 0.80,
            "signalness": 0.82,
            "do_index": True
        })

        stage = QualityGateStage(quality_service=mock_service, enable_gating=True)
        context = StageContext(doc_id="doc_123", filename="test.txt")
        enriched_doc = EnrichedDocument(
            content="Test content",
            enriched_metadata={"title": "Test"}
        )

        result, output = await stage.process(enriched_doc, context)

        assert result == StageResult.CONTINUE
        assert output.quality_score == 0.85
        assert output.do_index is True
        assert context.gated is False

    async def test_quality_gate_blocks_low_quality(self):
        """Test that low quality documents are gated"""
        mock_service = Mock()
        mock_service.score_document = Mock(return_value={
            "quality_score": 0.25,
            "novelty_score": 0.15,
            "actionability_score": 0.10,
            "signalness": 0.20,
            "do_index": False,
            "gate_reason": "Low quality score"
        })

        stage = QualityGateStage(quality_service=mock_service, enable_gating=True)
        context = StageContext(doc_id="doc_123", filename="test.txt")
        enriched_doc = EnrichedDocument(
            content="Test content",
            enriched_metadata={"title": "Test"}
        )

        result, output = await stage.process(enriched_doc, context)

        assert result == StageResult.STOP
        assert output.do_index is False
        assert context.gated is True
        assert context.gate_reason == "Low quality score"

    async def test_quality_gate_disabled(self):
        """Test quality gate with gating disabled (score only)"""
        mock_service = Mock()
        mock_service.score_document = Mock(return_value={
            "quality_score": 0.25,
            "novelty_score": 0.15,
            "actionability_score": 0.10,
            "signalness": 0.20,
            "do_index": False
        })

        stage = QualityGateStage(quality_service=mock_service, enable_gating=False)
        context = StageContext(doc_id="doc_123", filename="test.txt")
        enriched_doc = EnrichedDocument(
            content="Test content",
            enriched_metadata={"title": "Test"}
        )

        result, output = await stage.process(enriched_doc, context)

        # Should pass even though do_index=False, because gating is disabled
        assert result == StageResult.CONTINUE
        assert output.quality_score == 0.25

    async def test_quality_gate_should_skip_when_disabled(self):
        """Test that quality gate can be skipped"""
        mock_service = Mock()
        stage = QualityGateStage(quality_service=mock_service, enable_gating=False)
        context = StageContext(doc_id="doc_123", filename="test.txt")

        assert stage.should_skip(context) is True

    async def test_quality_gate_error_handling(self):
        """Test quality gate error handling (fail open)"""
        mock_service = Mock()
        mock_service.score_document = Mock(side_effect=Exception("Scoring error"))

        stage = QualityGateStage(quality_service=mock_service, enable_gating=True)
        context = StageContext(doc_id="doc_123", filename="test.txt")
        enriched_doc = EnrichedDocument(
            content="Test content",
            enriched_metadata={"title": "Test"}
        )

        result, output = await stage.process(enriched_doc, context)

        # Should fail open (allow document through on error)
        assert result == StageResult.CONTINUE


@pytest.mark.asyncio
class TestChunkingStage:
    """Test suite for ChunkingStage"""

    async def test_chunking_stage_text_document(self):
        """Test chunking of text document"""
        mock_service = Mock()
        mock_service.chunk_text = Mock(return_value=[
            {"content": "Chunk 1", "metadata": {"chunk_type": "paragraph"}},
            {"content": "Chunk 2", "metadata": {"chunk_type": "paragraph", "section_title": "Section 1"}}
        ])

        stage = ChunkingStage(chunking_service=mock_service)
        context = StageContext(doc_id="doc_123", filename="test.txt")
        enriched_doc = EnrichedDocument(
            content="Test content",
            enriched_metadata={"title": "Test"},
            document_type=DocumentType.text
        )

        result, output = await stage.process(enriched_doc, context)

        assert result == StageResult.CONTINUE
        assert isinstance(output, ChunkedDocument)
        assert len(output.chunks) == 2
        assert output.chunks[0].content == "Chunk 1"
        assert output.chunks[1].section_title == "Section 1"
        assert mock_service.chunk_text.called

    async def test_chunking_stage_chat_log(self):
        """Test chunking of chat log (turn-based)"""
        mock_service = Mock()
        mock_service.chunk_chat_log = Mock(return_value=[
            {"content": "User: Hello", "metadata": {"chunk_type": "chat_turn"}},
            {"content": "Assistant: Hi!", "metadata": {"chunk_type": "chat_turn"}}
        ])

        stage = ChunkingStage(chunking_service=mock_service)
        context = StageContext(doc_id="doc_123", filename="chat.md")
        enriched_doc = EnrichedDocument(
            content="Chat log content",
            enriched_metadata={"title": "Chat"},
            document_type=DocumentType.llm_chat
        )

        result, output = await stage.process(enriched_doc, context)

        assert result == StageResult.CONTINUE
        assert len(output.chunks) == 2
        assert mock_service.chunk_chat_log.called
        assert not mock_service.chunk_text.called

    async def test_chunking_stage_error_handling(self):
        """Test chunking error handling"""
        mock_service = Mock()
        mock_service.chunk_text = Mock(side_effect=Exception("Chunking error"))

        stage = ChunkingStage(chunking_service=mock_service)
        context = StageContext(doc_id="doc_123", filename="test.txt")
        enriched_doc = EnrichedDocument(
            content="Test content",
            enriched_metadata={"title": "Test"}
        )

        result, output = await stage.process(enriched_doc, context)

        assert result == StageResult.ERROR
        assert output is None


@pytest.mark.asyncio
class TestStorageStage:
    """Test suite for StorageStage"""

    async def test_storage_stage_success(self):
        """Test successful storage in ChromaDB"""
        # Mock vector service with collection
        mock_collection = Mock()
        mock_collection.add = Mock()

        mock_service = Mock()
        mock_service.collection = mock_collection

        stage = StorageStage(vector_service=mock_service)
        context = StageContext(doc_id="doc_123", filename="test.txt")

        chunks = [
            Chunk(content="Chunk 1", chunk_index=0),
            Chunk(content="Chunk 2", chunk_index=1, section_title="Section 1")
        ]
        chunked_doc = ChunkedDocument(
            doc_id="doc_123",
            chunks=chunks,
            enriched_metadata={"title": "Test"},
            people=["Alice"],
            organizations=["ACME"]
        )

        result, output = await stage.process(chunked_doc, context)

        assert result == StageResult.CONTINUE
        assert isinstance(output, StoredDocument)
        assert output.chunk_count == 2
        assert len(output.chunk_ids) == 2
        assert output.chunk_ids[0] == "doc_123_chunk_0"
        assert mock_collection.add.called

    async def test_storage_stage_flattens_entities(self):
        """Test that storage stage flattens entity lists"""
        mock_collection = Mock()
        mock_collection.add = Mock()

        mock_service = Mock()
        mock_service.collection = mock_collection

        stage = StorageStage(vector_service=mock_service)
        context = StageContext(doc_id="doc_123", filename="test.txt")

        chunks = [Chunk(content="Chunk 1", chunk_index=0)]
        chunked_doc = ChunkedDocument(
            doc_id="doc_123",
            chunks=chunks,
            enriched_metadata={"title": "Test"},
            people=["Alice", "Bob"],
            organizations=["ACME Corp"]
        )

        await stage.process(chunked_doc, context)

        # Verify add was called with flattened entities
        call_args = mock_collection.add.call_args
        metadata = call_args.kwargs["metadatas"][0]

        # ChromaDBAdapter should flatten to comma-separated strings
        assert "people" in metadata
        assert "organizations" in metadata

    async def test_storage_stage_error_handling(self):
        """Test storage error handling"""
        mock_collection = Mock()
        mock_collection.add = Mock(side_effect=Exception("ChromaDB error"))

        mock_service = Mock()
        mock_service.collection = mock_collection

        stage = StorageStage(vector_service=mock_service)
        context = StageContext(doc_id="doc_123", filename="test.txt")

        chunks = [Chunk(content="Chunk 1", chunk_index=0)]
        chunked_doc = ChunkedDocument(
            doc_id="doc_123",
            chunks=chunks,
            enriched_metadata={"title": "Test"}
        )

        result, output = await stage.process(chunked_doc, context)

        assert result == StageResult.ERROR
        assert output is None


@pytest.mark.asyncio
class TestExportStage:
    """Test suite for ExportStage"""

    async def test_export_stage_success(self):
        """Test successful Obsidian export"""
        mock_service = Mock()
        mock_service.create_obsidian_note = Mock(return_value="/vault/test.md")

        stage = ExportStage(obsidian_service=mock_service, enable_export=True)
        context = StageContext(doc_id="doc_123", filename="test.txt")

        stored_doc = StoredDocument(
            doc_id="doc_123",
            chunk_ids=["chunk_0", "chunk_1"],
            chunk_count=2,
            enriched_metadata={
                "title": "Test Document",
                "summary": "Test summary",
                "tags": ["test"],
                "people": ["Alice"],
                "organizations": []
            }
        )

        result, output = await stage.process(stored_doc, context)

        assert result == StageResult.CONTINUE
        assert isinstance(output, ExportedDocument)
        assert output.obsidian_path == "/vault/test.md"
        assert output.entity_refs_created == 1  # 1 person
        assert mock_service.create_obsidian_note.called

    async def test_export_stage_disabled(self):
        """Test export stage when export is disabled"""
        mock_service = Mock()

        stage = ExportStage(obsidian_service=mock_service, enable_export=False)
        context = StageContext(doc_id="doc_123", filename="test.txt")

        stored_doc = StoredDocument(
            doc_id="doc_123",
            chunk_ids=["chunk_0"],
            chunk_count=1,
            enriched_metadata={"title": "Test"}
        )

        result, output = await stage.process(stored_doc, context)

        assert result == StageResult.CONTINUE
        assert output.obsidian_path is None
        assert not mock_service.create_obsidian_note.called

    async def test_export_stage_should_skip_when_disabled(self):
        """Test that export stage can be skipped"""
        mock_service = Mock()
        stage = ExportStage(obsidian_service=mock_service, enable_export=False)
        context = StageContext(doc_id="doc_123", filename="test.txt")

        assert stage.should_skip(context) is True

    async def test_export_stage_error_handling(self):
        """Test export error handling (fail open - export not critical)"""
        mock_service = Mock()
        mock_service.create_obsidian_note = Mock(side_effect=Exception("Export error"))

        stage = ExportStage(obsidian_service=mock_service, enable_export=True)
        context = StageContext(doc_id="doc_123", filename="test.txt")

        stored_doc = StoredDocument(
            doc_id="doc_123",
            chunk_ids=["chunk_0"],
            chunk_count=1,
            enriched_metadata={"title": "Test"}
        )

        result, output = await stage.process(stored_doc, context)

        # Export failure is not critical - document is already stored
        assert result == StageResult.CONTINUE
        assert output.obsidian_path is None
