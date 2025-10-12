"""
Unit tests for LLMService and CostTracker

Tests the multi-provider LLM service including:
- Cost tracking and budgeting
- Token estimation
- Provider availability checking
- Cost calculation logic
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from src.services.llm_service import LLMService, CostTracker, MODEL_PRICING
from src.core.config import Settings
from src.models.schemas import CostInfo, CostStats


# =============================================================================
# CostTracker Tests
# =============================================================================

class TestCostTracker:
    """Test the CostTracker class"""

    def test_init(self):
        """Test CostTracker initialization"""
        tracker = CostTracker(daily_budget=5.0)
        assert tracker.daily_budget == 5.0
        assert tracker.total_cost == 0.0
        assert len(tracker.operations) == 0
        assert len(tracker.daily_totals) == 0

    def test_estimate_tokens(self):
        """Test token estimation (4 chars ≈ 1 token)"""
        tracker = CostTracker()

        # Empty string
        assert tracker.estimate_tokens("") == 1  # Min 1 token

        # Short text (~25 tokens)
        assert tracker.estimate_tokens("a" * 100) == 25

        # Realistic text
        text = "This is a test sentence with approximately thirty characters."
        tokens = tracker.estimate_tokens(text)
        assert 10 < tokens < 20  # Roughly 15 tokens

    def test_calculate_cost_known_model(self):
        """Test cost calculation for known models"""
        tracker = CostTracker()

        # Test Groq (cheapest)
        cost = tracker.calculate_cost(
            model="groq/llama-3.1-8b-instant",
            input_tokens=1000,
            output_tokens=500
        )
        # (1000/1M * 0.05) + (500/1M * 0.08) = 0.00005 + 0.00004 = 0.00009
        assert abs(cost - 0.00009) < 0.000001

        # Test Claude Haiku
        cost = tracker.calculate_cost(
            model="anthropic/claude-3-haiku-20240307",
            input_tokens=10000,
            output_tokens=5000
        )
        # (10000/1M * 0.25) + (5000/1M * 1.25) = 0.0025 + 0.00625 = 0.00875
        assert abs(cost - 0.00875) < 0.000001

    def test_calculate_cost_unknown_model(self):
        """Test cost calculation for unknown models returns 0"""
        tracker = CostTracker()
        cost = tracker.calculate_cost(
            model="unknown/model",
            input_tokens=1000,
            output_tokens=500
        )
        assert cost == 0.0

    def test_check_budget_under_limit(self):
        """Test budget check when under daily limit"""
        tracker = CostTracker(daily_budget=10.0)

        # No operations yet
        assert tracker.check_budget() is True

        # Record operation under budget
        tracker.record_operation(
            provider="groq",
            model="groq/llama-3.1-8b-instant",
            input_tokens=1000,
            output_tokens=500,
            cost=0.5
        )
        assert tracker.check_budget() is True

    def test_check_budget_over_limit(self):
        """Test budget check when over daily limit"""
        tracker = CostTracker(daily_budget=1.0)

        # Record operation that exceeds budget
        tracker.record_operation(
            provider="anthropic",
            model="anthropic/claude-3-opus-20240229",
            input_tokens=100000,
            output_tokens=50000,
            cost=5.0
        )

        # Should be over budget
        assert tracker.check_budget() is False

    def test_record_operation(self):
        """Test recording operations updates all tracking"""
        tracker = CostTracker(daily_budget=10.0)
        today = datetime.now().strftime("%Y-%m-%d")

        # Record first operation
        tracker.record_operation(
            provider="groq",
            model="groq/llama-3.1-8b-instant",
            input_tokens=1000,
            output_tokens=500,
            cost=0.1
        )

        assert len(tracker.operations) == 1
        assert tracker.total_cost == 0.1
        assert tracker.daily_totals[today] == 0.1

        # Record second operation
        tracker.record_operation(
            provider="anthropic",
            model="anthropic/claude-3-haiku-20240307",
            input_tokens=2000,
            output_tokens=1000,
            cost=0.3
        )

        assert len(tracker.operations) == 2
        assert tracker.total_cost == 0.4
        assert tracker.daily_totals[today] == 0.4

    def test_get_stats(self):
        """Test getting cost statistics"""
        tracker = CostTracker(daily_budget=10.0)

        # Record some operations
        tracker.record_operation(
            provider="groq",
            model="groq/llama-3.1-8b-instant",
            input_tokens=1000,
            output_tokens=500,
            cost=0.1
        )
        tracker.record_operation(
            provider="anthropic",
            model="anthropic/claude-3-haiku-20240307",
            input_tokens=2000,
            output_tokens=1000,
            cost=0.5
        )
        tracker.record_operation(
            provider="groq",
            model="groq/llama-3.1-8b-instant",
            input_tokens=3000,
            output_tokens=1500,
            cost=0.2
        )

        stats = tracker.get_stats()

        assert stats.total_cost_today == pytest.approx(0.8)
        assert stats.total_cost_all_time == pytest.approx(0.8)
        assert stats.daily_budget == 10.0
        assert stats.budget_remaining == pytest.approx(9.2)
        assert stats.operations_today == 3
        assert stats.most_expensive_operation.cost_usd == pytest.approx(0.5)
        assert stats.cost_by_provider["groq"] == pytest.approx(0.3)
        assert stats.cost_by_provider["anthropic"] == pytest.approx(0.5)


# =============================================================================
# LLMService Tests
# =============================================================================

class TestLLMService:
    """Test the LLMService class"""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with API keys"""
        settings = Mock(spec=Settings)
        settings.groq_api_key = "test_groq_key"
        settings.anthropic_api_key = "test_anthropic_key"
        settings.openai_api_key = "test_openai_key"
        settings.google_api_key = None  # Optional
        settings.llm_temperature = 0.7
        settings.llm_max_retries = 3
        settings.daily_budget_usd = 10.0
        settings.default_llm = "groq"
        settings.fallback_llm = "anthropic"
        settings.emergency_llm = "openai"
        settings.enable_cost_tracking = True
        return settings

    def test_init(self, mock_settings):
        """Test LLMService initialization"""
        service = LLMService(mock_settings)

        assert service.settings == mock_settings
        assert service.cost_tracker is not None
        assert service.cost_tracker.daily_budget == 10.0

    def test_is_provider_available(self, mock_settings):
        """Test checking if providers are available"""
        service = LLMService(mock_settings)

        # Providers with API keys
        assert service.is_provider_available("groq") is True
        assert service.is_provider_available("anthropic") is True
        assert service.is_provider_available("openai") is True

        # Provider without API key
        assert service.is_provider_available("google") is False

        # Unknown provider
        assert service.is_provider_available("unknown") is False

    def test_get_available_providers(self, mock_settings):
        """Test getting list of available providers"""
        service = LLMService(mock_settings)

        providers = service.get_available_providers()
        assert "groq" in providers
        assert "anthropic" in providers
        assert "openai" in providers
        assert "google" not in providers  # No API key

    def test_get_available_models(self, mock_settings):
        """Test getting list of available models"""
        service = LLMService(mock_settings)

        models = service.get_available_models()

        # Should include models from providers with API keys
        assert any("groq" in model for model in models)
        assert any("anthropic" in model for model in models)
        assert any("openai" in model for model in models)

        # Should not include models from providers without keys
        assert not any("google" in model for model in models)

    def test_get_cost_stats(self, mock_settings):
        """Test getting cost statistics from service"""
        service = LLMService(mock_settings)

        # Record some costs
        service.cost_tracker.record_operation(
            provider="groq",
            model="groq/llama-3.1-8b-instant",
            input_tokens=1000,
            output_tokens=500,
            cost=0.1
        )

        stats = service.get_cost_stats()
        assert isinstance(stats, CostStats)
        assert stats.total_cost_today == 0.1
        assert stats.operations_today == 1

    @pytest.mark.asyncio
    async def test_call_llm_missing_api_key(self, mock_settings):
        """Test that calling LLM with missing API key fails gracefully"""
        # Set up settings with no API keys
        mock_settings.groq_api_key = None
        mock_settings.anthropic_api_key = None
        mock_settings.openai_api_key = None

        service = LLMService(mock_settings)

        with pytest.raises(Exception):  # Should raise an error
            await service.call_llm(
                prompt="Test prompt",
                model="groq/llama-3.1-8b-instant"
            )

    @pytest.mark.asyncio
    @patch('src.services.llm_service.litellm.acompletion')
    async def test_call_llm_success_groq(self, mock_acompletion, mock_settings):
        """Test successful LLM call via LiteLLM"""
        # Mock LiteLLM response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response from LiteLLM"

        mock_acompletion.return_value = mock_response

        service = LLMService(mock_settings)

        response, cost, model_used = await service.call_llm(
            prompt="Test prompt",
            model_id="groq/llama-3.1-8b-instant",
            temperature=0.7
        )

        assert response == "Test response from LiteLLM"
        assert cost > 0
        assert model_used == "groq/llama-3.1-8b-instant"
        assert len(service.cost_tracker.operations) == 1

        # Verify LiteLLM was called with correct parameters
        mock_acompletion.assert_called_once()
        call_args = mock_acompletion.call_args
        assert call_args[1]['model'] == "groq/llama-3.1-8b-instant"
        assert call_args[1]['temperature'] == 0.7


# =============================================================================
# Integration Test Markers
# =============================================================================

def test_model_pricing_coverage():
    """Test that all major models have pricing information"""
    required_models = [
        "groq/llama-3.1-8b-instant",
        "anthropic/claude-3-haiku-20240307",
        "openai/gpt-4o-mini"
    ]

    for model in required_models:
        assert model in MODEL_PRICING, f"Missing pricing for {model}"
        assert "input" in MODEL_PRICING[model]
        assert "output" in MODEL_PRICING[model]
        assert MODEL_PRICING[model]["input"] > 0
        assert MODEL_PRICING[model]["output"] > 0
