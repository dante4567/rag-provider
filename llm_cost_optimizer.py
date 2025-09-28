#!/usr/bin/env python3
"""
LLM Cost Optimizer and Cloud Provider Manager

This service optimizes LLM costs by:
- Smart provider selection based on task complexity
- Automatic fallback chains with cost considerations
- Budget tracking and alerting
- Performance vs cost optimization
"""

import asyncio
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class TaskComplexity(Enum):
    SIMPLE = "simple"        # Basic summarization, simple Q&A
    MEDIUM = "medium"        # Entity extraction, classification
    COMPLEX = "complex"      # Deep analysis, reasoning
    PREMIUM = "premium"      # Critical tasks requiring best quality

@dataclass
class LLMProvider:
    name: str
    model: str
    input_cost_per_1m: float   # USD per 1M input tokens
    output_cost_per_1m: float  # USD per 1M output tokens
    max_tokens: int
    speed_rating: int          # 1-5, higher is faster
    quality_rating: int        # 1-5, higher is better
    reliability_rating: int    # 1-5, higher is more reliable

class LLMCostOptimizer:
    """
    Intelligent LLM provider selection with cost optimization
    """

    def __init__(self, daily_budget: float = 10.0):
        self.daily_budget = daily_budget
        self.daily_usage = 0.0

        # Define provider catalog with real-world pricing
        self.providers = {
            # Ultra-cheap options (for bulk processing)
            "groq_fast": LLMProvider(
                name="Groq",
                model="groq/llama-3.1-8b-instant",
                input_cost_per_1m=0.05,
                output_cost_per_1m=0.08,
                max_tokens=8192,
                speed_rating=5,  # Fastest
                quality_rating=3,
                reliability_rating=4
            ),

            "groq_large": LLMProvider(
                name="Groq",
                model="groq/llama3-70b-8192",
                input_cost_per_1m=0.59,
                output_cost_per_1m=0.79,
                max_tokens=8192,
                speed_rating=4,
                quality_rating=4,
                reliability_rating=4
            ),

            # Balanced options
            "anthropic_haiku": LLMProvider(
                name="Anthropic",
                model="anthropic/claude-3-haiku-20240307",
                input_cost_per_1m=0.25,
                output_cost_per_1m=1.25,
                max_tokens=200000,
                speed_rating=4,
                quality_rating=4,
                reliability_rating=5
            ),

            "openai_mini": LLMProvider(
                name="OpenAI",
                model="openai/gpt-4o-mini",
                input_cost_per_1m=0.15,
                output_cost_per_1m=0.60,
                max_tokens=128000,
                speed_rating=3,
                quality_rating=4,
                reliability_rating=5
            ),

            # Premium options
            "anthropic_sonnet": LLMProvider(
                name="Anthropic",
                model="anthropic/claude-3-5-sonnet-20241022",
                input_cost_per_1m=3.00,
                output_cost_per_1m=15.00,
                max_tokens=200000,
                speed_rating=3,
                quality_rating=5,
                reliability_rating=5
            ),

            "openai_gpt4": LLMProvider(
                name="OpenAI",
                model="openai/gpt-4o",
                input_cost_per_1m=5.00,
                output_cost_per_1m=15.00,
                max_tokens=128000,
                speed_rating=2,
                quality_rating=5,
                reliability_rating=5
            ),

            # Long context option
            "google_gemini": LLMProvider(
                name="Google",
                model="google/gemini-1.5-pro",
                input_cost_per_1m=1.25,
                output_cost_per_1m=5.00,
                max_tokens=2000000,  # 2M context!
                speed_rating=2,
                quality_rating=4,
                reliability_rating=4
            )
        }

        # Task-based optimization strategies
        self.optimization_strategies = {
            TaskComplexity.SIMPLE: {
                "primary": "groq_fast",
                "fallback": "anthropic_haiku",
                "emergency": "openai_mini",
                "max_cost_per_call": 0.01  # 1 cent max
            },
            TaskComplexity.MEDIUM: {
                "primary": "groq_large",
                "fallback": "anthropic_haiku",
                "emergency": "openai_mini",
                "max_cost_per_call": 0.05  # 5 cents max
            },
            TaskComplexity.COMPLEX: {
                "primary": "anthropic_haiku",
                "fallback": "anthropic_sonnet",
                "emergency": "openai_gpt4",
                "max_cost_per_call": 0.25  # 25 cents max
            },
            TaskComplexity.PREMIUM: {
                "primary": "anthropic_sonnet",
                "fallback": "openai_gpt4",
                "emergency": "google_gemini",
                "max_cost_per_call": 1.00  # $1 max
            }
        }

    def select_provider(
        self,
        task_complexity: TaskComplexity,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        force_budget_limit: bool = True
    ) -> Tuple[str, float]:
        """
        Select the optimal provider based on task complexity and budget

        Returns: (provider_model, estimated_cost)
        """

        strategy = self.optimization_strategies[task_complexity]

        # Try providers in order of preference
        for provider_key in ["primary", "fallback", "emergency"]:
            provider_id = strategy[provider_key]
            provider = self.providers[provider_id]

            # Calculate estimated cost
            input_cost = (estimated_input_tokens / 1_000_000) * provider.input_cost_per_1m
            output_cost = (estimated_output_tokens / 1_000_000) * provider.output_cost_per_1m
            total_cost = input_cost + output_cost

            # Check budget constraints
            max_cost = strategy["max_cost_per_call"]
            if force_budget_limit and total_cost > max_cost:
                logger.warning(f"Provider {provider.name} exceeds cost limit: ${total_cost:.4f} > ${max_cost:.4f}")
                continue

            # Check daily budget
            if self.daily_usage + total_cost > self.daily_budget:
                logger.warning(f"Provider {provider.name} would exceed daily budget")
                if provider_key == "emergency":  # Last resort
                    logger.error("All providers exceed budget - using cheapest available")
                    return self._get_cheapest_provider(estimated_input_tokens, estimated_output_tokens)
                continue

            logger.info(f"Selected {provider.name} ({provider.model}) - estimated cost: ${total_cost:.4f}")
            return provider.model, total_cost

        # Fallback to cheapest if all else fails
        return self._get_cheapest_provider(estimated_input_tokens, estimated_output_tokens)

    def _get_cheapest_provider(self, input_tokens: int, output_tokens: int) -> Tuple[str, float]:
        """Get the cheapest available provider"""
        cheapest_cost = float('inf')
        cheapest_model = None

        for provider in self.providers.values():
            input_cost = (input_tokens / 1_000_000) * provider.input_cost_per_1m
            output_cost = (output_tokens / 1_000_000) * provider.output_cost_per_1m
            total_cost = input_cost + output_cost

            if total_cost < cheapest_cost:
                cheapest_cost = total_cost
                cheapest_model = provider.model

        logger.info(f"Using cheapest provider: {cheapest_model} - cost: ${cheapest_cost:.4f}")
        return cheapest_model, cheapest_cost

    def get_cost_breakdown(self) -> Dict[str, any]:
        """Get detailed cost breakdown for all providers"""

        # Sample calculation for 1000 tokens input, 200 tokens output
        sample_input = 1000
        sample_output = 200

        breakdown = {}
        for key, provider in self.providers.items():
            input_cost = (sample_input / 1_000_000) * provider.input_cost_per_1m
            output_cost = (sample_output / 1_000_000) * provider.output_cost_per_1m
            total_cost = input_cost + output_cost

            breakdown[key] = {
                "provider": provider.name,
                "model": provider.model,
                "cost_per_1k_tokens": total_cost * 1000,  # Scale to 1K tokens
                "input_cost_per_1m": provider.input_cost_per_1m,
                "output_cost_per_1m": provider.output_cost_per_1m,
                "speed_rating": provider.speed_rating,
                "quality_rating": provider.quality_rating,
                "reliability_rating": provider.reliability_rating,
                "max_tokens": provider.max_tokens
            }

        return breakdown

    def get_optimization_recommendations(self) -> Dict[str, str]:
        """Get cost optimization recommendations"""

        return {
            "document_enrichment": "Use groq_fast for basic summaries and tags - 80% cheaper than premium options",
            "entity_extraction": "Use groq_large for better accuracy while staying cost-effective",
            "complex_analysis": "Use anthropic_haiku for quality analysis at reasonable cost",
            "critical_tasks": "Reserve anthropic_sonnet/openai_gpt4 for mission-critical work only",
            "long_documents": "Use google_gemini for documents >100K tokens (2M context window)",
            "bulk_processing": "Always use groq_fast for high-volume batch operations",
            "budget_strategy": "Set task-specific cost limits to prevent budget overruns"
        }

    def simulate_monthly_costs(self, usage_scenarios: Dict[str, int]) -> Dict[str, float]:
        """
        Simulate monthly costs for different usage scenarios

        usage_scenarios: {
            "simple_enrichments_per_day": 100,
            "medium_analysis_per_day": 20,
            "complex_analysis_per_day": 5,
            "premium_tasks_per_day": 1
        }
        """

        daily_costs = {}
        monthly_costs = {}

        # Calculate costs for each scenario
        for task_type, count_per_day in usage_scenarios.items():
            if "simple" in task_type:
                complexity = TaskComplexity.SIMPLE
                avg_input_tokens = 1000
                avg_output_tokens = 200
            elif "medium" in task_type:
                complexity = TaskComplexity.MEDIUM
                avg_input_tokens = 2000
                avg_output_tokens = 400
            elif "complex" in task_type:
                complexity = TaskComplexity.COMPLEX
                avg_input_tokens = 4000
                avg_output_tokens = 800
            else:  # premium
                complexity = TaskComplexity.PREMIUM
                avg_input_tokens = 8000
                avg_output_tokens = 1500

            _, cost_per_call = self.select_provider(
                complexity, avg_input_tokens, avg_output_tokens, force_budget_limit=False
            )

            daily_cost = cost_per_call * count_per_day
            monthly_cost = daily_cost * 30

            daily_costs[task_type] = daily_cost
            monthly_costs[task_type] = monthly_cost

        total_daily = sum(daily_costs.values())
        total_monthly = sum(monthly_costs.values())

        return {
            "daily_costs": daily_costs,
            "monthly_costs": monthly_costs,
            "total_daily": total_daily,
            "total_monthly": total_monthly,
            "budget_utilization": (total_daily / self.daily_budget) * 100
        }

    def track_usage(self, actual_cost: float):
        """Track actual usage against budget"""
        self.daily_usage += actual_cost

        utilization = (self.daily_usage / self.daily_budget) * 100

        if utilization > 90:
            logger.warning(f"Daily budget 90% utilized: ${self.daily_usage:.2f}/${self.daily_budget:.2f}")
        elif utilization > 75:
            logger.info(f"Daily budget 75% utilized: ${self.daily_usage:.2f}/${self.daily_budget:.2f}")


