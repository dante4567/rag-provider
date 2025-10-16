"""
Export Stage - Export document to Obsidian

This stage creates Obsidian markdown files with metadata and entity references.

INPUT: StoredDocument
OUTPUT: ExportedDocument
"""

from typing import Optional
from src.pipeline.base import PipelineStage, StageResult, StageContext
from src.pipeline.models import StoredDocument, ExportedDocument
from src.services.obsidian_service import ObsidianService
from src.models.schemas import DocumentType
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ExportStage(PipelineStage[StoredDocument, ExportedDocument]):
    """
    Export stage - Creates Obsidian markdown files.

    This stage:
    1. Converts enriched metadata to ObsidianMetadata
    2. Generates markdown file with frontmatter
    3. Creates entity reference files
    4. Generates WikiLinks
    5. Exports attachments (if any)

    Dependencies:
    - ObsidianService
    """

    def __init__(
        self,
        obsidian_service: ObsidianService,
        enable_export: bool = True,
        name: Optional[str] = None
    ):
        """
        Initialize export stage.

        Args:
            obsidian_service: Service for Obsidian export
            enable_export: Whether export is enabled
            name: Optional custom stage name
        """
        super().__init__(name)
        self.obsidian_service = obsidian_service
        self.enable_export = enable_export

    async def process(
        self,
        input_data: StoredDocument,
        context: StageContext
    ) -> tuple[StageResult, Optional[ExportedDocument]]:
        """
        Export document to Obsidian.

        Args:
            input_data: Stored document
            context: Pipeline context

        Returns:
            (CONTINUE, ExportedDocument) on success
            (ERROR, None) on failure
        """
        try:
            if not self.enable_export:
                self.logger.info("Export disabled, skipping")
                return StageResult.CONTINUE, ExportedDocument(
                    doc_id=input_data.doc_id,
                    metadata=input_data.enriched_metadata
                )

            self.logger.info("Exporting to Obsidian...")

            metadata = input_data.enriched_metadata

            # Convert document_type string to enum if needed
            doc_type_str = metadata.get("document_type", "text")
            if isinstance(doc_type_str, str) and doc_type_str.startswith("DocumentType."):
                doc_type_str = doc_type_str.replace("DocumentType.", "")
            try:
                doc_type_enum = DocumentType[doc_type_str]
            except (KeyError, TypeError):
                doc_type_enum = DocumentType.text

            # Get title from metadata
            title = metadata.get("title", context.filename or "Untitled")

            # Get document's original creation date (email send date, etc.)
            doc_created_at = datetime.now()  # Default to now
            created_date_str = metadata.get("created_date") or metadata.get("created_at")
            if created_date_str:
                try:
                    if isinstance(created_date_str, str):
                        # Try parsing ISO date
                        doc_created_at = datetime.fromisoformat(created_date_str.replace('Z', '+00:00'))
                    elif isinstance(created_date_str, datetime):
                        doc_created_at = created_date_str
                except (ValueError, AttributeError):
                    self.logger.warning(f"Could not parse created_date: {created_date_str}, using now")

            # Export to Obsidian - ObsidianService handles all the parsing internally
            obsidian_path = self.obsidian_service.export_document(
                title=title,
                content="",  # Content already in ChromaDB
                metadata=metadata,  # Pass flat enriched_metadata dict
                document_type=doc_type_enum,
                created_at=doc_created_at,  # Use document's original date
                source=context.filename or "pipeline"
            )

            self.logger.info(f"✅ Exported to: {obsidian_path}")

            # Count entities for response
            entities_dict = metadata.get("entities", {})
            if isinstance(entities_dict, dict):
                people_count = len(entities_dict.get("people", []))
                orgs_count = len(entities_dict.get("organizations", []))
                places_count = len(entities_dict.get("places", []))
                tech_count = len(entities_dict.get("technologies", []))
                entity_refs_created = people_count + orgs_count + places_count + tech_count
            else:
                entity_refs_created = 0

            # Create exported document
            # Add chunk_count to metadata for response
            response_metadata = {
                **input_data.enriched_metadata,
                "chunks": input_data.chunk_count
            }

            exported_doc = ExportedDocument(
                doc_id=input_data.doc_id,
                obsidian_path=str(obsidian_path),
                entity_refs_created=entity_refs_created,
                metadata=response_metadata
            )

            return StageResult.CONTINUE, exported_doc

        except Exception as e:
            self.logger.error(f"Export failed: {e}", exc_info=True)
            # Export failure is not critical - document is already stored
            return StageResult.CONTINUE, ExportedDocument(
                doc_id=input_data.doc_id,
                metadata=input_data.enriched_metadata
            )

    def should_skip(self, context: StageContext) -> bool:
        """Skip export if disabled"""
        return not self.enable_export
