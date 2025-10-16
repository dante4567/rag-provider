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
from src.models.schemas import ObsidianMetadata, Keywords, Entities, DocumentType, ComplexityLevel
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

            # Extract lists for ObsidianMetadata
            tags_list = metadata.get("tags", [])
            if isinstance(tags_list, str):
                tags_list = [t.strip() for t in tags_list.split(',') if t.strip()]

            key_points = metadata.get("key_points", [])
            if isinstance(key_points, str):
                key_points = [k.strip() for k in key_points.split(',') if k.strip()]

            people_list = metadata.get("people", [])
            if isinstance(people_list, str):
                people_list = [p.strip() for p in people_list.split(',') if p.strip()]

            orgs_list = metadata.get("organizations", [])
            if isinstance(orgs_list, str):
                orgs_list = [o.strip() for o in orgs_list.split(',') if o.strip()]

            locs_list = metadata.get("locations", [])
            if isinstance(locs_list, str):
                locs_list = [l.strip() for l in locs_list.split(',') if l.strip()]

            tech_list = metadata.get("technologies", [])
            if isinstance(tech_list, str):
                tech_list = [t.strip() for t in tech_list.split(',') if t.strip()]

            dates_list = metadata.get("dates", [])
            if isinstance(dates_list, str):
                dates_list = [d.strip() for d in dates_list.split(',') if d.strip()]

            # Extract summary
            summary_value = metadata.get("summary", "")
            if isinstance(summary_value, dict):
                summary_str = summary_value.get("tl_dr", "") or summary_value.get("text", "") or str(summary_value)
            else:
                summary_str = str(summary_value) if summary_value else ""

            # Convert document_type string to enum
            doc_type_str = metadata.get("document_type", "text")
            if isinstance(doc_type_str, str) and doc_type_str.startswith("DocumentType."):
                doc_type_str = doc_type_str.replace("DocumentType.", "")
            try:
                doc_type_enum = DocumentType[doc_type_str]
            except (KeyError, TypeError):
                doc_type_enum = DocumentType.text

            # Create ObsidianMetadata
            obsidian_metadata = ObsidianMetadata(
                title=metadata.get("title", "Untitled"),
                keywords=Keywords(
                    primary=tags_list[:3],
                    secondary=tags_list[3:] if len(tags_list) > 3 else []
                ),
                tags=[f"#{tag}" if not tag.startswith("#") else tag for tag in tags_list],
                summary=summary_str,
                abstract=summary_str,
                key_points=key_points,
                entities=Entities(
                    people=people_list,
                    organizations=orgs_list,
                    locations=locs_list,
                    technologies=tech_list
                ),
                reading_time=f"{metadata.get('estimated_reading_time_min', 1)} min",
                complexity=ComplexityLevel[metadata.get("complexity", "intermediate")],
                links=[],
                document_type=doc_type_enum,
                source=context.filename or "",
                created_at=datetime.now(),
                dates=dates_list,
                dates_detailed=metadata.get("dates_detailed", [])
            )

            # Export to Obsidian
            obsidian_path = self.obsidian_service.export_document(
                doc_id=input_data.doc_id,
                content="",  # Content already in ChromaDB
                metadata=obsidian_metadata,
                enriched_metadata=metadata
            )

            self.logger.info(f"✅ Exported to: {obsidian_path}")

            # Create exported document
            # Add chunk_count to metadata for response
            response_metadata = {
                **input_data.enriched_metadata,
                "chunks": input_data.chunk_count
            }

            exported_doc = ExportedDocument(
                doc_id=input_data.doc_id,
                obsidian_path=obsidian_path,
                entity_refs_created=len(people_list) + len(orgs_list) + len(locs_list) + len(tech_list),
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
