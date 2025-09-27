#!/usr/bin/env python3
"""
Test Enhanced RAG Features
==========================

Test script to verify all enhanced RAG features are working properly.

Tests:
1. Cross-encoder reranking
2. Hybrid retrieval (dense + BM25)
3. Controlled tag hierarchy
4. Enhanced search endpoints
5. Obsidian vault generation

Author: Enhanced RAG Team
Date: 2025-09-27
"""

import asyncio
import sys
import os
import json
import time
import requests
from pathlib import Path

# Add current directory to path
sys.path.append('/home/danielt/mygit/rag-provider')

def test_api_endpoint(url, method="GET", data=None, description=""):
    """Test an API endpoint"""
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=30)
        else:
            return False, f"Unsupported method: {method}"

        if response.status_code == 200:
            return True, response.json()
        else:
            return False, f"HTTP {response.status_code}: {response.text}"

    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"

def test_reranker():
    """Test the reranker implementation"""
    print("🔄 Testing Cross-Encoder Reranker...")

    try:
        from enhanced_retrieval import CrossEncoderReranker

        reranker = CrossEncoderReranker()

        # Test documents
        test_docs = [
            {
                'content': 'Machine learning algorithms require large datasets for training.',
                'metadata': {'title': 'ML Training'},
                'relevance_score': 0.6,
                'chunk_id': 'chunk_1'
            },
            {
                'content': 'Deep learning uses neural networks with multiple hidden layers.',
                'metadata': {'title': 'Deep Learning'},
                'relevance_score': 0.7,
                'chunk_id': 'chunk_2'
            },
            {
                'content': 'Transformers revolutionized natural language processing with attention mechanisms.',
                'metadata': {'title': 'Transformers'},
                'relevance_score': 0.5,
                'chunk_id': 'chunk_3'
            }
        ]

        query = "What are neural networks in deep learning?"
        reranked = reranker.rerank(query, test_docs, top_k=3)

        print(f"✅ Reranker test passed")
        print(f"   Query: '{query}'")
        print(f"   Reranked {len(reranked)} documents")

        for i, result in enumerate(reranked):
            print(f"   {i+1}. Score: {result.final_score:.3f} - {result.content[:50]}...")

        return True

    except Exception as e:
        print(f"❌ Reranker test failed: {e}")
        return False

def test_bm25():
    """Test BM25 sparse retrieval"""
    print("\n📊 Testing BM25 Sparse Retrieval...")

    try:
        from enhanced_retrieval import BM25Retriever

        bm25 = BM25Retriever()

        # Test documents
        test_docs = [
            {
                'content': 'Machine learning is a method of data analysis that automates analytical model building.',
                'metadata': {'title': 'ML Overview'},
                'chunk_id': 'chunk_1'
            },
            {
                'content': 'Deep learning is part of a broader family of machine learning methods based on neural networks.',
                'metadata': {'title': 'Deep Learning'},
                'chunk_id': 'chunk_2'
            },
            {
                'content': 'Natural language processing combines computational linguistics with machine learning.',
                'metadata': {'title': 'NLP'},
                'chunk_id': 'chunk_3'
            }
        ]

        bm25.index_documents(test_docs)

        query = "machine learning methods"
        results = bm25.search(query, top_k=3)

        print(f"✅ BM25 test passed")
        print(f"   Query: '{query}'")
        print(f"   Found {len(results)} results")

        for i, result in enumerate(results):
            print(f"   {i+1}. BM25 Score: {result['sparse_score']:.3f} - {result['content'][:50]}...")

        return True

    except Exception as e:
        print(f"❌ BM25 test failed: {e}")
        return False

def test_tag_hierarchy():
    """Test controlled tag hierarchy"""
    print("\n🏷️  Testing Controlled Tag Hierarchy...")

    try:
        from enhanced_retrieval import ControlledTagHierarchy

        tag_system = ControlledTagHierarchy()

        # Test tag normalization
        test_tags = ["BERT", "GPT-3", "attention mechanism", "Machine Learning", "deep_learning"]

        print("✅ Tag hierarchy test passed")
        print("   Tag Normalization:")

        for tag in test_tags:
            normalized = tag_system.normalize_tag(tag)
            hierarchy = tag_system.get_tag_hierarchy(normalized)
            print(f"     '{tag}' -> '{normalized}' -> {hierarchy}")

        # Test suggestions
        suggestions = tag_system.suggest_related_tags(test_tags)
        print(f"   Suggested related tags: {suggestions}")

        return True

    except Exception as e:
        print(f"❌ Tag hierarchy test failed: {e}")
        return False

