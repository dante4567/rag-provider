"""
Unit tests for pipeline factory and data models

Tests the create_ingestion_pipeline factory and Pydantic data models.
"""

import pytest
from unittest.mock import Mock
from src.pipeline import (
    create_ingestion_pipeline,
    RawDocument,
    EnrichedDocument,
    ChunkedDocument,
    StoredDocument,
    ExportedDocument,
    Chunk,
    Pipeline
)
from src.models.schemas import DocumentType, ComplexityLevel


class TestPipelineFactory:
    """Test suite for create_ingestion_pipeline factory"""

    def test_factory_creates_pipeline_with_all_stages(self):
        """Test that factory creates pipeline with all 5 stages"""
        # Mock services
        enrichment_service = Mock()
        quality_service = Mock()
        chunking_service = Mock()
        vector_service = Mock()
        obsidian_service = Mock()

        pipeline = create_ingestion_pipeline(
            enrichment_service=enrichment_service,
            quality_service=quality_service,
            chunking_service=chunking_service,
            vector_service=vector_service,
            obsidian_service=obsidian_service
        )

        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.stages) == 5
        assert pipeline.stages[0].name == "enrichment"
        assert pipeline.stages[1].name == "quality_gate"
        assert pipeline.stages[2].name == "chunking"
        assert pipeline.stages[3].name == "storage"
        assert pipeline.stages[4].name == "export"

    def test_factory_respects_enable_flags(self):
        """Test that factory respects enable_quality_gate and enable_export flags"""
        enrichment_service = Mock()
        quality_service = Mock()
        chunking_service = Mock()
        vector_service = Mock()
        obsidian_service = Mock()

        pipeline = create_ingestion_pipeline(
            enrichment_service=enrichment_service,
            quality_service=quality_service,
            chunking_service=chunking_service,
            vector_service=vector_service,
            obsidian_service=obsidian_service,
            enable_quality_gate=False,
            enable_export=False
        )

        # Stages are created but with gating/export disabled
        quality_gate_stage = pipeline.stages[1]
        export_stage = pipeline.stages[4]

        assert quality_gate_stage.enable_gating is False
        assert export_stage.enable_export is False

    def test_factory_custom_pipeline_name(self):
        """Test factory with custom pipeline name"""
        enrichment_service = Mock()
        quality_service = Mock()
        chunking_service = Mock()
        vector_service = Mock()
        obsidian_service = Mock()

        pipeline = create_ingestion_pipeline(
            enrichment_service=enrichment_service,
            quality_service=quality_service,
            chunking_service=chunking_service,
            vector_service=vector_service,
            obsidian_service=obsidian_service,
            pipeline_name="custom_pipeline"
        )

        assert pipeline.name == "custom_pipeline"


class TestRawDocument:
    """Test suite for RawDocument model"""

    def test_raw_document_minimal(self):
        """Test RawDocument with minimal fields"""
        doc = RawDocument(content="Test content")

        assert doc.content == "Test content"
        assert doc.filename is None
        assert doc.document_type == DocumentType.text
        assert doc.metadata == {}

    def test_raw_document_full(self):
        """Test RawDocument with all fields"""
        doc = RawDocument(
            content="Test content",
            filename="test.pdf",
            document_type=DocumentType.pdf,
            metadata={"author": "Alice"}
        )

        assert doc.content == "Test content"
        assert doc.filename == "test.pdf"
        assert doc.document_type == DocumentType.pdf
        assert doc.metadata["author"] == "Alice"


class TestEnrichedDocument:
    """Test suite for EnrichedDocument model"""

    def test_enriched_document_minimal(self):
        """Test EnrichedDocument with minimal fields"""
        doc = EnrichedDocument(
            content="Test content",
            enriched_metadata={"title": "Test"}
        )

        assert doc.content == "Test content"
        assert doc.enriched_metadata["title"] == "Test"
        assert doc.people == []
        assert doc.organizations == []
        assert doc.quality_score == 0.0
        assert doc.do_index is True

    def test_enriched_document_full(self):
        """Test EnrichedDocument with all fields"""
        doc = EnrichedDocument(
            content="Test content",
            enriched_metadata={"title": "Test"},
            people=["Alice", "Bob"],
            organizations=["ACME Corp"],
            locations=["New York"],
            technologies=["Python"],
            tags=["test"],
            dates=["2025-10-16"],
            quality_score=0.85,
            novelty_score=0.75,
            actionability_score=0.80,
            signalness=0.82,
            do_index=True,
            gate_reason=None,
            filename="test.pdf",
            document_type=DocumentType.pdf
        )

        assert doc.people == ["Alice", "Bob"]
        assert doc.organizations == ["ACME Corp"]
        assert doc.quality_score == 0.85
        assert doc.do_index is True


