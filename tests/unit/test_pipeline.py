"""
Unit tests for Pipeline orchestrator

Tests the Pipeline class that runs stages in sequence.
"""

import pytest
from unittest.mock import AsyncMock, Mock
from src.pipeline.base import Pipeline, PipelineStage, StageResult, StageContext


class MockStage(PipelineStage):
    """Mock pipeline stage for testing"""

    def __init__(self, name: str, result: StageResult = StageResult.CONTINUE, should_skip: bool = False):
        super().__init__(name)
        self.result = result
        self._should_skip = should_skip
        self.process_called = False
        self.input_received = None

    async def process(self, input_data, context):
        self.process_called = True
        self.input_received = input_data
        output = {"stage": self.name, "input": input_data}
        return self.result, output

    def should_skip(self, context):
        return self._should_skip


@pytest.mark.asyncio
class TestPipeline:
    """Test suite for Pipeline orchestrator"""

    async def test_pipeline_runs_all_stages_on_continue(self):
        """Test that pipeline runs all stages when each returns CONTINUE"""
        stage1 = MockStage("stage1", StageResult.CONTINUE)
        stage2 = MockStage("stage2", StageResult.CONTINUE)
        stage3 = MockStage("stage3", StageResult.CONTINUE)

        pipeline = Pipeline([stage1, stage2, stage3])
        context = StageContext(doc_id="test_doc", filename="test.txt")

        result, output = await pipeline.run("initial_input", context)

        assert result == StageResult.CONTINUE
        assert stage1.process_called
        assert stage2.process_called
        assert stage3.process_called
        assert output["stage"] == "stage3"  # Final stage output

    async def test_pipeline_stops_on_stop_result(self):
        """Test that pipeline stops when stage returns STOP"""
        stage1 = MockStage("stage1", StageResult.CONTINUE)
        stage2 = MockStage("stage2", StageResult.STOP)
        stage3 = MockStage("stage3", StageResult.CONTINUE)

        pipeline = Pipeline([stage1, stage2, stage3])
        context = StageContext(doc_id="test_doc", filename="test.txt")

        result, output = await pipeline.run("initial_input", context)

        assert result == StageResult.STOP
        assert stage1.process_called
        assert stage2.process_called
        assert not stage3.process_called  # Should not reach stage3

    async def test_pipeline_stops_on_error(self):
        """Test that pipeline stops when stage returns ERROR"""
        stage1 = MockStage("stage1", StageResult.CONTINUE)
        stage2 = MockStage("stage2", StageResult.ERROR)
        stage3 = MockStage("stage3", StageResult.CONTINUE)

        pipeline = Pipeline([stage1, stage2, stage3])
        context = StageContext(doc_id="test_doc", filename="test.txt")

        result, output = await pipeline.run("initial_input", context)

        assert result == StageResult.ERROR
        assert stage1.process_called
        assert stage2.process_called
        assert not stage3.process_called

    async def test_pipeline_skips_stages_with_should_skip(self):
        """Test that pipeline skips stages when should_skip() returns True"""
        stage1 = MockStage("stage1", StageResult.CONTINUE, should_skip=False)
        stage2 = MockStage("stage2", StageResult.CONTINUE, should_skip=True)
        stage3 = MockStage("stage3", StageResult.CONTINUE, should_skip=False)

        pipeline = Pipeline([stage1, stage2, stage3])
        context = StageContext(doc_id="test_doc", filename="test.txt")

        result, output = await pipeline.run("initial_input", context)

        assert result == StageResult.CONTINUE
        assert stage1.process_called
        assert not stage2.process_called  # Skipped
        assert stage3.process_called

    async def test_pipeline_passes_data_between_stages(self):
        """Test that output from one stage becomes input to next stage"""
        stage1 = MockStage("stage1", StageResult.CONTINUE)
        stage2 = MockStage("stage2", StageResult.CONTINUE)

        pipeline = Pipeline([stage1, stage2])
        context = StageContext(doc_id="test_doc", filename="test.txt")

        await pipeline.run("initial_input", context)

        # Stage 1 receives initial input
        assert stage1.input_received == "initial_input"

        # Stage 2 receives output from stage 1
        assert stage2.input_received["stage"] == "stage1"
        assert stage2.input_received["input"] == "initial_input"

    async def test_pipeline_with_empty_stages(self):
        """Test pipeline with no stages"""
        pipeline = Pipeline([])
        context = StageContext(doc_id="test_doc", filename="test.txt")

        result, output = await pipeline.run("initial_input", context)

        assert result == StageResult.CONTINUE
        assert output == "initial_input"  # Unchanged

    async def test_pipeline_with_single_stage(self):
        """Test pipeline with single stage"""
        stage = MockStage("stage1", StageResult.CONTINUE)
        pipeline = Pipeline([stage])
        context = StageContext(doc_id="test_doc", filename="test.txt")

        result, output = await pipeline.run("initial_input", context)

        assert result == StageResult.CONTINUE
        assert stage.process_called
        assert output["stage"] == "stage1"

    async def test_pipeline_name(self):
        """Test that pipeline name is set correctly"""
        pipeline = Pipeline([], name="test_pipeline")
        assert pipeline.name == "test_pipeline"

        pipeline2 = Pipeline([])
        assert "pipeline" in pipeline2.name.lower()


@pytest.mark.asyncio
class TestStageContext:
    """Test suite for StageContext"""

    def test_context_initialization(self):
        """Test StageContext initialization with required fields"""
        context = StageContext(doc_id="doc_123", filename="test.pdf")

        assert context.doc_id == "doc_123"
        assert context.filename == "test.pdf"
        assert context.quality_scores is None
        assert context.gated is False
        assert context.gate_reason is None

    def test_context_with_optional_fields(self):
        """Test StageContext with optional fields"""
        quality_scores = {"quality_score": 0.85, "novelty_score": 0.72}

        context = StageContext(
            doc_id="doc_123",
            filename="test.pdf",
            quality_scores=quality_scores,
            gated=True,
            gate_reason="Low quality"
        )

        assert context.quality_scores == quality_scores
        assert context.gated is True
        assert context.gate_reason == "Low quality"

    def test_context_is_mutable(self):
        """Test that context can be modified by stages"""
        context = StageContext(doc_id="doc_123", filename="test.pdf")

        # Stage can update context
        context.quality_scores = {"quality_score": 0.9}
        context.gated = True
        context.gate_reason = "Test gate"

        assert context.quality_scores["quality_score"] == 0.9
        assert context.gated is True
        assert context.gate_reason == "Test gate"


@pytest.mark.asyncio
class TestStageResult:
    """Test suite for StageResult enum"""

    def test_stage_result_values(self):
        """Test that StageResult has expected values"""
        assert StageResult.CONTINUE.value == "continue"
        assert StageResult.STOP.value == "stop"
        assert StageResult.ERROR.value == "error"

    def test_stage_result_comparison(self):
        """Test StageResult comparison"""
        assert StageResult.CONTINUE == StageResult.CONTINUE
        assert StageResult.CONTINUE != StageResult.STOP
        assert StageResult.STOP != StageResult.ERROR
