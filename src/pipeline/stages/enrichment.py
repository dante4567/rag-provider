"""
Enrichment Stage - Extract metadata from documents using LLM

This stage takes raw document text and enriches it with:
- Title, summary, tags
- Entity extraction (people, organizations, locations, technologies)
- Topic classification using controlled vocabulary
- Quality scores and triage information

INPUT: RawDocument (raw text + basic metadata)
OUTPUT: EnrichedDocument (text + extracted metadata + entities)
"""

from typing import Optional
from src.pipeline.base import PipelineStage, StageResult, StageContext
from src.pipeline.models import RawDocument, EnrichedDocument
from src.services.enrichment_service import EnrichmentService
from src.models.schemas import DocumentType
import logging

logger = logging.getLogger(__name__)


class EnrichmentStage(PipelineStage[RawDocument, EnrichedDocument]):
    """
    Enrichment stage - Uses LLM to extract metadata from documents.

    This stage:
    1. Calls enrichment service (LiteLLM + Instructor)
    2. Extracts entities, tags, summary, etc.
    3. Validates output using Pydantic models
    4. Returns structured EnrichedDocument

    Dependencies:
    - EnrichmentService (LLM-based extraction)
    - VocabularyService (controlled vocabulary)
    """

    def __init__(
        self,
        enrichment_service: EnrichmentService,
        use_iteration: bool = False,
        name: Optional[str] = None
    ):
        """
        Initialize enrichment stage.

        Args:
            enrichment_service: Service for LLM-based enrichment
            use_iteration: Whether to use self-improvement loop
            name: Optional custom stage name
        """
        super().__init__(name)
        self.enrichment_service = enrichment_service
        self.use_iteration = use_iteration

    async def process(
        self,
        input_data: RawDocument,
        context: StageContext
    ) -> tuple[StageResult, Optional[EnrichedDocument]]:
        """
        Enrich document with metadata extraction.

        Args:
            input_data: Raw document
            context: Pipeline context

        Returns:
            (CONTINUE, EnrichedDocument) on success
            (ERROR, None) on failure
        """
        try:
            self.logger.info(f"Enriching document: {input_data.filename or context.doc_id}")

            # Call enrichment service
            if self.use_iteration:
                self.logger.info("Using self-improvement loop (max 2 iterations)")
                enriched_metadata = await self.enrichment_service.enrich_with_iteration(
                    content=input_data.content,
                    filename=input_data.filename or context.doc_id,
                    document_type=input_data.document_type
                )
            else:
                enriched_metadata = await self.enrichment_service.enrich_document(
                    content=input_data.content,
                    filename=input_data.filename or context.doc_id,
                    document_type=input_data.document_type
                )

            # Extract entity lists from enriched metadata
            enriched_lists = self.enrichment_service.extract_enriched_lists(enriched_metadata)

            # Extract specific lists
            people_list = [
                p.get("name") if isinstance(p, dict) else p
                for p in enriched_lists.get("people", [])
            ]
            orgs_list = enriched_lists.get("organizations", [])
            locs_list = enriched_lists.get("locations", [])
            tech_list = enriched_lists.get("technologies", [])
            tags_list = enriched_lists.get("tags", [])
            key_points_list = enriched_lists.get("key_points", [])
            dates_list = enriched_lists.get("dates", [])

            # Log extraction results
            self.logger.info(
                f"Extracted: {len(people_list)} people, {len(orgs_list)} orgs, "
                f"{len(locs_list)} places, {len(tech_list)} tech"
            )

            # Create enriched document
            enriched_doc = EnrichedDocument(
                content=input_data.content,
                filename=input_data.filename,
                document_type=input_data.document_type,
                enriched_metadata=enriched_metadata,
                people=people_list,
                organizations=orgs_list,
                locations=locs_list,
                technologies=tech_list,
                tags=tags_list,
                key_points=key_points_list,
                dates=dates_list,
                # Quality scores will be added by QualityGateStage
            )

            return StageResult.CONTINUE, enriched_doc

        except Exception as e:
            self.logger.error(f"Enrichment failed: {e}", exc_info=True)
            return StageResult.ERROR, None

    async def on_error(self, error: Exception, context: StageContext) -> None:
        """Log enrichment errors"""
        self.logger.error(
            f"Enrichment error for {context.filename or context.doc_id}: {error}"
        )