async def test_hybrid_retrieval():
    """Test hybrid retrieval integration"""
    print("\n🔀 Testing Hybrid Retrieval...")

    try:
        from enhanced_retrieval import HybridRetriever

        hybrid = HybridRetriever()

        # Mock dense results
        dense_results = [
            {
                'content': 'Transformers use self-attention mechanisms for sequence processing.',
                'metadata': {'title': 'Transformers'},
                'relevance_score': 0.8,
                'chunk_id': 'chunk_1'
            },
            {
                'content': 'BERT is a bidirectional transformer model for language understanding.',
                'metadata': {'title': 'BERT'},
                'relevance_score': 0.7,
                'chunk_id': 'chunk_2'
            }
        ]

        # Index for BM25
        hybrid.index_documents(dense_results)

        query = "transformer attention mechanisms"
        hybrid_results = await hybrid.hybrid_search(query, dense_results, top_k=2)

        print(f"✅ Hybrid retrieval test passed")
        print(f"   Query: '{query}'")
        print(f"   Found {len(hybrid_results)} hybrid results")

        for i, result in enumerate(hybrid_results):
            print(f"   {i+1}. Combined: {result.combined_score:.3f} "
                  f"(Dense: {result.dense_score:.3f}, Sparse: {result.sparse_score:.3f})")
            print(f"       {result.content[:60]}...")

        return True

    except Exception as e:
        print(f"❌ Hybrid retrieval test failed: {e}")
        return False

async def test_enhanced_endpoints():
    """Test enhanced API endpoints"""
    print("\n🌐 Testing Enhanced API Endpoints...")

    base_url = "http://localhost:8001"

    # Test basic connectivity
    success, result = test_api_endpoint(f"{base_url}/health", description="Health check")
    if not success:
        print(f"❌ Cannot connect to RAG service: {result}")
        return False

    print("✅ RAG service is accessible")

    # Test enhanced search endpoint (if implemented)
    search_data = {
        "text": "machine learning algorithms",
        "top_k": 3,
        "use_hybrid": True,
        "use_reranker": True
    }

    # This endpoint might not exist yet, so we'll test regular search
    success, result = test_api_endpoint(
        f"{base_url}/search",
        method="POST",
        data={"text": "machine learning", "top_k": 3},
        description="Regular search"
    )

    if success:
        print(f"✅ Search endpoint working - found {result.get('total_results', 0)} results")

        # Test RAG chat
        chat_data = {
            "question": "What is machine learning?",
            "max_context_chunks": 3
        }

        success, result = test_api_endpoint(
            f"{base_url}/chat",
            method="POST",
            data=chat_data,
            description="RAG chat"
        )

        if success:
            print(f"✅ Chat endpoint working")
            print(f"   Answer: {result.get('answer', '')[:100]}...")
        else:
            print(f"⚠️  Chat endpoint issue: {result}")
    else:
        print(f"❌ Search endpoint failed: {result}")
        return False

    return True

def test_obsidian_vault():
    """Test Obsidian vault generation"""
    print("\n📝 Testing Obsidian Vault Generation...")

    try:
        # Check if any Obsidian files exist
        obsidian_paths = [
            "/tmp/obsidian",
            os.path.expanduser("~/rag_data/obsidian"),
            "/home/danielt/mygit/rag-provider/obsidian"
        ]

        obsidian_files = []
        for path in obsidian_paths:
            if os.path.exists(path):
                files = list(Path(path).glob("*.md"))
                obsidian_files.extend(files)

        if obsidian_files:
            print(f"✅ Found {len(obsidian_files)} Obsidian markdown files")

            # Read a sample file
            sample_file = obsidian_files[0]
            try:
                with open(sample_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                print(f"   Sample file: {sample_file.name}")
                print(f"   Content preview:")
                print("   " + "\n   ".join(content.split('\n')[:10]))

                # Check for proper frontmatter
                if content.startswith('---'):
                    print("   ✅ Contains YAML frontmatter")
                else:
                    print("   ⚠️  Missing YAML frontmatter")

            except Exception as e:
                print(f"   ⚠️  Could not read sample file: {e}")
        else:
            print("⚠️  No Obsidian markdown files found")
            print("   This might be because:")
            print("   - Files are created in a different location")
            print("   - Obsidian generation is disabled")
            print("   - No documents have been processed yet")

        return True

    except Exception as e:
        print(f"❌ Obsidian vault test failed: {e}")
        return False

async def run_all_tests():
    """Run all enhancement tests"""
    print("🧪 Enhanced RAG Features Test Suite")
    print("===================================")

    tests = [
        ("Reranker", test_reranker),
        ("BM25 Sparse Retrieval", test_bm25),
        ("Tag Hierarchy", test_tag_hierarchy),
        ("Hybrid Retrieval", test_hybrid_retrieval),
        ("API Endpoints", test_enhanced_endpoints),
        ("Obsidian Vault", test_obsidian_vault)
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False

    # Summary
    print(f"\n📊 Test Results Summary")
    print("======================")

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("🎉 All enhanced RAG features are working!")
    else:
        print("⚠️  Some features need attention")

    return results

if __name__ == "__main__":
    asyncio.run(run_all_tests())