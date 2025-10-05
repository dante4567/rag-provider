"""
Unit tests for LLMService
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.services.llm_service import LLMService
from src.core.config import Settings


@pytest.fixture
def settings():
    """Create test settings"""
    return Settings(
        groq_api_key="test_groq_key",
        anthropic_api_key="test_anthropic_key",
        openai_api_key="test_openai_key",
        google_api_key="test_google_key",
        default_llm="groq",
        fallback_llm="anthropic",
        emergency_llm="openai",
        enable_cost_tracking=True,
        daily_budget_usd=10.0
    )


@pytest.fixture
def llm_service(settings):
    """Create LLMService instance"""
    return LLMService(settings)


@pytest.mark.asyncio
async def test_call_llm_with_groq(llm_service):
    """Test calling Groq LLM"""
    with patch('src.services.llm_service.completion') as mock_completion:
        mock_completion.return_value = {
            "choices": [{"message": {"content": "Test response from Groq"}}],
            "usage": {"total_tokens": 100}
        }

        response, cost, model_used = await llm_service.call_llm(
            prompt="Test prompt",
            model_id="groq/llama-3.1-70b-versatile"
        )

        assert response == "Test response from Groq"
        assert cost >= 0
        assert "groq" in model_used.lower()
        mock_completion.assert_called_once()


@pytest.mark.asyncio
async def test_call_llm_with_anthropic(llm_service):
    """Test calling Anthropic Claude"""
    with patch('src.services.llm_service.completion') as mock_completion:
        mock_completion.return_value = {
            "choices": [{"message": {"content": "Test response from Claude"}}],
            "usage": {"total_tokens": 150}
        }

        response, cost, model_used = await llm_service.call_llm(
            prompt="Test prompt",
            model_id="anthropic/claude-3-haiku-20240307"
        )

        assert response == "Test response from Claude"
        assert cost > 0
        assert "anthropic" in model_used.lower()


@pytest.mark.asyncio
async def test_call_llm_fallback_on_failure(llm_service):
    """Test fallback to alternative provider on failure"""
    with patch('src.services.llm_service.completion') as mock_completion:
        # First call fails, second succeeds
        mock_completion.side_effect = [
            Exception("Groq API error"),
            {
                "choices": [{"message": {"content": "Fallback response"}}],
                "usage": {"total_tokens": 100}
            }
        ]

        response, cost, model_used = await llm_service.call_llm(
            prompt="Test prompt"
        )

        assert response == "Fallback response"
        assert mock_completion.call_count == 2  # Tried primary, then fallback


@pytest.mark.asyncio
async def test_call_llm_with_custom_parameters(llm_service):
    """Test LLM call with custom temperature and max_tokens"""
    with patch('src.services.llm_service.completion') as mock_completion:
        mock_completion.return_value = {
            "choices": [{"message": {"content": "Custom response"}}],
            "usage": {"total_tokens": 200}
        }

        await llm_service.call_llm(
            prompt="Test prompt",
            temperature=0.7,
            max_tokens=500
        )

        call_args = mock_completion.call_args[1]
        assert call_args["temperature"] == 0.7
        assert call_args["max_tokens"] == 500


@pytest.mark.asyncio
async def test_cost_tracking(llm_service):
    """Test that costs are tracked correctly"""
    with patch('src.services.llm_service.completion') as mock_completion:
        mock_completion.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"total_tokens": 1000}
        }

        initial_cost = llm_service.total_cost

        _, cost, _ = await llm_service.call_llm(prompt="Test")

        assert cost > 0
        assert llm_service.total_cost > initial_cost
        assert llm_service.total_cost == initial_cost + cost


@pytest.mark.asyncio
async def test_budget_limit_check(llm_service):
    """Test that budget limits are enforced"""
    # Set total cost to exceed budget
    llm_service.total_cost = 15.0  # Exceeds 10.0 budget

    with pytest.raises(Exception) as exc_info:
        await llm_service.call_llm(prompt="Test")

    assert "budget" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_cost_summary(llm_service):
    """Test cost summary retrieval"""
    llm_service.total_cost = 5.25
    llm_service.settings.daily_budget_usd = 10.0

    summary = llm_service.get_cost_summary()

    assert summary["total_cost"] == 5.25
    assert summary["daily_budget"] == 10.0
    assert summary["remaining_budget"] == 4.75
    assert summary["budget_used_percent"] == 52.5


@pytest.mark.asyncio
async def test_all_providers_fail(llm_service):
    """Test behavior when all providers fail"""
    with patch('src.services.llm_service.completion') as mock_completion:
        mock_completion.side_effect = Exception("All APIs down")

        with pytest.raises(Exception):
            await llm_service.call_llm(prompt="Test")


@pytest.mark.asyncio
async def test_streaming_not_supported(llm_service):
    """Test that streaming is handled appropriately"""
    with patch('src.services.llm_service.completion') as mock_completion:
        mock_completion.return_value = {
            "choices": [{"message": {"content": "Non-streaming response"}}],
            "usage": {"total_tokens": 50}
        }

        response, _, _ = await llm_service.call_llm(
            prompt="Test",
            stream=False
        )

        assert response == "Non-streaming response"
        call_args = mock_completion.call_args[1]
        assert call_args.get("stream", False) == False
