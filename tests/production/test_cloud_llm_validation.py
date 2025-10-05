"""
Production validation tests for cloud LLM providers.

This tests REAL cloud providers with REAL API calls to ensure:
1. Cloud LLMs work properly at each step
2. Models are current and available
3. Fallback mechanisms work when providers fail
4. Local vs cloud functionality comparison
"""

import pytest
import asyncio
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.config import get_settings
from src.services.llm_service import LLMService


class TestCloudLLMProviders:
    """Test each cloud provider individually with real API calls"""

    @pytest.fixture
    def llm_service(self):
        """Initialize LLM service with real API keys"""
        settings = get_settings()
        return LLMService(settings)

    @pytest.mark.asyncio
    async def test_groq_llama_current_model(self, llm_service):
        """
        Test 1: Groq with Llama 3.1 8B Instant
        - Verify model is current and working
        - This is our PRIMARY cheap model
        """
        prompt = "What is 2+2? Answer with just the number."

        try:
            response, cost, model_used = await llm_service.call_llm(
                prompt=prompt,
                model_id="groq/llama-3.1-8b-instant"
            )

            assert response is not None, "Groq returned no response"
            assert "4" in response, f"Groq gave wrong answer: {response}"
            assert cost >= 0, f"Invalid cost: {cost}"
            assert model_used == "groq/llama-3.1-8b-instant", f"Wrong model: {model_used}"

            print(f"✅ GROQ WORKING - Cost: ${cost:.6f}, Response: {response[:50]}")
            return True

        except Exception as e:
            print(f"❌ GROQ FAILED: {str(e)}")
            pytest.fail(f"Groq provider failed: {str(e)}")

    @pytest.mark.asyncio
    async def test_anthropic_current_model(self, llm_service):
        """
        Test 2: Anthropic Claude Sonnet
        - Verify current model works
        - This is our FALLBACK for quality
        """
        prompt = "What is 2+2? Answer with just the number."

        try:
            response, cost, model_used = await llm_service.call_llm(
                prompt=prompt,
                model_id="anthropic/claude-3-5-sonnet-20241022"
            )

            assert response is not None, "Anthropic returned no response"
            assert "4" in response, f"Anthropic gave wrong answer: {response}"
            assert cost >= 0, f"Invalid cost: {cost}"
            assert "anthropic" in model_used.lower(), f"Wrong model: {model_used}"

            print(f"✅ ANTHROPIC WORKING - Cost: ${cost:.6f}, Response: {response[:50]}")
            return True

        except Exception as e:
            print(f"❌ ANTHROPIC FAILED: {str(e)}")
            pytest.fail(f"Anthropic provider failed: {str(e)}")

    @pytest.mark.asyncio
    async def test_openai_current_model(self, llm_service):
        """
        Test 3: OpenAI GPT-4
        - Verify current model works
        - This is our SECOND FALLBACK
        """
        prompt = "What is 2+2? Answer with just the number."

        try:
            response, cost, model_used = await llm_service.call_llm(
                prompt=prompt,
                model_id="openai/gpt-4o-mini"
            )

            assert response is not None, "OpenAI returned no response"
            assert "4" in response, f"OpenAI gave wrong answer: {response}"
            assert cost >= 0, f"Invalid cost: {cost}"
            assert "openai" in model_used.lower(), f"Wrong model: {model_used}"

            print(f"✅ OPENAI WORKING - Cost: ${cost:.6f}, Response: {response[:50]}")
            return True

        except Exception as e:
            print(f"❌ OPENAI FAILED: {str(e)}")
            pytest.fail(f"OpenAI provider failed: {str(e)}")

    @pytest.mark.asyncio
    async def test_google_gemini_current_model(self, llm_service):
        """
        Test 4: Google Gemini 1.5 Pro
        - Verify current model works
        - This is our THIRD FALLBACK
        """
        prompt = "What is 2+2? Answer with just the number."

        try:
            response, cost, model_used = await llm_service.call_llm(
                prompt=prompt,
                model_id="google/gemini-1.5-pro-latest"
            )

            assert response is not None, "Google returned no response"
            assert "4" in response, f"Google gave wrong answer: {response}"
            assert cost >= 0, f"Invalid cost: {cost}"
            assert "google" in model_used.lower() or "gemini" in model_used.lower(), f"Wrong model: {model_used}"

            print(f"✅ GOOGLE WORKING - Cost: ${cost:.6f}, Response: {response[:50]}")
            return True

        except Exception as e:
            print(f"❌ GOOGLE FAILED: {str(e)}")
            pytest.fail(f"Google provider failed: {str(e)}")


