"""
Quality Gate Stage - Filter documents based on quality scores

This stage evaluates document quality and decides whether to continue processing.
Documents that don't meet quality thresholds are gated (not indexed).

INPUT: EnrichedDocument
OUTPUT: EnrichedDocument (with quality scores added)
RESULT: STOP if gated, CONTINUE if passes
"""

from typing import Optional
from src.pipeline.base import PipelineStage, StageResult, StageContext
from src.pipeline.models import EnrichedDocument
from src.services.quality_scoring_service import QualityScoringService
import logging

logger = logging.getLogger(__name__)


class QualityGateStage(PipelineStage[EnrichedDocument, EnrichedDocument]):
    """
    Quality gate stage - Evaluates and filters documents by quality.

    This stage:
    1. Calculates quality scores (quality, novelty, actionability)
    2. Determines if document should be indexed
    3. Returns STOP if gated (document not indexed)
    4. Returns CONTINUE if passed (document continues to storage)

    Dependencies:
    - QualityScoringService
    """

    def __init__(
        self,
        quality_service: QualityScoringService,
        enable_gating: bool = True,
        name: Optional[str] = None
    ):
        """
        Initialize quality gate stage.

        Args:
            quality_service: Service for quality scoring
            enable_gating: Whether to actually gate documents (False = score only)
            name: Optional custom stage name
        """
        super().__init__(name)
        self.quality_service = quality_service
        self.enable_gating = enable_gating

    async def process(
        self,
        input_data: EnrichedDocument,
        context: StageContext
    ) -> tuple[StageResult, Optional[EnrichedDocument]]:
        """
        Evaluate document quality and decide whether to continue.

        Args:
            input_data: Enriched document
            context: Pipeline context

        Returns:
            (CONTINUE, doc_with_scores) if passes quality gate
            (STOP, doc_with_scores) if gated
        """
        try:
            self.logger.info("Evaluating document quality...")

            # Calculate quality scores
            quality_scores = self.quality_service.score_document(
                content=input_data.content,
                document_type=input_data.document_type,
                metadata=input_data.enriched_metadata,
                existing_docs_count=0,  # TODO: Get from vector service
                watchlist_people=None,
                watchlist_projects=None,
                watchlist_topics=None
            )

            # Update document with quality scores
            input_data.quality_score = quality_scores["quality_score"]
            input_data.novelty_score = quality_scores["novelty_score"]
            input_data.actionability_score = quality_scores["actionability_score"]
            input_data.signalness = quality_scores["signalness"]
            input_data.do_index = quality_scores["do_index"]
            input_data.gate_reason = quality_scores.get("gate_reason")

            # Update context
            context.quality_scores = quality_scores
            context.gated = not quality_scores["do_index"]
            context.gate_reason = quality_scores.get("gate_reason")

            # Log scores
            self.logger.info(
                f"Quality: {quality_scores['quality_score']:.2f}, "
                f"Novelty: {quality_scores['novelty_score']:.2f}, "
                f"Actionability: {quality_scores['actionability_score']:.2f}, "
                f"Signal: {quality_scores['signalness']:.2f}"
            )

            # Check if document passes gate
            if self.enable_gating and not quality_scores["do_index"]:
                self.logger.warning(
                    f"⛔ Document GATED: {quality_scores.get('gate_reason', 'Failed quality threshold')}"
                )
                return StageResult.STOP, input_data

            self.logger.info("✅ Document passed quality gate")
            return StageResult.CONTINUE, input_data

        except Exception as e:
            self.logger.error(f"Quality gate error: {e}", exc_info=True)
            # On error, allow document through (fail open)
            return StageResult.CONTINUE, input_data

    def should_skip(self, context: StageContext) -> bool:
        """Skip quality gate if gating is disabled"""
        return not self.enable_gating
