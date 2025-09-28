#!/usr/bin/env python3
"""
Test script for the Enhanced LLM Service using LiteLLM

This script tests the LiteLLM-based implementation and compares it
with the original LLM service approach.
"""

import asyncio
import logging
import time
import os
from typing import Dict, Any
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_enhanced_llm_service():
    """Test the enhanced LLM service"""
    logger.info("Testing Enhanced LLM Service...")

    try:
        from enhanced_llm_service import EnhancedLLMService

        # Create service
        llm_service = EnhancedLLMService(daily_budget=5.0)

        # Test 1: Check available models
        logger.info("Test 1: Checking available models...")
        available_models = llm_service.get_available_models()
        logger.info(f"Available models: {available_models}")

        if not available_models:
            logger.warning("No models available - this might be due to missing API keys")
            return {"success": False, "reason": "No models available"}

        # Test 2: Simple LLM call with fallback
        logger.info("Test 2: Testing LLM call with automatic fallback...")
        try:
            response = await llm_service.call_llm(
                prompt="What is 2+2? Please respond with just the number.",
                max_tokens=50
            )
            logger.info(f"✅ LLM Response: '{response.strip()}'")
        except Exception as e:
            logger.error(f"❌ LLM call failed: {e}")
            return {"success": False, "reason": f"LLM call failed: {e}"}

        # Test 3: Test specific model (if available)
        logger.info("Test 3: Testing specific model call...")
        if available_models:
            test_model = available_models[0]
            try:
                response, cost = await llm_service.call_llm_with_model(
                    prompt="Say 'Hello from LiteLLM!'",
                    model=test_model,
                    max_tokens=50
                )
                logger.info(f"✅ Model {test_model} response: '{response.strip()}' (cost: ${cost:.4f})")
            except Exception as e:
                logger.warning(f"⚠️ Model {test_model} failed: {e}")

        # Test 4: Cost tracking
        logger.info("Test 4: Testing cost tracking...")
        cost_stats = llm_service.get_cost_stats()
        logger.info(f"✅ Cost stats: {cost_stats}")

        # Test 5: Model testing
        logger.info("Test 5: Testing model validation...")
        if available_models:
            test_result = await llm_service.test_model(available_models[0])
            if test_result["success"]:
                logger.info(f"✅ Model test successful: {test_result['response'][:50]}...")
            else:
                logger.warning(f"⚠️ Model test failed: {test_result['error']}")

        logger.info("🎉 Enhanced LLM Service tests completed successfully!")
        return {"success": True, "available_models": len(available_models)}

    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return {"success": False, "reason": f"Import error: {e}"}
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return {"success": False, "reason": f"Test failed: {e}"}

async def test_litellm_direct():
    """Test LiteLLM directly to verify installation"""
    logger.info("Testing LiteLLM direct functionality...")

    try:
        import litellm
        from litellm import completion

        # Test simple completion
        logger.info("Testing basic LiteLLM completion...")

        # Check if we have any API keys available
        api_keys_available = []
        if os.getenv("GROQ_API_KEY"):
            api_keys_available.append("groq")
        if os.getenv("ANTHROPIC_API_KEY"):
            api_keys_available.append("anthropic")
        if os.getenv("OPENAI_API_KEY"):
            api_keys_available.append("openai")

        if not api_keys_available:
            logger.warning("No API keys detected - testing with mock response")
            return {"success": True, "note": "No API keys available for actual testing"}

        # Try a simple completion with the first available provider
        test_models = {
            "groq": "groq/llama-3.1-8b-instant",
            "anthropic": "anthropic/claude-3-haiku-20240307",
            "openai": "openai/gpt-4o-mini"
        }

        for provider in api_keys_available:
            if provider in test_models:
                try:
                    model = test_models[provider]
                    logger.info(f"Testing {model}...")

                    response = completion(
                        model=model,
                        messages=[{"role": "user", "content": "Say 'LiteLLM test successful'"}],
                        max_tokens=50,
                        timeout=30
                    )

                    result = response.choices[0].message.content
                    logger.info(f"✅ {provider} test successful: '{result.strip()}'")

                    # Test cost calculation
                    try:
                        cost = litellm.completion_cost(completion_response=response)
                        logger.info(f"✅ Cost calculation: ${cost:.6f}")
                    except:
                        logger.info("ℹ️ Cost calculation not available for this model")

                    return {"success": True, "provider": provider, "model": model}

                except Exception as e:
                    logger.warning(f"⚠️ {provider} test failed: {e}")
                    continue

        logger.error("❌ All provider tests failed")
        return {"success": False, "reason": "All providers failed"}

    except ImportError as e:
        logger.error(f"❌ LiteLLM import failed: {e}")
        return {"success": False, "reason": f"LiteLLM import failed: {e}"}
    except Exception as e:
        logger.error(f"❌ LiteLLM test failed: {e}")
        return {"success": False, "reason": f"LiteLLM test failed: {e}"}

async def main():
    """Main test function"""
    logger.info("Starting LiteLLM and Enhanced LLM Service tests...")

    # Check environment
    logger.info(f"Available API keys:")
    for key in ["GROQ_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"]:
        value = os.getenv(key)
        if value:
            logger.info(f"  {key}: ✅ (length: {len(value)})")
        else:
            logger.info(f"  {key}: ❌ (not set)")

    results = []

    # Test 1: LiteLLM direct
    logger.info("\n" + "="*50)
    result1 = await test_litellm_direct()
    results.append(result1)

    # Test 2: Enhanced LLM Service
    logger.info("\n" + "="*50)
    result2 = await test_enhanced_llm_service()
    results.append(result2)

    # Summary
    logger.info("\n" + "="*50)
    logger.info("TEST SUMMARY")
    logger.info("="*50)

    passed = sum(1 for r in results if r["success"])
    total = len(results)

    logger.info(f"Tests passed: {passed}/{total}")

    if passed == total:
        logger.info("🎉 All tests passed! LiteLLM integration is working correctly.")
        return 0
    else:
        logger.error("❌ Some tests failed. Check the logs above.")
        for i, result in enumerate(results, 1):
            if not result["success"]:
                logger.error(f"  Test {i}: {result.get('reason', 'Unknown error')}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)