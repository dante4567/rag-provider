#!/usr/bin/env python3
"""
Direct test of LLM functionality with different providers for enriching, embeddings, retrieval
"""

import asyncio
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_litellm_providers():
    """Test different LLM providers for various RAG pipeline tasks"""
    logger.info("🚀 Testing LLM Providers for RAG Pipeline Components")
    logger.info("=" * 80)

    try:
        import litellm
        from litellm import completion, acompletion

        # Test scenarios for different RAG pipeline components
        test_scenarios = {
            "enriching": {
                "prompt": "Enrich this document excerpt with relevant context: 'Machine learning algorithms can improve prediction accuracy.'",
                "description": "Testing document enrichment capabilities"
            },
            "retrieval": {
                "prompt": "Given this query: 'What are the benefits of machine learning?', generate 3 alternative search queries that would help retrieve relevant documents.",
                "description": "Testing query expansion for retrieval"
            },
            "reranking": {
                "prompt": "Rank these documents by relevance to 'machine learning applications': 1) 'Deep learning in healthcare' 2) 'Weather prediction models' 3) 'Neural networks for image recognition'. Explain your ranking.",
                "description": "Testing reranking capabilities"
            },
            "summarization": {
                "prompt": "Summarize this technical content in 2 sentences: 'Transformer architectures have revolutionized natural language processing by enabling better context understanding through self-attention mechanisms.'",
                "description": "Testing summarization for RAG responses"
            }
        }

        # Available models to test (using free tier models)
        test_models = [
            "groq/llama-3.1-8b-instant",
            # "anthropic/claude-3-haiku-20240307",  # Requires API key
            # "openai/gpt-4o-mini",  # Requires API key
        ]

        results = {}

        for model in test_models:
            logger.info(f"\n🤖 Testing model: {model}")
            results[model] = {}

            for task, scenario in test_scenarios.items():
                logger.info(f"  📋 {scenario['description']}")
                try:
                    response = await acompletion(
                        model=model,
                        messages=[{"role": "user", "content": scenario["prompt"]}],
                        max_tokens=200,
                        temperature=0.7,
                        timeout=30
                    )

                    result = response.choices[0].message.content.strip()
                    cost = litellm.completion_cost(completion_response=response) if hasattr(litellm, 'completion_cost') else 0.0

                    results[model][task] = {
                        "success": True,
                        "response": result[:100] + "..." if len(result) > 100 else result,
                        "cost": cost,
                        "tokens": response.usage.total_tokens if response.usage else 0
                    }

                    logger.info(f"     ✅ Success: {result[:50]}... (${cost:.6f}, {response.usage.total_tokens if response.usage else 0} tokens)")

                except Exception as e:
                    logger.error(f"     ❌ Failed: {str(e)}")
                    results[model][task] = {
                        "success": False,
                        "error": str(e),
                        "cost": 0.0,
                        "tokens": 0
                    }

        # Test embeddings if available
        logger.info(f"\n🔍 Testing embeddings capabilities")
        try:
            # Test if we can get embeddings using LiteLLM
            embedding_response = await acompletion(
                model="text-embedding-ada-002",  # OpenAI embedding model
                messages=[{"role": "user", "content": "This is a test document for embedding generation."}],
                timeout=30
            )
            logger.info("     ✅ Embeddings: Available through LiteLLM")
        except Exception as e:
            logger.info(f"     ℹ️ Embeddings: Not available ({str(e)[:50]}...)")

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("📊 TESTING SUMMARY")
        logger.info("=" * 80)

        total_tests = 0
        successful_tests = 0
        total_cost = 0.0

        for model, tasks in results.items():
            logger.info(f"\n🤖 {model}:")
            for task, result in tasks.items():
                total_tests += 1
                if result["success"]:
                    successful_tests += 1
                    total_cost += result["cost"]
                    logger.info(f"   ✅ {task}: Success (${result['cost']:.6f})")
                else:
                    logger.info(f"   ❌ {task}: Failed")

        logger.info(f"\n📈 Overall Results:")
        logger.info(f"   Tests passed: {successful_tests}/{total_tests}")
        logger.info(f"   Success rate: {(successful_tests/total_tests)*100:.1f}%")
        logger.info(f"   Total cost: ${total_cost:.6f}")

        # Check for reranking capabilities
        logger.info(f"\n🔄 Reranking Analysis:")
        if any(task.get("reranking", {}).get("success", False) for task in results.values()):
            logger.info("   ✅ LLM-based reranking: Available (using LLM reasoning)")
        logger.info("   ℹ️ Advanced reranking: Would require additional libraries (e.g., sentence-transformers)")

        return {
            "success": successful_tests > 0,
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "total_cost": total_cost,
            "results": results
        }

    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return {"success": False, "error": f"Import error: {e}"}
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return {"success": False, "error": f"Test failed: {e}"}

async def test_embedding_approaches():
    """Test different approaches for embeddings in RAG"""
    logger.info("\n🔍 Testing Embedding Approaches for RAG")
    logger.info("=" * 60)

    embedding_strategies = {
        "chromadb_default": "Using ChromaDB's default embedding function",
        "openai_embeddings": "Using OpenAI ada-002 embeddings via LiteLLM",
        "sentence_transformers": "Using sentence-transformers (if available)",
        "custom_embeddings": "Custom embedding implementation"
    }

    for strategy, description in embedding_strategies.items():
        logger.info(f"📋 {strategy}: {description}")
        if strategy == "chromadb_default":
            logger.info("   ✅ Available (already integrated in ChromaDB)")
        elif strategy == "openai_embeddings":
            logger.info("   ⚠️ Requires OpenAI API key")
        elif strategy == "sentence_transformers":
            try:
                import sentence_transformers
                logger.info("   ✅ Available (install sentence-transformers)")
            except ImportError:
                logger.info("   ❌ Not installed (pip install sentence-transformers)")
        elif strategy == "custom_embeddings":
            logger.info("   ✅ Possible with custom implementation")

if __name__ == "__main__":
    async def main():
        logger.info("🚀 Starting LLM Provider Testing for RAG Pipeline")

        # Check environment
        api_keys = ["GROQ_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"]
        available_keys = []
        for key in api_keys:
            if os.getenv(key):
                available_keys.append(key)
                logger.info(f"   ✅ {key}: Available")
            else:
                logger.info(f"   ❌ {key}: Not set")

        if not available_keys:
            logger.warning("⚠️ No API keys available - limited testing possible")

        # Run tests
        result1 = await test_litellm_providers()
        await test_embedding_approaches()

        # Final verdict
        if result1["success"]:
            logger.info("\n🎉 LLM provider testing successful!")
            return 0
        else:
            logger.error("\n❌ LLM provider testing failed")
            return 1

    exit_code = asyncio.run(main())
    sys.exit(exit_code)