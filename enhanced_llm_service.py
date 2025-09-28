"""
Enhanced LLM Service using LiteLLM

This module provides a modern LLM management implementation using LiteLLM
to replace the custom LLM provider management logic. It maintains compatibility
with the existing FastAPI interface while providing better LLM capabilities.

Benefits over the original implementation:
- Unified interface for 100+ LLM providers
- Built-in fallback and retry logic
- Automatic cost tracking and budgeting
- Rate limiting and caching
- Better error handling and logging
- Significantly less code to maintain
"""

import logging
import os
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import asyncio

try:
    import litellm
    from litellm import completion, acompletion
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    logging.warning("LiteLLM not available")

logger = logging.getLogger(__name__)

class EnhancedCostTracker:
    """
    Enhanced cost tracking with LiteLLM integration
    """

    def __init__(self, daily_budget: float = 10.0):
        self.daily_budget = daily_budget
        self.usage_data = {}
        self.current_date = datetime.now().date()

    def reset_daily_usage(self):
        """Reset usage data for a new day"""
        today = datetime.now().date()
        if today != self.current_date:
            self.usage_data = {}
            self.current_date = today

    def record_usage(self, model: str, cost: float, input_tokens: int, output_tokens: int):
        """Record LLM usage with cost"""
        self.reset_daily_usage()

        if "daily" not in self.usage_data:
            self.usage_data["daily"] = {
                "total_cost": 0.0,
                "total_requests": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "by_model": {}
            }

        daily = self.usage_data["daily"]
        daily["total_cost"] += cost
        daily["total_requests"] += 1
        daily["total_input_tokens"] += input_tokens
        daily["total_output_tokens"] += output_tokens

        if model not in daily["by_model"]:
            daily["by_model"][model] = {
                "cost": 0.0,
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0
            }

        model_data = daily["by_model"][model]
        model_data["cost"] += cost
        model_data["requests"] += 1
        model_data["input_tokens"] += input_tokens
        model_data["output_tokens"] += output_tokens

    def check_budget(self) -> bool:
        """Check if we're within budget"""
        self.reset_daily_usage()
        daily_cost = self.usage_data.get("daily", {}).get("total_cost", 0.0)
        return daily_cost < self.daily_budget

    def get_remaining_budget(self) -> float:
        """Get remaining budget for today"""
        self.reset_daily_usage()
        daily_cost = self.usage_data.get("daily", {}).get("total_cost", 0.0)
        return max(0.0, self.daily_budget - daily_cost)

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        self.reset_daily_usage()
        return {
            "daily_budget": self.daily_budget,
            "daily_usage": self.usage_data.get("daily", {}),
            "remaining_budget": self.get_remaining_budget(),
            "budget_percentage": (self.usage_data.get("daily", {}).get("total_cost", 0.0) / self.daily_budget) * 100
        }