class TestChunk:
    """Test suite for Chunk model"""

    def test_chunk_minimal(self):
        """Test Chunk with minimal fields"""
        chunk = Chunk(content="Chunk content", chunk_index=0)

        assert chunk.content == "Chunk content"
        assert chunk.chunk_index == 0
        assert chunk.chunk_type == "paragraph"
        assert chunk.section_title is None
        assert chunk.parent_sections == []
        assert chunk.estimated_tokens > 0

    def test_chunk_full(self):
        """Test Chunk with all fields"""
        chunk = Chunk(
            content="Chunk content",
            chunk_index=5,
            chunk_type="heading",
            section_title="Introduction",
            parent_sections=["Chapter 1", "Section 1.1"],
            estimated_tokens=100
        )

        assert chunk.chunk_index == 5
        assert chunk.chunk_type == "heading"
        assert chunk.section_title == "Introduction"
        assert chunk.parent_sections == ["Chapter 1", "Section 1.1"]
        assert chunk.estimated_tokens == 100


class TestChunkedDocument:
    """Test suite for ChunkedDocument model"""

    def test_chunked_document_minimal(self):
        """Test ChunkedDocument with minimal fields"""
        chunks = [
            Chunk(content="Chunk 1", chunk_index=0),
            Chunk(content="Chunk 2", chunk_index=1)
        ]
        doc = ChunkedDocument(
            doc_id="doc_123",
            chunks=chunks,
            enriched_metadata={"title": "Test"}
        )

        assert doc.doc_id == "doc_123"
        assert len(doc.chunks) == 2
        assert doc.enriched_metadata["title"] == "Test"
        assert doc.people == []

    def test_chunked_document_full(self):
        """Test ChunkedDocument with all fields"""
        chunks = [Chunk(content="Chunk 1", chunk_index=0)]
        doc = ChunkedDocument(
            doc_id="doc_123",
            chunks=chunks,
            enriched_metadata={"title": "Test"},
            people=["Alice"],
            organizations=["ACME"],
            locations=["NYC"],
            technologies=["Python"],
            tags=["test"],
            dates=["2025-10-16"],
            filename="test.pdf",
            document_type=DocumentType.pdf
        )

        assert doc.people == ["Alice"]
        assert doc.organizations == ["ACME"]
        assert doc.filename == "test.pdf"


class TestStoredDocument:
    """Test suite for StoredDocument model"""

    def test_stored_document(self):
        """Test StoredDocument model"""
        doc = StoredDocument(
            doc_id="doc_123",
            chunk_ids=["chunk_0", "chunk_1", "chunk_2"],
            chunk_count=3,
            enriched_metadata={"title": "Test"}
        )

        assert doc.doc_id == "doc_123"
        assert len(doc.chunk_ids) == 3
        assert doc.chunk_count == 3
        assert doc.enriched_metadata["title"] == "Test"


class TestExportedDocument:
    """Test suite for ExportedDocument model"""

    def test_exported_document_minimal(self):
        """Test ExportedDocument with minimal fields"""
        doc = ExportedDocument(
            doc_id="doc_123",
            metadata={"title": "Test"}
        )

        assert doc.doc_id == "doc_123"
        assert doc.obsidian_path is None
        assert doc.entity_refs_created == 0
        assert doc.metadata["title"] == "Test"

    def test_exported_document_full(self):
        """Test ExportedDocument with all fields"""
        doc = ExportedDocument(
            doc_id="doc_123",
            obsidian_path="/vault/test.md",
            entity_refs_created=10,
            metadata={"title": "Test"}
        )

        assert doc.doc_id == "doc_123"
        assert doc.obsidian_path == "/vault/test.md"
        assert doc.entity_refs_created == 10


class TestDataModelIntegration:
    """Test data flow between models"""

    def test_pipeline_data_flow(self):
        """Test that data models work together in sequence"""
        # 1. Start with RawDocument
        raw = RawDocument(
            content="Test content",
            filename="test.txt",
            document_type=DocumentType.text
        )

        # 2. EnrichmentStage produces EnrichedDocument
        enriched = EnrichedDocument(
            content=raw.content,
            enriched_metadata={"title": "Test"},
            people=["Alice"],
            filename=raw.filename,
            document_type=raw.document_type
        )

        # 3. ChunkingStage produces ChunkedDocument
        chunks = [
            Chunk(content="Chunk 1", chunk_index=0),
            Chunk(content="Chunk 2", chunk_index=1)
        ]
        chunked = ChunkedDocument(
            doc_id="doc_123",
            chunks=chunks,
            enriched_metadata=enriched.enriched_metadata,
            people=enriched.people,
            filename=enriched.filename
        )

        # 4. StorageStage produces StoredDocument
        stored = StoredDocument(
            doc_id=chunked.doc_id,
            chunk_ids=["doc_123_chunk_0", "doc_123_chunk_1"],
            chunk_count=len(chunked.chunks),
            enriched_metadata=chunked.enriched_metadata
        )

        # 5. ExportStage produces ExportedDocument
        exported = ExportedDocument(
            doc_id=stored.doc_id,
            obsidian_path="/vault/test.md",
            entity_refs_created=1,
            metadata=stored.enriched_metadata
        )

        # Verify data flows through pipeline
        assert exported.doc_id == "doc_123"
        assert exported.metadata["title"] == "Test"