def demonstrate_cost_optimization():
    """Demonstrate the cost optimization in action"""

    print("🏢 Cloud LLM Cost Optimization Demo")
    print("=" * 50)

    optimizer = LLMCostOptimizer(daily_budget=10.0)

    # Show cost breakdown
    print("\n💰 Provider Cost Breakdown (per 1K tokens):")
    breakdown = optimizer.get_cost_breakdown()

    for key, info in breakdown.items():
        cost_1k = info["cost_per_1k_tokens"]
        speed = "⚡" * info["speed_rating"]
        quality = "🌟" * info["quality_rating"]
        print(f"  {info['provider']:10} {info['model']:30} ${cost_1k:.6f} {speed:5} {quality}")

    # Show optimization strategies
    print("\n🎯 Task-Based Optimization:")
    for complexity, strategy in optimizer.optimization_strategies.items():
        provider = optimizer.providers[strategy["primary"]]
        print(f"  {complexity.value:8}: {provider.name:10} ({provider.model}) - max ${strategy['max_cost_per_call']}")

    # Simulate usage scenarios
    print("\n📊 Monthly Cost Simulation:")
    scenarios = {
        "simple_enrichments_per_day": 100,   # Document summaries, basic tags
        "medium_analysis_per_day": 20,       # Entity extraction, classification
        "complex_analysis_per_day": 5,       # Deep document analysis
        "premium_tasks_per_day": 1           # Critical business decisions
    }

    costs = optimizer.simulate_monthly_costs(scenarios)

    for task, monthly_cost in costs["monthly_costs"].items():
        print(f"  {task:30}: ${monthly_cost:7.2f}/month")

    print(f"\n  Total Monthly Cost: ${costs['total_monthly']:.2f}")
    print(f"  Budget Utilization: {costs['budget_utilization']:.1f}% of daily budget")

    # Show optimization recommendations
    print("\n💡 Cost Optimization Tips:")
    recommendations = optimizer.get_optimization_recommendations()
    for task, tip in recommendations.items():
        print(f"  • {task}: {tip}")

if __name__ == "__main__":
    demonstrate_cost_optimization()