class EnhancedLLMService:
    """
    Enhanced LLM service using LiteLLM

    This replaces the custom LLMService with a modern implementation
    that leverages LiteLLM for better LLM management.
    """

    def __init__(self, daily_budget: float = 10.0):
        if not LITELLM_AVAILABLE:
            raise ImportError("LiteLLM is required but not installed")

        self.cost_tracker = EnhancedCostTracker(daily_budget)

        # Configure LiteLLM
        self._setup_litellm()

        # Define model fallback chains
        self.primary_models = [
            "groq/llama-3.1-8b-instant",  # Fast and cheap
            "groq/llama3-70b-8192",       # Better quality
        ]

        self.fallback_models = [
            "anthropic/claude-3-haiku-20240307",     # Cheap and capable
            "anthropic/claude-3-5-sonnet-20241022",  # High quality
        ]

        self.emergency_models = [
            "openai/gpt-4o-mini",  # Reliable
            "openai/gpt-4o",       # Ultimate fallback
        ]

        # Combined fallback chain
        self.fallback_chain = self.primary_models + self.fallback_models + self.emergency_models

        logger.info("Enhanced LLM Service initialized with LiteLLM")

    def _setup_litellm(self):
        """Configure LiteLLM settings"""
        # Set API keys from environment
        api_keys = {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
            "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
            "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
        }

        # Only set keys that are available
        for key, value in api_keys.items():
            if value:
                os.environ[key] = value

        # Configure LiteLLM settings
        litellm.set_verbose = False  # Set to True for debugging
        litellm.drop_params = True   # Drop unsupported parameters
        litellm.default_fallbacks = ["openai/gpt-4o-mini"]  # Default fallback

    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        available_models = []

        # Check which models are available based on API keys
        if os.getenv("GROQ_API_KEY"):
            available_models.extend(self.primary_models)

        if os.getenv("ANTHROPIC_API_KEY"):
            available_models.extend(self.fallback_models)

        if os.getenv("OPENAI_API_KEY"):
            available_models.extend(self.emergency_models)

        if os.getenv("GOOGLE_API_KEY"):
            available_models.append("google/gemini-1.5-pro")

        return available_models

    async def call_llm_with_model(self, prompt: str, model: str, max_tokens: int = None, temperature: float = 0.7) -> Tuple[str, float]:
        """
        Call LLM with specific model using LiteLLM

        This replaces ~50 lines of custom provider-specific code with LiteLLM's unified interface
        """
        if not self.cost_tracker.check_budget():
            raise Exception(f"Daily budget limit reached. Remaining: ${self.cost_tracker.get_remaining_budget():.2f}")

        try:
            # Prepare message
            messages = [{"role": "user", "content": prompt}]

            # Set default max_tokens if not provided
            if max_tokens is None:
                max_tokens = 4000

            # Call LiteLLM (async)
            response = await acompletion(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=30  # 30 second timeout
            )

            # Extract response text
            result = response.choices[0].message.content

            # Extract usage information for cost tracking
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0

            # Calculate cost using LiteLLM's cost calculation
            try:
                cost = litellm.completion_cost(completion_response=response)
            except:
                # Fallback cost estimation
                cost = (input_tokens * 0.001 + output_tokens * 0.002) / 1000  # Very rough estimate

            # Record usage
            self.cost_tracker.record_usage(model, cost, input_tokens, output_tokens)

            logger.info(f"LLM call successful: {model}, cost: ${cost:.4f}, tokens: {input_tokens}+{output_tokens}")

            return result, cost

        except Exception as e:
            logger.warning(f"LLM call failed for {model}: {e}")
            raise

    async def call_llm(self, prompt: str, model: str = None, max_tokens: int = None, temperature: float = 0.7) -> str:
        """
        Call LLM with automatic fallback support

        This replaces the custom fallback logic with LiteLLM's built-in capabilities
        """
        # Determine models to try
        if model and model in self.get_available_models():
            models_to_try = [model] + [m for m in self.fallback_chain if m != model]
        else:
            models_to_try = self.fallback_chain

        # Filter to only available models
        available_models = self.get_available_models()
        models_to_try = [m for m in models_to_try if m in available_models]

        if not models_to_try:
            raise Exception("No LLM models available. Please check API keys.")

        last_error = None

        for model_to_try in models_to_try:
            try:
                result, cost = await self.call_llm_with_model(
                    prompt=prompt,
                    model=model_to_try,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return result

            except Exception as e:
                last_error = e
                logger.warning(f"Model {model_to_try} failed: {e}")
                continue

        # If we get here, all models failed
        raise Exception(f"All LLM models failed. Last error: {last_error}")

    async def test_model(self, model: str, test_prompt: str = "Hello! Please respond with 'Test successful.'") -> Dict[str, Any]:
        """
        Test a specific model

        This replaces the custom model testing logic
        """
        try:
            start_time = datetime.now()
            result, cost = await self.call_llm_with_model(
                prompt=test_prompt,
                model=model,
                max_tokens=100
            )
            end_time = datetime.now()

            response_time = (end_time - start_time).total_seconds()

            return {
                "success": True,
                "model": model,
                "response": result,
                "cost": cost,
                "response_time": response_time,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            return {
                "success": False,
                "model": model,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def get_cost_stats(self) -> Dict[str, Any]:
        """Get cost statistics"""
        return self.cost_tracker.get_stats()

    def get_model_pricing(self) -> Dict[str, Any]:
        """
        Get model pricing information using LiteLLM

        This replaces the manual pricing configuration
        """
        pricing_info = {}

        for model in self.get_available_models():
            try:
                # Get pricing info from LiteLLM
                model_info = litellm.get_model_info(model)
                pricing_info[model] = {
                    "input_cost_per_token": model_info.get("input_cost_per_token", "Unknown"),
                    "output_cost_per_token": model_info.get("output_cost_per_token", "Unknown"),
                    "max_tokens": model_info.get("max_tokens", "Unknown")
                }
            except:
                pricing_info[model] = {
                    "input_cost_per_token": "Unknown",
                    "output_cost_per_token": "Unknown",
                    "max_tokens": "Unknown"
                }

        return pricing_info

# Compatibility wrapper for easy migration
class LiteLLMService(EnhancedLLMService):
    """
    Alias for enhanced LLM service to maintain naming consistency
    """
    pass

# Factory function to create the enhanced service
def create_enhanced_llm_service(daily_budget: float = 10.0):
    """
    Factory function to create an enhanced LLM service
    """
    return EnhancedLLMService(daily_budget)