"""
Storage Stage - Store chunks in vector database (ChromaDB)

This stage stores document chunks in ChromaDB with embeddings.
Handles metadata flattening using ChromaDBAdapter.

INPUT: ChunkedDocument
OUTPUT: StoredDocument
"""

from typing import Optional
from src.pipeline.base import PipelineStage, StageResult, StageContext
from src.pipeline.models import ChunkedDocument, StoredDocument
from src.services.vector_service import VectorService
from src.adapters.chroma_adapter import ChromaDBAdapter
import logging

logger = logging.getLogger(__name__)


class StorageStage(PipelineStage[ChunkedDocument, StoredDocument]):
    """
    Storage stage - Stores chunks in vector database.

    This stage:
    1. Flattens metadata for ChromaDB using adapter
    2. Creates chunk IDs
    3. Stores chunks with embeddings in ChromaDB
    4. Returns StoredDocument with chunk IDs

    Dependencies:
    - VectorService (ChromaDB operations)
    - ChromaDBAdapter (format conversions)
    """

    def __init__(
        self,
        vector_service: VectorService,
        name: Optional[str] = None
    ):
        """
        Initialize storage stage.

        Args:
            vector_service: Service for vector database operations
            name: Optional custom stage name
        """
        super().__init__(name)
        self.vector_service = vector_service

    async def process(
        self,
        input_data: ChunkedDocument,
        context: StageContext
    ) -> tuple[StageResult, Optional[StoredDocument]]:
        """
        Store chunks in vector database.

        Args:
            input_data: Chunked document
            context: Pipeline context

        Returns:
            (CONTINUE, StoredDocument) on success
            (ERROR, None) on failure
        """
        try:
            self.logger.info(f"Storing {len(input_data.chunks)} chunks in ChromaDB...")

            # Sanitize enriched metadata for ChromaDB
            sanitized_enriched = ChromaDBAdapter.sanitize_for_chromadb(
                input_data.enriched_metadata
            )

            # Flatten entity lists using adapter
            entity_metadata = ChromaDBAdapter.flatten_entities_for_storage(
                people=input_data.people,
                organizations=input_data.organizations,
                locations=input_data.locations,
                technologies=input_data.technologies
            )

            # Create base metadata for all chunks
            base_metadata = {
                **sanitized_enriched,
                **entity_metadata,
                "doc_id": input_data.doc_id,
                "filename": str(input_data.filename or f"document_{input_data.doc_id}"),
                "chunks": len(input_data.chunks),
            }

            # Prepare chunks for storage
            chunk_ids = []
            chunk_metadatas = []
            chunk_contents = []

            for chunk in input_data.chunks:
                chunk_id = f"{input_data.doc_id}_chunk_{chunk.chunk_index}"

                # Create chunk-specific metadata
                chunk_metadata = {
                    **base_metadata,
                    "chunk_index": chunk.chunk_index,
                    "chunk_id": chunk_id,
                    "chunk_type": chunk.chunk_type,
                    "section_title": chunk.section_title or '',
                    "parent_sections": ','.join(chunk.parent_sections),
                    "estimated_tokens": chunk.estimated_tokens
                }

                chunk_ids.append(chunk_id)
                chunk_metadatas.append(chunk_metadata)
                chunk_contents.append(chunk.content)

            # Store in ChromaDB
            self.vector_service.collection.add(
                ids=chunk_ids,
                documents=chunk_contents,
                metadatas=chunk_metadatas
            )

            self.logger.info(f"✅ Stored {len(chunk_ids)} chunks")

            # Create stored document
            stored_doc = StoredDocument(
                doc_id=input_data.doc_id,
                chunk_ids=chunk_ids,
                chunk_count=len(chunk_ids),
                original_content=input_data.original_content,  # Pass through for Obsidian export
                enriched_metadata=input_data.enriched_metadata
            )

            return StageResult.CONTINUE, stored_doc

        except Exception as e:
            self.logger.error(f"Storage failed: {e}", exc_info=True)
            return StageResult.ERROR, None
