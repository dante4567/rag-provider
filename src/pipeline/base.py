"""
Pipeline Architecture - Base Classes and Interfaces

This module defines the contract for pipeline stages in the document ingestion flow.
Each stage takes an input, transforms it, and produces an output.

DESIGN PRINCIPLES:
1. Single Responsibility - Each stage does ONE thing
2. Clear Contracts - Input/output types are explicit via Pydantic
3. Testable - Stages can be tested in isolation
4. Composable - Pipeline can be reconfigured by adding/removing stages
5. Observable - Each stage can log and emit metrics

PIPELINE FLOW:
    Document → Parse → Enrich → QualityGate → Chunk → Store → Export

Each stage can:
- Transform data
- Validate data
- Decide to continue or stop processing
- Emit logs/metrics
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TypeVar, Generic
from pydantic import BaseModel, Field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class StageResult(str, Enum):
    """Result codes from stage processing"""
    CONTINUE = "continue"  # Continue to next stage
    STOP = "stop"          # Stop processing (not an error, e.g., quality gate)
    ERROR = "error"        # Error occurred, stop processing


class StageContext(BaseModel):
    """
    Context passed through the pipeline.

    Contains shared state and metadata that all stages can access.
    """
    doc_id: str
    filename: Optional[str] = None
    request_metadata: Dict[str, Any] = Field(default_factory=dict)

    # Performance tracking
    stage_timings: Dict[str, float] = Field(default_factory=dict)

    # Quality metrics
    quality_scores: Optional[Dict[str, float]] = None

    # Decisions made
    gated: bool = False
    gate_reason: Optional[str] = None

    # Triage metadata (from TriageStage)
    fingerprint: Optional[Any] = None
    triage_category: Optional[str] = None
    triage_confidence: Optional[float] = None
    triage_reasoning: Optional[list] = None
    knowledge_updates: Optional[list] = None

    class Config:
        arbitrary_types_allowed = True


# Type variables for input/output
TInput = TypeVar('TInput', bound=BaseModel)
TOutput = TypeVar('TOutput', bound=BaseModel)


class PipelineStage(ABC, Generic[TInput, TOutput]):
    """
    Abstract base class for pipeline stages.

    Each stage:
    - Takes an input of type TInput
    - Produces an output of type TOutput
    - Has access to shared context
    - Returns a result code indicating whether to continue

    Example:
        class MyStage(PipelineStage[InputModel, OutputModel]):
            async def process(self, input_data, context):
                # Transform input to output
                output = OutputModel(...)
                return StageResult.CONTINUE, output
    """

    def __init__(self, name: Optional[str] = None):
        """
        Initialize stage.

        Args:
            name: Optional custom name for the stage (defaults to class name)
        """
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f"pipeline.{self.name}")

    @abstractmethod
    async def process(
        self,
        input_data: TInput,
        context: StageContext
    ) -> tuple[StageResult, Optional[TOutput]]:
        """
        Process the input and produce output.

        Args:
            input_data: Input data for this stage
            context: Shared pipeline context

        Returns:
            Tuple of (result_code, output_data)
            - If result is CONTINUE, output_data must be provided
            - If result is STOP or ERROR, output_data is optional

        Raises:
            Should not raise exceptions - return StageResult.ERROR instead
        """
        pass

    def should_skip(self, context: StageContext) -> bool:
        """
        Determine if this stage should be skipped.

        Override this to implement conditional stage execution.

        Args:
            context: Pipeline context

        Returns:
            True if stage should be skipped
        """
        return False

    async def on_error(self, error: Exception, context: StageContext) -> None:
        """
        Handle errors that occur during processing.

        Override this to implement custom error handling.

        Args:
            error: The exception that occurred
            context: Pipeline context
        """
        self.logger.error(f"Error in {self.name}: {error}", exc_info=True)


class Pipeline:
    """
    Pipeline orchestrator that executes stages in sequence.

    Example:
        pipeline = Pipeline([
            ParseStage(),
            EnrichmentStage(),
            QualityGateStage(),
            ChunkingStage(),
            StorageStage()
        ])

        result = await pipeline.run(document, context)
    """

    def __init__(self, stages: list[PipelineStage], name: str = "pipeline"):
        """
        Initialize pipeline with stages.

        Args:
            stages: List of pipeline stages to execute in order
            name: Pipeline name for logging (default: "pipeline")
        """
        self.stages = stages
        self.name = name
        self.logger = logging.getLogger(name)

    async def run(
        self,
        initial_input: Any,
        context: StageContext
    ) -> tuple[StageResult, Any]:
        """
        Run the pipeline with initial input.

        Args:
            initial_input: Input to the first stage
            context: Pipeline context

        Returns:
            Tuple of (final_result, final_output)
        """
        current_input = initial_input
        final_result = StageResult.CONTINUE

        for stage in self.stages:
            # Check if stage should be skipped
            if stage.should_skip(context):
                self.logger.info(f"⏭️  Skipping stage: {stage.name}")
                continue

            self.logger.info(f"▶️  Running stage: {stage.name}")

            try:
                import time
                start_time = time.time()

                # Execute stage
                result, output = await stage.process(current_input, context)

                # Track timing
                elapsed = time.time() - start_time
                context.stage_timings[stage.name] = elapsed
                self.logger.info(f"✅ {stage.name} completed in {elapsed:.2f}s")

                # Handle result
                if result == StageResult.STOP:
                    self.logger.info(f"🛑 Pipeline stopped at {stage.name}")
                    final_result = result
                    current_input = output
                    break

                elif result == StageResult.ERROR:
                    self.logger.error(f"❌ Pipeline error at {stage.name}")
                    final_result = result
                    current_input = output
                    break

                elif result == StageResult.CONTINUE:
                    # Continue to next stage
                    current_input = output

            except Exception as e:
                self.logger.error(f"💥 Exception in {stage.name}: {e}", exc_info=True)
                await stage.on_error(e, context)
                final_result = StageResult.ERROR
                break

        return final_result, current_input

    def add_stage(self, stage: PipelineStage, position: Optional[int] = None) -> None:
        """
        Add a stage to the pipeline.

        Args:
            stage: Stage to add
            position: Optional position to insert at (default: append)
        """
        if position is None:
            self.stages.append(stage)
        else:
            self.stages.insert(position, stage)

    def remove_stage(self, stage_name: str) -> None:
        """
        Remove a stage by name.

        Args:
            stage_name: Name of stage to remove
        """
        self.stages = [s for s in self.stages if s.name != stage_name]

    def get_stage(self, stage_name: str) -> Optional[PipelineStage]:
        """
        Get a stage by name.

        Args:
            stage_name: Name of stage to find

        Returns:
            Stage if found, None otherwise
        """
        for stage in self.stages:
            if stage.name == stage_name:
                return stage
        return None
