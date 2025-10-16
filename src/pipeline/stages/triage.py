"""
Triage Stage - Fast document pre-processing and filtering

This stage runs BEFORE enrichment to:
1. Detect duplicates (exact, fuzzy, metadata-based)
2. Filter junk/spam documents
3. Categorize documents for routing
4. Resolve entity aliases using personal KB
5. Trigger knowledge base updates

INPUT: RawDocument
OUTPUT: RawDocument (with triage metadata added)
RESULT: STOP if duplicate/junk, CONTINUE if should process
"""

from typing import Optional
from src.pipeline.base import PipelineStage, StageResult, StageContext
from src.pipeline.models import RawDocument
from src.services.smart_triage_service import SmartTriageService, DocumentFingerprint, TriageDecision
import logging

logger = logging.getLogger(__name__)


class TriageStage(PipelineStage[RawDocument, RawDocument]):
    """
    Triage stage - Fast document filtering before expensive enrichment.

    This stage:
    1. Generates document fingerprints (content hash, fuzzy hash, metadata hash)
    2. Checks for duplicates in vector DB
    3. Detects junk/spam patterns
    4. Categorizes documents (personal/actionable/reference/archival)
    5. Returns STOP for duplicates/junk (saves enrichment cost)
    6. Returns CONTINUE for valuable documents

    Dependencies:
    - SmartTriageService
    """

    def __init__(
        self,
        triage_service: SmartTriageService,
        enable_duplicate_detection: bool = True,
        enable_junk_filtering: bool = True,
        name: Optional[str] = None
    ):
        """
        Initialize triage stage.

        Args:
            triage_service: Service for document triage
            enable_duplicate_detection: Skip duplicates (default: True)
            enable_junk_filtering: Skip junk/spam (default: True)
            name: Optional custom stage name
        """
        super().__init__(name)
        self.triage_service = triage_service
        self.enable_duplicate_detection = enable_duplicate_detection
        self.enable_junk_filtering = enable_junk_filtering

    async def process(
        self,
        input_data: RawDocument,
        context: StageContext
    ) -> tuple[StageResult, Optional[RawDocument]]:
        """
        Triage document and decide whether to continue processing.

        Args:
            input_data: Raw document
            context: Pipeline context

        Returns:
            (CONTINUE, doc) if should process
            (STOP, doc) if duplicate/junk
        """
        try:
            self.logger.info("🔍 Triaging document...")

            # Generate fingerprint for duplicate detection
            metadata_dict = input_data.metadata or {}
            entities_dict = metadata_dict.get("entities", {})

            fingerprint = self.triage_service.generate_fingerprint(
                content=input_data.content,
                metadata=metadata_dict,
                entities=entities_dict
            )

            # Store fingerprint in context for later stages
            context.fingerprint = fingerprint

            # Perform triage decision
            triage_decision = self.triage_service.triage_document(
                content=input_data.content,
                metadata=metadata_dict,
                entities=entities_dict,
                fingerprint=fingerprint
            )

            # Store triage decision in context
            context.triage_category = triage_decision.category
            context.triage_confidence = triage_decision.confidence
            context.triage_reasoning = triage_decision.reasoning
            context.knowledge_updates = triage_decision.knowledge_updates

            # Add triage metadata to document
            if not input_data.metadata:
                input_data.metadata = {}
            input_data.metadata["triage_category"] = triage_decision.category
            input_data.metadata["triage_confidence"] = triage_decision.confidence
            input_data.metadata["triage_reasoning"] = triage_decision.reasoning

            # Log triage summary
            self.logger.info(
                f"📋 Triage: {triage_decision.category} "
                f"(confidence: {triage_decision.confidence:.0%})"
            )
            for reason in triage_decision.reasoning:
                self.logger.info(f"  • {reason}")

            # Check for duplicate (highest priority - save enrichment cost)
            if self.enable_duplicate_detection and triage_decision.category == "duplicate":
                self.logger.warning(
                    f"⛔ DUPLICATE detected: {triage_decision.reasoning[0]}"
                )
                context.gated = True
                context.gate_reason = "duplicate"
                return StageResult.STOP, input_data

            # Check for junk/spam
            if self.enable_junk_filtering and triage_decision.category == "junk":
                self.logger.warning(
                    f"⛔ JUNK detected: {', '.join(triage_decision.reasoning)}"
                )
                context.gated = True
                context.gate_reason = "junk"
                return StageResult.STOP, input_data

            # Log knowledge base updates if any
            if triage_decision.knowledge_updates:
                self.logger.info(f"🔄 Knowledge base updates suggested:")
                for update in triage_decision.knowledge_updates:
                    self.logger.info(f"  • {update.get('action', 'Update')}")

            # Log suggested actions
            if triage_decision.actions_suggested:
                self.logger.info(f"📝 Actions suggested:")
                for action in triage_decision.actions_suggested:
                    self.logger.info(f"  • {action}")

            self.logger.info(
                f"✅ Triage passed: {triage_decision.category} "
                f"(proceeding to enrichment)"
            )
            return StageResult.CONTINUE, input_data

        except Exception as e:
            self.logger.error(f"Triage error: {e}", exc_info=True)
            # On error, allow document through (fail open)
            self.logger.warning("⚠️  Triage failed, allowing document through")
            return StageResult.CONTINUE, input_data

    def should_skip(self, context: StageContext) -> bool:
        """Skip triage if both duplicate detection and junk filtering disabled"""
        return not (self.enable_duplicate_detection or self.enable_junk_filtering)
