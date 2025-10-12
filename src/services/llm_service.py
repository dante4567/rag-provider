"""
LLM (Large Language Model) service - LiteLLM Integration

Unified LLM interface using LiteLLM for provider management,
with preserved cost tracking and budget enforcement.
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import os

# LiteLLM unified interface
import litellm

from src.core.config import Settings
from src.models.schemas import LLMProvider, CostInfo, CostStats

logger = logging.getLogger(__name__)

# Suppress LiteLLM verbose logging
litellm.suppress_debug_info = True


# Model pricing (per 1M tokens)
# Last updated: 2025-10-12 (v3.0 migration)
# Next review: 2025-11-01 (monthly - 1st of each month)
# Review script: python scripts/check_model_pricing.py
# Philosophy: Prioritize quality - willing to pay more for significant improvements
MODEL_PRICING = {
    # Groq - Lightning fast inference
    "groq/llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "groq/llama-3.1-70b-versatile": {"input": 0.59, "output": 0.79},

    # Anthropic - High quality reasoning
    "anthropic/claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "anthropic/claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    "anthropic/claude-3-5-sonnet-latest": {"input": 3.0, "output": 15.0},  # Same as 20241022
    "anthropic/claude-3-opus-20240229": {"input": 15.0, "output": 75.0},

    # OpenAI - Reliable general purpose
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai/gpt-4o": {"input": 5.0, "output": 15.0},
    "openai/gpt-4-turbo": {"input": 10.0, "output": 30.0},

    # Google - Long context specialist
    "google/gemini-1.5-pro": {"input": 1.25, "output": 5.0},
    "google/gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "google/gemini-2.5-pro": {"input": 1.25, "output": 5.0}
}


class CostTracker:
    """
    Tracks LLM API costs and enforces budget limits

    Maintains in-memory storage of operations and costs
    """

    def __init__(self, daily_budget: float = 10.0):
        """
        Initialize cost tracker

        Args:
            daily_budget: Daily budget limit in USD
        """
        self.operations: List[CostInfo] = []
        self.daily_totals: Dict[str, float] = {}
        self.total_cost: float = 0.0
        self.daily_budget = daily_budget

    def estimate_tokens(self, text: str) -> int:
        """
        Rough token estimation (4 chars ≈ 1 token for most models)

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        return max(1, len(text) // 4)

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost based on model pricing

        Args:
            model: Model ID (e.g., "groq/llama-3.1-8b-instant")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        if model not in MODEL_PRICING:
            logger.warning(f"No pricing info for model: {model}")
            return 0.0

        pricing = MODEL_PRICING[model]
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def check_budget(self) -> bool:
        """
        Check if daily budget limit is reached

        Returns:
            True if budget available, False if limit reached
        """
        today = datetime.now().strftime("%Y-%m-%d")
        today_cost = self.daily_totals.get(today, 0.0)
        return today_cost < self.daily_budget

    def record_operation(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float
    ):
        """
        Record an API operation and its cost

        Args:
            provider: LLM provider name
            model: Model ID
            input_tokens: Input token count
            output_tokens: Output token count
            cost: Cost in USD
        """
        today = datetime.now().strftime("%Y-%m-%d")

        operation = CostInfo(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            timestamp=datetime.now()
        )

        self.operations.append(operation)
        self.daily_totals[today] = self.daily_totals.get(today, 0.0) + cost
        self.total_cost += cost

        logger.info(f"Recorded ${cost:.6f} cost for {provider}/{model}")

    def get_stats(self) -> CostStats:
        """
        Get current cost statistics

        Returns:
            Cost statistics including daily totals and provider breakdown
        """
        today = datetime.now().strftime("%Y-%m-%d")
        today_cost = self.daily_totals.get(today, 0.0)

        cost_by_provider: Dict[str, float] = {}
        operations_today = 0
        most_expensive: Optional[CostInfo] = None
        max_cost = 0.0

        for op in self.operations:
            if op.timestamp.strftime("%Y-%m-%d") == today:
                operations_today += 1
                cost_by_provider[op.provider] = cost_by_provider.get(op.provider, 0.0) + op.cost_usd

                if op.cost_usd > max_cost:
                    max_cost = op.cost_usd
                    most_expensive = op

        return CostStats(
            total_cost_today=today_cost,
            total_cost_all_time=self.total_cost,
            daily_budget=self.daily_budget,
            budget_remaining=max(0.0, self.daily_budget - today_cost),
            operations_today=operations_today,
            most_expensive_operation=most_expensive,
            cost_by_provider=cost_by_provider
        )


class LLMService:
    """
    LiteLLM-powered LLM service with automatic fallback and cost tracking

    Supports 100+ LLM providers via unified LiteLLM interface
    """

    def __init__(self, settings: Settings):
        """
        Initialize LLM service with LiteLLM

        Args:
            settings: Application settings with API keys
        """
        self.settings = settings
        self.cost_tracker = CostTracker(daily_budget=settings.daily_budget_usd)

        # Configure LiteLLM with environment variables
        self._configure_litellm()

        # Provider order for fallbacks
        self.provider_order = [
            settings.default_llm,
            settings.fallback_llm,
            settings.emergency_llm
        ]

        # Available providers (determined by API keys)
        self.available_providers = self._detect_available_providers()

        # Provider-to-model mapping for fallbacks
        self.fallback_models = self._build_fallback_models()

        logger.info(f"✅ LiteLLM service initialized with providers: {self.available_providers}")

    def _configure_litellm(self):
        """Configure LiteLLM with API keys from settings"""
        # Set API keys in environment (LiteLLM reads from env)
        if self.settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = self.settings.anthropic_api_key
        if self.settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self.settings.openai_api_key
        if self.settings.groq_api_key:
            os.environ["GROQ_API_KEY"] = self.settings.groq_api_key
        if self.settings.google_api_key:
            os.environ["GOOGLE_API_KEY"] = self.settings.google_api_key

    def _detect_available_providers(self) -> List[str]:
        """Detect which providers are available based on API keys"""
        providers = []
        if self.settings.anthropic_api_key:
            providers.append("anthropic")
        if self.settings.openai_api_key:
            providers.append("openai")
        if self.settings.groq_api_key:
            providers.append("groq")
        if self.settings.google_api_key:
            providers.append("google")
        return providers

    def _build_fallback_models(self) -> Dict[str, str]:
        """Build provider-to-default-model mapping"""
        return {
            "anthropic": "anthropic/claude-3-5-sonnet-20241022",
            "openai": "openai/gpt-4o-mini",
            "groq": "groq/llama-3.1-8b-instant",
            "google": "google/gemini-2.0-flash"
        }

    async def call_llm(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Tuple[str, float, str]:
        """
        Call LLM via LiteLLM with automatic fallback

        Args:
            prompt: Input prompt
            model_id: Specific model to use (optional, uses default if None)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Tuple of (response_text, cost_usd, model_used)

        Raises:
            Exception: If all providers fail or budget exceeded
        """
        # Check budget
        if self.settings.enable_cost_tracking and not self.cost_tracker.check_budget():
            raise Exception(f"Daily budget limit (${self.settings.daily_budget_usd}) reached")

        # Determine which model(s) to try
        if model_id:
            # Specific model requested
            models_to_try = [model_id]
        else:
            # Build fallback chain from provider order
            models_to_try = []
            for provider in self.provider_order:
                if provider in self.available_providers:
                    models_to_try.append(self.fallback_models.get(provider))

        # Remove None values
        models_to_try = [m for m in models_to_try if m]

        if not models_to_try:
            raise Exception("No LLM providers available")

        # Try models in order (LiteLLM handles fallback automatically)
        for attempt_model in models_to_try:
            try:
                result, cost = await self._call_with_litellm(
                    prompt=prompt,
                    model_id=attempt_model,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return result, cost, attempt_model

            except Exception as e:
                provider = attempt_model.split('/')[0] if '/' in attempt_model else "unknown"
                logger.warning(f"LLM call failed for {attempt_model}: {e}")

                # If this was the last model, raise the exception
                if attempt_model == models_to_try[-1]:
                    raise Exception(f"All LLM providers failed. Last error: {e}")

                # Otherwise continue to next model
                continue

        raise Exception("All LLM providers failed")

    async def _call_with_litellm(
        self,
        prompt: str,
        model_id: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Tuple[str, float]:
        """
        Call LiteLLM and return response with cost tracking

        Args:
            prompt: Input prompt
            model_id: Model ID to use (LiteLLM format: "provider/model")
            max_tokens: Maximum tokens
            temperature: Sampling temperature

        Returns:
            Tuple of (response_text, cost_usd)

        Raises:
            Exception: If LiteLLM call fails
        """
        # Estimate input tokens for cost tracking
        input_tokens = self.cost_tracker.estimate_tokens(prompt)

        # Set default parameters
        tokens = max_tokens or 4000
        temp = temperature if temperature is not None else self.settings.llm_temperature

        try:
            # Call LiteLLM (async)
            response = await litellm.acompletion(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=tokens,
                temperature=temp,
                timeout=30
            )

            # Extract response text
            result = response.choices[0].message.content

            # Estimate output tokens
            output_tokens = self.cost_tracker.estimate_tokens(result)

            # Calculate cost
            cost = self.cost_tracker.calculate_cost(model_id, input_tokens, output_tokens)

            # Record operation
            if self.settings.enable_cost_tracking:
                provider = model_id.split('/')[0] if '/' in model_id else "unknown"
                self.cost_tracker.record_operation(
                    provider=provider,
                    model=model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost
                )

            return result, cost

        except Exception as e:
            logger.error(f"LiteLLM call failed for {model_id}: {e}")
            raise

    async def call_llm_structured(
        self,
        prompt: str,
        response_model: Any,
        model_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Tuple[Any, float, str]:
        """
        Call LLM with Instructor for type-safe structured outputs

        Args:
            prompt: Input prompt
            response_model: Pydantic model class for structured response
            model_id: Specific model to use (optional)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Tuple of (structured_response, cost_usd, model_used)

        Raises:
            Exception: If all providers fail or budget exceeded
        """
        import instructor
        from pydantic import BaseModel

        # Check budget
        if self.settings.enable_cost_tracking and not self.cost_tracker.check_budget():
            raise Exception(f"Daily budget limit (${self.settings.daily_budget_usd}) reached")

        # Determine which model(s) to try
        if model_id:
            models_to_try = [model_id]
        else:
            models_to_try = []
            for provider in self.provider_order:
                if provider in self.available_providers:
                    models_to_try.append(self.fallback_models.get(provider))
            models_to_try = [m for m in models_to_try if m]

        if not models_to_try:
            raise Exception("No LLM providers available")

        # Try models in order
        for attempt_model in models_to_try:
            try:
                # Estimate input tokens
                input_tokens = self.cost_tracker.estimate_tokens(prompt)

                # Set parameters
                tokens = max_tokens or 4000
                temp = temperature if temperature is not None else self.settings.llm_temperature

                # Create Instructor client wrapping LiteLLM
                client = instructor.from_litellm(litellm.acompletion)

                # Call with structured output using OpenAI-style interface
                response = await client.chat.completions.create(
                    model=attempt_model,
                    messages=[{"role": "user", "content": prompt}],
                    response_model=response_model,
                    max_tokens=tokens,
                    temperature=temp,
                    timeout=30
                )

                # Estimate output tokens (use serialized response)
                response_text = response.model_dump_json() if isinstance(response, BaseModel) else str(response)
                output_tokens = self.cost_tracker.estimate_tokens(response_text)

                # Calculate cost
                cost = self.cost_tracker.calculate_cost(attempt_model, input_tokens, output_tokens)

                # Record operation
                if self.settings.enable_cost_tracking:
                    provider = attempt_model.split('/')[0] if '/' in attempt_model else "unknown"
                    self.cost_tracker.record_operation(
                        provider=provider,
                        model=attempt_model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost=cost
                    )

                return response, cost, attempt_model

            except Exception as e:
                provider = attempt_model.split('/')[0] if '/' in attempt_model else "unknown"
                logger.warning(f"Structured LLM call failed for {attempt_model}: {e}")

                if attempt_model == models_to_try[-1]:
                    raise Exception(f"All LLM providers failed. Last error: {e}")

                continue

        raise Exception("All LLM providers failed")

    def get_cost_stats(self) -> CostStats:
        """
        Get current cost tracking statistics

        Returns:
            Cost statistics
        """
        return self.cost_tracker.get_stats()

    def is_provider_available(self, provider: str) -> bool:
        """
        Check if provider is available

        Args:
            provider: Provider name

        Returns:
            True if available
        """
        return provider in self.available_providers

    def get_available_providers(self) -> List[str]:
        """
        Get list of available providers

        Returns:
            List of provider names
        """
        return self.available_providers

    def get_available_models(self) -> List[str]:
        """
        Get list of all available models

        Returns:
            List of model IDs from MODEL_PRICING
        """
        # Return models for available providers
        models = []
        for model_id in MODEL_PRICING.keys():
            provider = model_id.split('/')[0]
            if provider in self.available_providers:
                models.append(model_id)
        return models