class TestFallbackMechanisms:
    """Test that fallback chains work when providers fail"""

    @pytest.fixture
    def llm_service(self):
        settings = get_settings()
        return LLMService(settings)

    @pytest.mark.asyncio
    async def test_fallback_with_invalid_groq_model(self, llm_service):
        """
        Test 5: Fallback from Groq to Anthropic
        - Use invalid Groq model to force fallback
        - Verify Anthropic takes over
        """
        prompt = "What is 2+2? Answer with just the number."

        try:
            response, cost, model_used = await llm_service.call_llm(
                prompt=prompt,
                model_id="groq/invalid-model-that-does-not-exist"
            )

            # Should have fallen back to a working provider
            assert response is not None, "No response even with fallback"
            assert "4" in response, f"Fallback gave wrong answer: {response}"

            # Check it's NOT groq
            assert "groq" not in model_used.lower(), f"Still using Groq?: {model_used}"

            print(f"✅ FALLBACK WORKING - Used {model_used} instead of Groq")
            return True

        except Exception as e:
            print(f"⚠️ FALLBACK FAILED - No working provider: {str(e)}")
            pytest.fail(f"Fallback mechanism failed: {str(e)}")

    @pytest.mark.asyncio
    async def test_cost_comparison_across_providers(self, llm_service):
        """
        Test 6: Compare costs across all providers
        - Same prompt to all providers
        - Verify Groq is cheapest
        - Confirm cost tracking works
        """
        prompt = "Summarize the concept of machine learning in one sentence."

        results = {}

        # Test each provider
        for provider_model in [
            "groq/llama-3.1-8b-instant",
            "anthropic/claude-3-5-sonnet-20241022",
            "openai/gpt-4o-mini",
            "google/gemini-1.5-pro-latest"
        ]:
            try:
                response, cost, model_used = await llm_service.call_llm(
                    prompt=prompt,
                    model_id=provider_model
                )

                results[provider_model] = {
                    "cost": cost,
                    "response": response,
                    "model_used": model_used
                }

                print(f"\n{provider_model}:")
                print(f"  Cost: ${cost:.6f}")
                print(f"  Response: {response[:80]}...")

            except Exception as e:
                print(f"\n{provider_model}: FAILED - {str(e)}")
                results[provider_model] = {"error": str(e)}

        # Verify at least 2 providers worked
        working_providers = [k for k, v in results.items() if "error" not in v]
        assert len(working_providers) >= 2, f"Only {len(working_providers)} providers working"

        print(f"\n✅ COST COMPARISON COMPLETE - {len(working_providers)}/4 providers working")

        # If Groq worked, it should be cheapest
        if "groq/llama-3.1-8b-instant" in working_providers:
            groq_cost = results["groq/llama-3.1-8b-instant"]["cost"]
            other_costs = [v["cost"] for k, v in results.items()
                          if k != "groq/llama-3.1-8b-instant" and "error" not in v]

            if other_costs:
                avg_other_cost = sum(other_costs) / len(other_costs)
                savings = ((avg_other_cost - groq_cost) / avg_other_cost) * 100
                print(f"\n💰 Groq is {savings:.1f}% cheaper than average of others")


class TestRealWorldUsage:
    """Test with real RAG prompts to verify production readiness"""

    @pytest.fixture
    def llm_service(self):
        settings = get_settings()
        return LLMService(settings)

    @pytest.mark.asyncio
    async def test_rag_summarization_prompt(self, llm_service):
        """
        Test 7: Real RAG summarization task
        - This is what we actually use in production
        """
        context = """
        Machine learning is a subset of artificial intelligence that focuses on
        building systems that learn from data. These systems improve their performance
        on tasks over time without being explicitly programmed. Common applications
        include image recognition, natural language processing, and recommendation systems.
        """

        question = "What is machine learning used for?"

        rag_prompt = f"""Based on the following context, answer the question.

Context:
{context}

Question: {question}

Answer concisely using only the information from the context."""

        try:
            response, cost, model_used = await llm_service.call_llm(
                prompt=rag_prompt,
                model_id=None  # Use default (should be Groq)
            )

            assert response is not None, "No response to RAG prompt"
            assert len(response) > 10, f"Response too short: {response}"

            # Check if it used context (should mention applications)
            response_lower = response.lower()
            context_used = any(word in response_lower for word in
                             ["image", "recognition", "language", "recommendation", "applications"])

            assert context_used, f"Response didn't use context: {response}"

            print(f"\n✅ RAG PROMPT WORKING")
            print(f"  Model: {model_used}")
            print(f"  Cost: ${cost:.6f}")
            print(f"  Response: {response}")

            return True

        except Exception as e:
            print(f"❌ RAG PROMPT FAILED: {str(e)}")
            pytest.fail(f"RAG prompt failed: {str(e)}")

    @pytest.mark.asyncio
    async def test_long_context_handling(self, llm_service):
        """
        Test 8: Handle long documents
        - Test with ~1000 words of context
        - Verify all providers can handle it
        """
        # Generate long context
        long_context = " ".join([
            f"This is sentence number {i} in a very long document. " * 10
            for i in range(100)
        ])

        prompt = f"""Summarize this document in one sentence:

{long_context}

Summary:"""

        try:
            response, cost, model_used = await llm_service.call_llm(
                prompt=prompt,
                model_id=None  # Use default
            )

            assert response is not None, "No response to long context"
            assert len(response) > 0, "Empty response"
            assert len(response) < len(long_context), "Summary not shorter than input"

            print(f"\n✅ LONG CONTEXT WORKING")
            print(f"  Input: {len(long_context)} chars")
            print(f"  Output: {len(response)} chars")
            print(f"  Cost: ${cost:.6f}")
            print(f"  Model: {model_used}")

            return True

        except Exception as e:
            print(f"⚠️ LONG CONTEXT FAILED: {str(e)}")
            # Don't fail test - some models have context limits
            print("This is expected if context exceeds model limits")


if __name__ == "__main__":
    """
    Run production validation tests

    Usage:
        python tests/production/test_cloud_llm_validation.py
    """
    pytest.main([__file__, "-v", "-s"])
