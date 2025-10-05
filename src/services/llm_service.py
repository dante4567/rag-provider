"""
LLM (Large Language Model) service

Handles LLM provider management, API calls, cost tracking, and fallback logic
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

# LLM provider SDKs
import anthropic
import openai
import groq

from src.core.config import Settings
from src.models.schemas import LLMProvider, CostInfo, CostStats

logger = logging.getLogger(__name__)

# Check Google availability
try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("Google Generative AI not available")


# Model pricing (per 1M tokens) - Updated 2024
MODEL_PRICING = {
    # Groq - Lightning fast inference
    "groq/llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},

    # Anthropic - High quality reasoning
    "anthropic/claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "anthropic/claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    "anthropic/claude-3-opus-20240229": {"input": 15.0, "output": 75.0},

    # OpenAI - Reliable general purpose
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai/gpt-4o": {"input": 5.0, "output": 15.0},

    # Google - Long context specialist
    "google/gemini-1.5-pro": {"input": 1.25, "output": 5.0}
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
    Service for managing multiple LLM providers with fallback and cost tracking

    Supports: Anthropic, OpenAI, Groq, Google Gemini
    """

    def __init__(self, settings: Settings):
        """
        Initialize LLM service

        Args:
            settings: Application settings with API keys
        """
        self.settings = settings
        self.cost_tracker = CostTracker(daily_budget=settings.daily_budget_usd)

        # Provider order for fallbacks
        self.provider_order = [
            settings.default_llm,
            settings.fallback_llm,
            settings.emergency_llm
        ]

        # Initialize provider clients
        self.clients: Dict[str, Any] = {}
        self._initialize_clients()

        # Provider configurations
        self.provider_configs = self._build_provider_configs()

    def _initialize_clients(self):
        """Initialize LLM provider clients based on available API keys"""

        # Anthropic
        if self.settings.anthropic_api_key:
            try:
                self.clients["anthropic"] = anthropic.Anthropic(
                    api_key=self.settings.anthropic_api_key
                )
                logger.info("Initialized Anthropic client")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic: {e}")

        # OpenAI
        if self.settings.openai_api_key:
            try:
                self.clients["openai"] = openai.OpenAI(
                    api_key=self.settings.openai_api_key
                )
                logger.info("Initialized OpenAI client")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")

        # Groq
        if self.settings.groq_api_key:
            try:
                self.clients["groq"] = groq.Groq(
                    api_key=self.settings.groq_api_key
                )
                logger.info("Initialized Groq client")
            except Exception as e:
                logger.error(f"Failed to initialize Groq: {e}")

        # Google Gemini
        if self.settings.google_api_key and GOOGLE_AVAILABLE:
            try:
                genai.configure(api_key=self.settings.google_api_key)
                # Note: Model is selected per-call, just store genai module
                self.clients["google"] = genai
                logger.info("Initialized Google Gemini client")
            except Exception as e:
                logger.error(f"Failed to initialize Google: {e}")

    def _build_provider_configs(self) -> Dict[str, Dict]:
        """Build provider configuration dictionary"""
        return {
            "anthropic": {
                "models": {
                    "anthropic/claude-3-haiku-20240307": {
                        "max_tokens": 4000,
                        "model_name": "claude-3-haiku-20240307"
                    },
                    "anthropic/claude-3-5-sonnet-latest": {
                        "max_tokens": 4000,
                        "model_name": "claude-3-5-sonnet-latest"
                    },
                    "anthropic/claude-3-opus-20240229": {
                        "max_tokens": 4000,
                        "model_name": "claude-3-opus-20240229"
                    }
                }
            },
            "openai": {
                "models": {
                    "openai/gpt-4o-mini": {
                        "max_tokens": 4000,
                        "model_name": "gpt-4o-mini"
                    },
                    "openai/gpt-4o": {
                        "max_tokens": 4000,
                        "model_name": "gpt-4o"
                    }
                }
            },
            "groq": {
                "models": {
                    "groq/llama-3.1-8b-instant": {
                        "max_tokens": 8000,
                        "model_name": "llama-3.1-8b-instant"
                    },
                    "groq/llama3-70b-8192": {
                        "max_tokens": 8192,
                        "model_name": "llama3-70b-8192"
                    }
                }
            },
            "google": {
                "models": {
                    "google/gemini-pro-latest": {
                        "max_tokens": 8000,
                        "model_name": "models/gemini-pro-latest"
                    },
                    "google/gemini-2.5-pro": {
                        "max_tokens": 8000,
                        "model_name": "models/gemini-2.5-pro"
                    },
                    "google/gemini-2.0-flash": {
                        "max_tokens": 8000,
                        "model_name": "models/gemini-2.0-flash"
                    }
                }
            }
        }

    def get_model_info(self, model_id: str) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Extract provider and model config from model ID

        Args:
            model_id: Full model ID (e.g., "groq/llama-3.1-8b-instant")

        Returns:
            Tuple of (provider_name, model_config) or (None, None) if not found
        """
        try:
            provider = model_id.split('/')[0]
            if provider in self.provider_configs:
                models = self.provider_configs[provider]["models"]
                if model_id in models:
                    return provider, models[model_id]
        except Exception as e:
            logger.error(f"Error parsing model ID '{model_id}': {e}")

        return None, None

    async def call_llm(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Tuple[str, float, str]:
        """
        Call LLM with automatic fallback

        Args:
            prompt: Input prompt
            model_id: Specific model to use (optional, uses default if None)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Tuple of (response_text, cost_usd, model_used)

        Raises:
            Exception: If all providers fail
        """
        # Check budget
        if self.settings.enable_cost_tracking and not self.cost_tracker.check_budget():
            raise Exception(f"Daily budget limit (${self.settings.daily_budget_usd}) reached")

        # If specific model requested, try it
        if model_id:
            try:
                result, cost = await self._call_specific_model(
                    prompt=prompt,
                    model_id=model_id,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return result, cost, model_id
            except Exception as e:
                logger.error(f"Failed to call specific model {model_id}: {e}")
                raise

        # Otherwise, try providers in order
        for provider in self.provider_order:
            if provider not in self.clients:
                continue

            # Get first model for provider
            provider_models = self.provider_configs.get(provider, {}).get("models", {})
            if not provider_models:
                continue

            default_model = list(provider_models.keys())[0]

            try:
                result, cost = await self._call_specific_model(
                    prompt=prompt,
                    model_id=default_model,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return result, cost, default_model

            except Exception as e:
                logger.warning(f"LLM provider {provider} failed: {e}")
                continue

        raise Exception("All LLM providers failed")

    async def _call_specific_model(
        self,
        prompt: str,
        model_id: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Tuple[str, float]:
        """
        Call specific LLM model and return response with cost

        Args:
            prompt: Input prompt
            model_id: Model ID to use
            max_tokens: Maximum tokens
            temperature: Sampling temperature

        Returns:
            Tuple of (response_text, cost_usd)

        Raises:
            Exception: If model not available or call fails
        """
        provider, model_config = self.get_model_info(model_id)

        if not provider or provider not in self.clients:
            raise Exception(f"Model {model_id} not available")

        client = self.clients[provider]
        model_name = model_config["model_name"]
        tokens = max_tokens or model_config["max_tokens"]
        temp = temperature if temperature is not None else self.settings.llm_temperature

        # Estimate input tokens
        input_tokens = self.cost_tracker.estimate_tokens(prompt)

        try:
            # Call appropriate provider API
            if provider == "anthropic":
                response = client.messages.create(
                    model=model_name,
                    max_tokens=tokens,
                    temperature=temp,
                    messages=[{"role": "user", "content": prompt}]
                )
                result = response.content[0].text
                output_tokens = self.cost_tracker.estimate_tokens(result)

            elif provider in ["openai", "groq"]:
                response = client.chat.completions.create(
                    model=model_name,
                    max_tokens=tokens,
                    temperature=temp,
                    messages=[{"role": "user", "content": prompt}]
                )
                result = response.choices[0].message.content
                output_tokens = self.cost_tracker.estimate_tokens(result)

            elif provider == "google":
                # Create model instance per-call with specific model_name
                model = client.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                result = response.text
                output_tokens = self.cost_tracker.estimate_tokens(result)

            else:
                raise Exception(f"Unknown provider: {provider}")

            # Calculate and record cost
            cost = self.cost_tracker.calculate_cost(model_id, input_tokens, output_tokens)

            if self.settings.enable_cost_tracking:
                self.cost_tracker.record_operation(
                    provider=provider,
                    model=model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost
                )

            return result, cost

        except Exception as e:
            logger.error(f"LLM call failed for {provider}/{model_id}: {e}")
            raise

    def get_cost_stats(self) -> CostStats:
        """
        Get current cost tracking statistics

        Returns:
            Cost statistics
        """
        return self.cost_tracker.get_stats()

    def is_provider_available(self, provider: str) -> bool:
        """
        Check if provider is initialized and available

        Args:
            provider: Provider name

        Returns:
            True if available
        """
        return provider in self.clients

    def get_available_providers(self) -> List[str]:
        """
        Get list of available (initialized) providers

        Returns:
            List of provider names
        """
        return list(self.clients.keys())

    def get_available_models(self) -> List[str]:
        """
        Get list of all available models

        Returns:
            List of model IDs
        """
        models = []
        for provider in self.clients.keys():
            if provider in self.provider_configs:
                models.extend(self.provider_configs[provider]["models"].keys())
        return models
