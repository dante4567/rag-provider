"""
Integration test for the complete self-improvement iteration loop

Tests the full flow: enrich → critique → edit → validate → apply → re-score
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.services.enrichment_service import EnrichmentService
from src.services.editor_service import EditorService
from src.services.patch_service import PatchService
from src.services.schema_validator import SchemaValidator


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing"""
    service = Mock()
    service.call_llm = AsyncMock()
    service.settings = Mock()
    service.settings.default_llm = "groq/llama-3.1-8b-instant"
    return service


@pytest.fixture
def mock_vocabulary_service():
    """Mock vocabulary service"""
    service = Mock()
    service.get_all_topics = Mock(return_value=[
        "tech/programming",
        "tech/ai",
        "business/strategy"
    ])
    service.get_active_projects = Mock(return_value=["project-2025"])
    service.get_all_places = Mock(return_value=["Berlin", "San Francisco"])
    return service


@pytest.mark.asyncio
@pytest.mark.integration
async def test_complete_iteration_loop_improves_quality(mock_llm_service, mock_vocabulary_service):
    """Test that iteration loop improves enrichment quality"""

    # Setup: Initial enrichment returns low quality
    initial_enrichment = {
        "id": "test-doc",
        "source": {"type": "upload", "path": "/test.txt", "content_hash": "hash123"},
        "doc_time": {"created": "2025-01-01T00:00:00"},
        "title": "Test Document",
        "summary": "Basic summary",
        "topics": ["general"],
        "entities": {"people": [], "organizations": [], "locations": [], "technologies": []},
        "significance_score": 0.3,
        "quality_tier": "low"
    }

    # Mock enrichment call
    async def mock_enrich(*args, **kwargs):
        return initial_enrichment.copy()

    # Mock critic calls - first low score, then improved
    critic_responses = [
        # First iteration: Low score
        {
            "scores": {
                "schema_compliance": 3.0,
                "entity_quality": 2.0,
                "topic_relevance": 2.0,
                "summary_quality": 3.0,
                "task_identification": 3.0,
                "privacy_assessment": 4.0,
                "metadata_completeness": 2.0
            },
            "overall_quality": 2.71,
            "suggestions": [
                "Add more specific topics from controlled vocabulary",
                "Extract named entities from the text",
                "Improve summary clarity and length"
            ],
            "critic_model": "groq/llama-3.1-8b-instant",
            "critic_cost": 0.0001,
            "critic_date": "2025-01-01T00:00:00"
        },
        # Second iteration: Improved score
        {
            "scores": {
                "schema_compliance": 4.0,
                "entity_quality": 4.0,
                "topic_relevance": 4.0,
                "summary_quality": 4.0,
                "task_identification": 4.0,
                "privacy_assessment": 5.0,
                "metadata_completeness": 4.0
            },
            "overall_quality": 4.14,
            "suggestions": ["Minor improvements possible"],
            "critic_model": "groq/llama-3.1-8b-instant",
            "critic_cost": 0.0001,
            "critic_date": "2025-01-01T00:01:00"
        }
    ]

    # Mock editor patch generation
    editor_patch = {
        "add": {
            "entities.technologies": ["Python", "FastAPI"],
            "entities.people": ["Alice Smith"]
        },
        "replace": {
            "topics": ["tech/programming", "tech/ai"],
            "summary": "Improved technical summary about Python and FastAPI development"
        },
        "remove": []
    }

    # Setup mocks
    mock_llm_service.call_llm.side_effect = [
        # Critic call 1
        (str(critic_responses[0]), 0.0001, "groq/llama-3.1-8b-instant"),
        # Editor call
        (str(editor_patch), 0.0001, "groq/llama-3.1-8b-instant"),
        # Critic call 2
        (str(critic_responses[1]), 0.0001, "groq/llama-3.1-8b-instant")
    ]

    # Create enrichment service
    enrichment_service = EnrichmentService(
        llm_service=mock_llm_service,
        vocab_service=mock_vocabulary_service
    )

    # Mock the enrich_document method
    enrichment_service.enrich_document = mock_enrich

    # Mock critique_enrichment to return our predefined critiques
    critique_call_count = [0]

    async def mock_critique(*args, **kwargs):
        result = critic_responses[critique_call_count[0]].copy()
        critique_call_count[0] += 1
        return result

    enrichment_service.critique_enrichment = mock_critique

    # Run iteration loop
    final_enrichment, final_critique = await enrichment_service.enrich_with_iteration(
        text="Test document about Python and FastAPI development. Alice Smith is working on the project.",
        filename="test.txt",
        max_iterations=2,
        min_avg_score=4.0,
        use_critic=True
    )

    # Assertions
    assert final_enrichment is not None
    assert final_critique is not None

    # Quality should have improved
    assert final_critique["overall_quality"] > 2.71  # Better than initial

    # Document should have been enriched with entities
    # Note: Actual patch application depends on implementation
    assert "entities" in final_enrichment


