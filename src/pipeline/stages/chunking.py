"""
Chunking Stage - Split documents into semantic chunks

This stage splits documents into chunks for vector storage.
Uses structure-aware chunking to preserve semantic boundaries.

INPUT: EnrichedDocument
OUTPUT: ChunkedDocument
"""

from typing import Optional
from src.pipeline.base import PipelineStage, StageResult, StageContext
from src.pipeline.models import EnrichedDocument, ChunkedDocument, Chunk
from src.services.chunking_service import ChunkingService
from src.models.schemas import DocumentType
import logging

logger = logging.getLogger(__name__)


class ChunkingStage(PipelineStage[EnrichedDocument, ChunkedDocument]):
    """
    Chunking stage - Splits documents into semantic chunks.

    This stage:
    1. Splits document using structure-aware chunking
    2. Preserves section boundaries (headings, tables, code)
    3. Respects RAG:IGNORE blocks
    4. Creates Chunk objects with metadata

    Dependencies:
    - ChunkingService
    """

    def __init__(
        self,
        chunking_service: ChunkingService,
        name: Optional[str] = None
    ):
        """
        Initialize chunking stage.

        Args:
            chunking_service: Service for document chunking
            name: Optional custom stage name
        """
        super().__init__(name)
        self.chunking_service = chunking_service

    async def process(
        self,
        input_data: EnrichedDocument,
        context: StageContext
    ) -> tuple[StageResult, Optional[ChunkedDocument]]:
        """
        Split document into chunks.

        Args:
            input_data: Enriched document
            context: Pipeline context

        Returns:
            (CONTINUE, ChunkedDocument) on success
            (ERROR, None) on failure
        """
        try:
            self.logger.info("Chunking document...")

            # Determine chunking strategy based on document type
            if input_data.document_type == DocumentType.llm_chat:
                self.logger.info("Using turn-based chunking for chat log")
                chunk_dicts = self.chunking_service.chunk_chat_log(
                    input_data.content,
                    input_data.enriched_metadata
                )
            else:
                self.logger.info("Using structure-aware chunking")
                chunk_dicts = self.chunking_service.chunk_text(
                    input_data.content,
                    preserve_structure=True
                )

            # Convert to Chunk models
            chunks = []
            for i, chunk_dict in enumerate(chunk_dicts):
                chunk_meta = chunk_dict.get('metadata', {})

                # Extract parent sections
                parent_secs = chunk_meta.get('parent_sections', [])
                if parent_secs and isinstance(parent_secs[0], dict):
                    # Convert dict format to strings
                    parent_secs_list = [p.get('title', str(p)) for p in parent_secs]
                else:
                    parent_secs_list = [str(p) for p in parent_secs]

                chunk = Chunk(
                    content=chunk_dict['content'],
                    chunk_index=i,
                    chunk_type=chunk_meta.get('chunk_type', 'paragraph'),
                    section_title=chunk_meta.get('section_title'),
                    parent_sections=parent_secs_list,
                    estimated_tokens=chunk_dict.get('estimated_tokens', len(chunk_dict['content']) // 4)
                )
                chunks.append(chunk)

            self.logger.info(f"Created {len(chunks)} chunks")

            # Create chunked document
            chunked_doc = ChunkedDocument(
                doc_id=context.doc_id,
                chunks=chunks,
                enriched_metadata=input_data.enriched_metadata,
                people=input_data.people,
                organizations=input_data.organizations,
                locations=input_data.locations,
                technologies=input_data.technologies,
                tags=input_data.tags,
                dates=input_data.dates,
                filename=input_data.filename,
                document_type=input_data.document_type
            )

            return StageResult.CONTINUE, chunked_doc

        except Exception as e:
            self.logger.error(f"Chunking failed: {e}", exc_info=True)
            return StageResult.ERROR, None
