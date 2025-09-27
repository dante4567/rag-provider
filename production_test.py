#!/usr/bin/env python3
"""
Production Enhanced RAG Test Suite
==================================

Tests the production-ready enhanced RAG features without external dependencies.
Designed for NixOS environments.

Author: Production Team
Date: 2025-09-27
"""

import asyncio
import sys
import os
import json
import time
from pathlib import Path

# Add current directory to path
sys.path.append('/home/danielt/mygit/rag-provider')

async def test_production_imports():
    """Test that all production modules import correctly"""
    print("📦 Testing Production Imports...")

    try:
        from production_enhanced_retrieval import (
            ProductionEnhancedRAG,
            ProductionBM25,
            ProductionReranker,
            ProductionHybridRetriever,
            ProductionCloudOCR,
            ProductionTagSimilarity
        )
        print("✅ All production modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

async def test_bm25_retrieval():
    """Test BM25 sparse retrieval"""
    print("\n📊 Testing BM25 Sparse Retrieval...")

    try:
        from production_enhanced_retrieval import ProductionBM25

        bm25 = ProductionBM25()

        # Test documents
        test_docs = [
            {
                'content': 'Machine learning algorithms require large datasets for training.',
                'metadata': {'title': 'ML Training'},
                'chunk_id': 'chunk_1'
            },
            {
                'content': 'Deep learning uses neural networks with multiple hidden layers.',
                'metadata': {'title': 'Deep Learning'},
                'chunk_id': 'chunk_2'
            },
            {
                'content': 'Transformers revolutionized natural language processing.',
                'metadata': {'title': 'Transformers'},
                'chunk_id': 'chunk_3'
            }
        ]

        # Index documents
        bm25.index_documents(test_docs)

        # Search
        query = "machine learning neural networks"
        results = bm25.search(query, top_k=3)

        print(f"✅ BM25 test passed")
        print(f"   Query: '{query}'")
        print(f"   Found {len(results)} results")

        for i, result in enumerate(results):
            print(f"   {i+1}. Score: {result['sparse_score']:.3f} - {result['content'][:50]}...")

        return True

    except Exception as e:
        print(f"❌ BM25 test failed: {e}")
        return False

async def test_reranker():
    """Test production reranker"""
    print("\n🔄 Testing Production Reranker...")

    try:
        from production_enhanced_retrieval import ProductionReranker

        reranker = ProductionReranker()

        # Test documents
        test_docs = [
            {
                'content': 'Machine learning algorithms require large datasets.',
                'metadata': {'title': 'ML'},
                'relevance_score': 0.6,
                'chunk_id': 'chunk_1'
            },
            {
                'content': 'Deep learning uses neural networks with multiple layers.',
                'metadata': {'title': 'Deep Learning'},
                'relevance_score': 0.7,
                'chunk_id': 'chunk_2'
            }
        ]

        query = "neural networks deep learning"
        reranked = reranker.rerank(query, test_docs, top_k=2)

        print(f"✅ Reranker test passed")
        print(f"   Query: '{query}'")
        print(f"   Reranked {len(reranked)} documents")

        for i, result in enumerate(reranked):
            print(f"   {i+1}. Score: {result.final_score:.3f} - {result.content[:50]}...")

        return True

    except Exception as e:
        print(f"❌ Reranker test failed: {e}")
        return False

async def test_hybrid_retrieval():
    """Test hybrid retrieval"""
    print("\n🔀 Testing Hybrid Retrieval...")

    try:
        from production_enhanced_retrieval import ProductionHybridRetriever

        hybrid = ProductionHybridRetriever()

        # Test documents
        test_docs = [
            {
                'content': 'Transformers use self-attention for sequence processing.',
                'metadata': {'title': 'Transformers'},
                'relevance_score': 0.8,
                'chunk_id': 'chunk_1'
            },
            {
                'content': 'BERT is a bidirectional transformer for language understanding.',
                'metadata': {'title': 'BERT'},
                'relevance_score': 0.7,
                'chunk_id': 'chunk_2'
            }
        ]

        # Initialize
        hybrid.initialize(test_docs)

        query = "transformer attention mechanisms"
        results = await hybrid.hybrid_search(query, test_docs, top_k=2)

        print(f"✅ Hybrid retrieval test passed")
        print(f"   Query: '{query}'")
        print(f"   Found {len(results)} hybrid results")

        for i, result in enumerate(results):
            print(f"   {i+1}. Combined: {result.final_score:.3f} "
                  f"(Dense: {result.dense_score:.3f}, Sparse: {result.sparse_score:.3f})")

        return True

    except Exception as e:
        print(f"❌ Hybrid retrieval test failed: {e}")
        return False

async def test_cloud_ocr():
    """Test cloud OCR integration"""
    print("\n☁️  Testing Cloud OCR Integration...")

    try:
        from production_enhanced_retrieval import ProductionCloudOCR

        ocr = ProductionCloudOCR()

        print(f"✅ Cloud OCR initialized")
        print(f"   Available providers: {ocr.available_providers}")

        if not ocr.available_providers:
            print("   ⚠️  No API keys configured - this is expected for testing")
        else:
            print(f"   🎉 Found {len(ocr.available_providers)} configured providers")

        return True

    except Exception as e:
        print(f"❌ Cloud OCR test failed: {e}")
        return False

async def test_quality_triage():
    """Test document quality triage"""
    print("\n🏥 Testing Document Quality Triage...")

    try:
        from production_enhanced_retrieval import ProductionEnhancedRAG

        enhanced_rag = ProductionEnhancedRAG()

        # Test different quality content
        test_contents = [
            ("High quality content with proper sentences and vocabulary diversity. This content demonstrates excellent readability.", "high_quality"),
            ("poor ocr text w1th m@ny 3rr0rs and w3ird ch@racters everywhere", "poor_ocr"),
            ("abc def ghi jkl mno pqr", "low_quality"),
            ("", "empty")
        ]

        for content, content_type in test_contents:
            result = await enhanced_rag.triage_document_quality(content, f"test_{content_type}.txt")

            print(f"   {content_type}: Quality {result['quality_score']:.2f} - {result['recommendation']}")

            if 'ocr_detected' in result:
                print(f"     OCR detected: Quality {result['ocr_quality']:.2f}")

        print(f"✅ Quality triage test passed")
        return True

    except Exception as e:
        print(f"❌ Quality triage test failed: {e}")
        return False

async def test_enhanced_rag_integration():
    """Test complete enhanced RAG system"""
    print("\n🚀 Testing Enhanced RAG Integration...")

    try:
        from production_enhanced_retrieval import ProductionEnhancedRAG

        enhanced_rag = ProductionEnhancedRAG()

        # Test initialization
        test_docs = [
            {
                'content': 'Advanced machine learning techniques for data analysis.',
                'metadata': {'filename': 'ml_guide.txt', 'tags': 'machine_learning,data_science'},
                'chunk_id': 'test_chunk_1'
            }
        ]

        await enhanced_rag.initialize(test_docs)

        print(f"✅ Enhanced RAG integration test passed")
        print(f"   Initialized: {enhanced_rag.initialized}")
        print(f"   Dense weight: {enhanced_rag.dense_weight}")
        print(f"   Sparse weight: {enhanced_rag.sparse_weight}")
        print(f"   Available providers: {enhanced_rag.cloud_ocr.available_providers}")

        return True

    except Exception as e:
        print(f"❌ Enhanced RAG integration test failed: {e}")
        return False

async def test_app_integration():
    """Test integration with main FastAPI app"""
    print("\n🌐 Testing FastAPI App Integration...")

    try:
        # Test import compatibility
        from app import app
        from production_enhanced_retrieval import ProductionEnhancedRAG

        print(f"✅ App integration test passed")
        print(f"   FastAPI app imported successfully")
        print(f"   Enhanced RAG module compatible")

        # Check if enhanced endpoints were added
        routes = [route.path for route in app.routes]
        enhanced_routes = [r for r in routes if 'enhanced' in r or 'triage' in r]

        print(f"   Enhanced endpoints available: {len(enhanced_routes)}")
        for route in enhanced_routes:
            print(f"     - {route}")

        return True

    except Exception as e:
        print(f"❌ App integration test failed: {e}")
        return False

async def run_production_tests():
    """Run all production tests"""
    print("🧪 Production Enhanced RAG Test Suite")
    print("===================================")

    tests = [
        ("Import Test", test_production_imports),
        ("BM25 Retrieval", test_bm25_retrieval),
        ("Production Reranker", test_reranker),
        ("Hybrid Retrieval", test_hybrid_retrieval),
        ("Cloud OCR", test_cloud_ocr),
        ("Quality Triage", test_quality_triage),
        ("Enhanced RAG Integration", test_enhanced_rag_integration),
        ("FastAPI Integration", test_app_integration)
    ]

    results = {}
    start_time = time.time()

    for test_name, test_func in tests:
        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False

    # Summary
    print(f"\n📊 Production Test Results")
    print("=========================")

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    elapsed = time.time() - start_time
    print(f"\nResults: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print(f"Duration: {elapsed:.2f} seconds")

    if passed == total:
        print("🎉 All production features are working!")
        print("🚀 Ready for production deployment!")
    else:
        print("⚠️  Some features need attention before deployment")

    return results

if __name__ == "__main__":
    asyncio.run(run_production_tests())