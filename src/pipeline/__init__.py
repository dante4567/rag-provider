"""
Pipeline Package - Modular RAG Ingestion Pipeline

This package provides a stage-based pipeline architecture for document ingestion.

Usage:
    from src.pipeline import create_ingestion_pipeline, StageContext

    # Create pipeline with service dependencies
    pipeline = create_ingestion_pipeline(
        enrichment_service=enrichment_service,
        quality_service=quality_service,
        chunking_service=chunking_service,
        vector_service=vector_service,
        obsidian_service=obsidian_service,
        enable_quality_gate=True,
        enable_export=True
    )

    # Create context
    context = StageContext(doc_id="doc_123", filename="example.pdf")

    # Run pipeline
    raw_doc = RawDocument(content="...", filename="example.pdf")
    result, output = await pipeline.run(raw_doc, context)

Pipeline Stages:
    1. EnrichmentStage - LLM-based metadata extraction
    2. QualityGateStage - Quality evaluation and filtering
    3. ChunkingStage - Structure-aware text splitting
    4. StorageStage - ChromaDB vector storage
    5. ExportStage - Obsidian markdown generation

Each stage:
    - Has clear input/output contracts via Pydantic models
    - Is testable in isolation
    - Can be skipped via should_skip()
    - Returns (StageResult, output) tuple
"""

from typing import Optional
from src.pipeline.base import Pipeline, PipelineStage, StageResult, StageContext
from src.pipeline.models import (
    RawDocument,
    EnrichedDocument,
    ChunkedDocument,
    StoredDocument,
    ExportedDocument,
    Chunk
)
from src.pipeline.stages import (
    TriageStage,
    EnrichmentStage,
    QualityGateStage,
    ChunkingStage,
    StorageStage,
    ExportStage
)


def create_ingestion_pipeline(
    enrichment_service,
    quality_service,
    chunking_service,
    vector_service,
    obsidian_service,
    triage_service=None,
    enable_triage: bool = True,
    enable_quality_gate: bool = True,
    enable_export: bool = True,
    pipeline_name: str = "ingestion_pipeline"
) -> Pipeline:
    """
    Factory function to create a configured ingestion pipeline.

    This pipeline handles the full document ingestion flow:
    RawDocument → [Triage] → EnrichedDocument → [QualityGate] → ChunkedDocument → StoredDocument → ExportedDocument

    Args:
        enrichment_service: Service for LLM-based metadata extraction
        quality_service: Service for quality scoring and gating
        chunking_service: Service for structure-aware text splitting
        vector_service: Service for ChromaDB operations
        obsidian_service: Service for Obsidian markdown generation
        triage_service: Service for document triage (optional, auto-created if None)
        enable_triage: Whether to enable triage stage (default: True)
        enable_quality_gate: Whether to enable quality gating (default: True)
        enable_export: Whether to enable Obsidian export (default: True)
        pipeline_name: Optional custom pipeline name

    Returns:
        Configured Pipeline ready to process documents

    Example:
        >>> pipeline = create_ingestion_pipeline(
        ...     enrichment_service=get_enrichment_service(),
        ...     quality_service=get_quality_service(),
        ...     chunking_service=get_chunking_service(),
        ...     vector_service=get_vector_service(),
        ...     obsidian_service=get_obsidian_service()
        ... )
        >>>
        >>> context = StageContext(doc_id="doc_123", filename="test.pdf")
        >>> raw_doc = RawDocument(content="Document text...", filename="test.pdf")
        >>> result, output = await pipeline.run(raw_doc, context)
        >>>
        >>> if result == StageResult.CONTINUE:
        ...     print(f"✅ Document ingested: {output.doc_id}")
        ... elif result == StageResult.STOP:
        ...     print(f"⛔ Document gated: {context.gate_reason}")
    """

    stages = []

    # Stage 1: Triage (optional, runs before enrichment to save costs)
    if enable_triage and triage_service:
        stages.append(
            TriageStage(
                triage_service=triage_service,
                enable_duplicate_detection=True,
                enable_junk_filtering=True,
                name="triage"
            )
        )

    # Stage 2: Enrichment (LLM-based metadata extraction)
    stages.append(
        EnrichmentStage(
            enrichment_service=enrichment_service,
            name="enrichment"
        )
    )

    # Stage 3: Quality Gate (optional, filters low-quality docs)
    stages.append(
        QualityGateStage(
            quality_service=quality_service,
            enable_gating=enable_quality_gate,
            name="quality_gate"
        )
    )

    # Stage 4: Chunking (structure-aware text splitting)
    stages.append(
        ChunkingStage(
            chunking_service=chunking_service,
            name="chunking"
        )
    )

    # Stage 5: Storage (ChromaDB persistence)
    stages.append(
        StorageStage(
            vector_service=vector_service,
            name="storage"
        )
    )

    # Stage 6: Export (optional, Obsidian markdown generation)
    stages.append(
        ExportStage(
            obsidian_service=obsidian_service,
            enable_export=enable_export,
            name="export"
        )
    )

    return Pipeline(stages=stages, name=pipeline_name)


__all__ = [
    # Core pipeline classes
    "Pipeline",
    "PipelineStage",
    "StageResult",
    "StageContext",

    # Data models
    "RawDocument",
    "EnrichedDocument",
    "ChunkedDocument",
    "StoredDocument",
    "ExportedDocument",
    "Chunk",

    # Pipeline stages
    "TriageStage",
    "EnrichmentStage",
    "QualityGateStage",
    "ChunkingStage",
    "StorageStage",
    "ExportStage",

    # Factory
    "create_ingestion_pipeline",
]