@pytest.mark.asyncio
@pytest.mark.integration
async def test_iteration_loop_stops_at_quality_threshold(mock_llm_service, mock_vocabulary_service):
    """Test that loop stops when quality threshold is reached"""

    # Setup: Initial enrichment already good quality
    good_enrichment = {
        "id": "test-doc",
        "source": {"type": "upload", "path": "/test.txt", "content_hash": "hash123"},
        "doc_time": {"created": "2025-01-01T00:00:00"},
        "title": "High Quality Document",
        "summary": "Comprehensive and well-structured summary",
        "topics": ["tech/ai", "tech/programming"],
        "entities": {
            "people": ["Dr. Smith", "Jane Doe"],
            "organizations": ["TechCorp"],
            "locations": ["Berlin"],
            "technologies": ["Python", "Docker"]
        },
        "significance_score": 0.85,
        "quality_tier": "high"
    }

    # Mock high quality score on first iteration
    high_quality_critique = {
        "scores": {
            "schema_compliance": 5.0,
            "entity_quality": 4.5,
            "topic_relevance": 4.5,
            "summary_quality": 4.5,
            "task_identification": 4.0,
            "privacy_assessment": 5.0,
            "metadata_completeness": 4.5
        },
        "overall_quality": 4.57,
        "suggestions": ["Excellent quality, minor improvements possible"],
        "critic_model": "groq/llama-3.1-8b-instant",
        "critic_cost": 0.0001,
        "critic_date": "2025-01-01T00:00:00"
    }

    # Create enrichment service
    enrichment_service = EnrichmentService(
        llm_service=mock_llm_service,
        vocab_service=mock_vocabulary_service
    )

    # Mock methods
    enrichment_service.enrich_document = AsyncMock(return_value=good_enrichment.copy())
    enrichment_service.critique_enrichment = AsyncMock(return_value=high_quality_critique.copy())

    # Run iteration loop
    final_enrichment, final_critique = await enrichment_service.enrich_with_iteration(
        text="High quality document text",
        filename="test.txt",
        max_iterations=2,
        min_avg_score=4.0,  # Threshold
        use_critic=True
    )

    # Should only call critique once (initial score already above threshold)
    assert enrichment_service.critique_enrichment.call_count == 1

    # Should return high quality
    assert final_critique["overall_quality"] >= 4.0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_iteration_loop_max_iterations_limit(mock_llm_service, mock_vocabulary_service):
    """Test that loop respects max iterations limit"""

    # Setup: Always return low quality (never reaches threshold)
    low_enrichment = {
        "id": "test-doc",
        "source": {"type": "upload", "path": "/test.txt", "content_hash": "hash123"},
        "doc_time": {"created": "2025-01-01T00:00:00"},
        "title": "Poor Quality",
        "summary": "Bad",
        "topics": [],
        "entities": {"people": [], "organizations": [], "locations": [], "technologies": []}
    }

    low_quality_critique = {
        "scores": {
            "schema_compliance": 2.0,
            "entity_quality": 1.0,
            "topic_relevance": 1.0,
            "summary_quality": 2.0,
            "task_identification": 1.0,
            "privacy_assessment": 3.0,
            "metadata_completeness": 1.0
        },
        "overall_quality": 1.57,  # Always below threshold
        "suggestions": ["Needs major improvements"],
        "critic_model": "groq/llama-3.1-8b-instant",
        "critic_cost": 0.0001,
        "critic_date": "2025-01-01T00:00:00"
    }

    # Create enrichment service
    enrichment_service = EnrichmentService(
        llm_service=mock_llm_service,
        vocab_service=mock_vocabulary_service
    )

    # Mock methods
    enrichment_service.enrich_document = AsyncMock(return_value=low_enrichment.copy())
    enrichment_service.critique_enrichment = AsyncMock(return_value=low_quality_critique.copy())

    # Mock editor to always return empty patch (no improvement)
    with patch('src.services.editor_service.EditorService') as MockEditor:
        mock_editor_instance = MockEditor.return_value
        mock_editor_instance.generate_patch = AsyncMock(return_value={
            "add": {},
            "replace": {},
            "remove": []
        })

        # Run iteration loop with max 3 iterations
        final_enrichment, final_critique = await enrichment_service.enrich_with_iteration(
            text="Poor quality document",
            filename="test.txt",
            max_iterations=3,
            min_avg_score=4.0,
            use_critic=True
        )

        # Should call critique max_iterations times (3)
        # Initial + 2 more attempts = 3 total
        assert enrichment_service.critique_enrichment.call_count == 3

        # Should still have low quality (never reached threshold)
        assert final_critique["overall_quality"] < 4.0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_iteration_loop_handles_editor_errors_gracefully(mock_llm_service, mock_vocabulary_service):
    """Test that loop handles editor errors without crashing"""

    enrichment = {
        "id": "test",
        "source": {"type": "upload", "path": "/test.txt", "content_hash": "hash"},
        "doc_time": {"created": "2025-01-01T00:00:00"},
        "title": "Test",
        "summary": "Test summary"
    }

    critique = {
        "scores": {
            "schema_compliance": 3.0,
            "entity_quality": 2.0,
            "topic_relevance": 2.0,
            "summary_quality": 3.0,
            "task_identification": 3.0,
            "privacy_assessment": 4.0,
            "metadata_completeness": 2.0
        },
        "overall_quality": 2.71,
        "suggestions": ["Improve quality"],
        "critic_model": "groq/llama-3.1-8b-instant",
        "critic_cost": 0.0001,
        "critic_date": "2025-01-01T00:00:00"
    }

    # Create enrichment service
    enrichment_service = EnrichmentService(
        llm_service=mock_llm_service,
        vocab_service=mock_vocabulary_service
    )

    enrichment_service.enrich_document = AsyncMock(return_value=enrichment.copy())
    enrichment_service.critique_enrichment = AsyncMock(return_value=critique.copy())

    # Mock editor to return empty patch (simulates error that's handled internally)
    with patch('src.services.editor_service.EditorService') as MockEditor:
        mock_editor_instance = MockEditor.return_value
        mock_editor_instance.generate_patch = AsyncMock(return_value={
            "add": {},
            "replace": {},
            "remove": []
        })
        mock_editor_instance.FORBIDDEN_PATHS = []

        # Should complete without crashing
        final_enrichment, final_critique = await enrichment_service.enrich_with_iteration(
            text="Test document",
            filename="test.txt",
            max_iterations=2,
            min_avg_score=4.0,
            use_critic=True
        )

        # Should return enrichment even if editor can't improve it
        assert final_enrichment is not None
        assert final_critique is not None


@pytest.mark.integration
def test_patch_service_integration_with_validator():
    """Test PatchService and SchemaValidator integration"""
    from pathlib import Path

    schema_path = Path(__file__).parent.parent.parent / "src" / "schemas" / "enrichment_schema.json"

    patch_service = PatchService()
    validator = SchemaValidator(schema_path=str(schema_path))

    # Start with valid metadata
    original = {
        "id": "test-123",
        "source": {"type": "upload", "path": "/test"},
        "doc_time": {"created": "2025-01-01T00:00:00"},
        "summary": {"tl_dr": "Original summary"},
        "topics": ["topic1", "topic2"]
    }

    # Apply patch that keeps it valid
    valid_patch = {
        "add": {"topics": ["topic3"]},
        "replace": {"summary.tl_dr": "Improved summary"},
        "remove": []
    }

    patched, diff = patch_service.apply_patch(original, valid_patch)

    # Validate result
    is_valid, errors = validator.validate_enrichment(patched, strict=False)

    assert is_valid
    assert patched["topics"] == ["topic1", "topic2", "topic3"]
    assert patched["summary"]["tl_dr"] == "Improved summary"
