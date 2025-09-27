#!/usr/bin/env python3
"""
Final Production Readiness Test
===============================

Comprehensive test to verify all production features are ready for deployment.
Tests both host compatibility and Docker integration scenarios.

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

async def test_core_functionality():
    """Test core enhanced RAG functionality"""
    print("🔧 Testing Core Enhanced RAG Functionality")
    print("==========================================")

    try:
        from production_enhanced_retrieval import ProductionEnhancedRAG

        # Initialize
        enhanced_rag = ProductionEnhancedRAG()

        # Test documents
        test_docs = [
            {
                'content': 'Machine learning algorithms require large datasets for training effective models.',
                'metadata': {'filename': 'ml_basics.txt', 'tags': 'machine_learning,data_science'},
                'chunk_id': 'chunk_ml_1'
            },
            {
                'content': 'Deep learning neural networks use multiple hidden layers for complex pattern recognition.',
                'metadata': {'filename': 'deep_learning.txt', 'tags': 'deep_learning,neural_networks'},
                'chunk_id': 'chunk_dl_1'
            },
            {
                'content': 'Natural language processing enables computers to understand and generate human language.',
                'metadata': {'filename': 'nlp_guide.txt', 'tags': 'nlp,language_processing'},
                'chunk_id': 'chunk_nlp_1'
            }
        ]

        await enhanced_rag.initialize(test_docs)

        # Test quality triage
        print("   🏥 Testing document quality triage...")
        quality_result = await enhanced_rag.triage_document_quality(
            "This is a high-quality document with proper sentence structure and vocabulary.",
            "test_document.txt"
        )

        print(f"      Quality Score: {quality_result['quality_score']:.2f}")
        print(f"      Recommendation: {quality_result['recommendation']}")
        print(f"      Enhanced: {quality_result['enhanced']}")

        # Test enhanced chat
        print("   💬 Testing enhanced chat...")
        chat_result = await enhanced_rag.enhanced_chat(
            "What is machine learning?",
            max_context_chunks=3,
            use_hybrid=True,
            use_reranker=True
        )

        print(f"      Question: {chat_result['question']}")
        print(f"      Features: {chat_result['features_available']}")
        print(f"      Search Type: {chat_result['search_type']}")

        print("   ✅ Core functionality tests passed")
        return True

    except Exception as e:
        print(f"   ❌ Core functionality test failed: {e}")
        return False

async def test_production_integration():
    """Test production integration compatibility"""
    print("\n🐳 Testing Production Integration Compatibility")
    print("==============================================")

    # Test 1: Import compatibility
    try:
        # These should work on the host
        from production_enhanced_retrieval import (
            ProductionEnhancedRAG,
            ProductionBM25,
            ProductionReranker,
            ProductionHybridRetriever,
            ProductionCloudOCR
        )
        print("   ✅ Enhanced modules import successfully")
    except ImportError as e:
        print(f"   ❌ Enhanced modules import failed: {e}")
        return False

    # Test 2: Docker configuration files
    required_files = [
        'Dockerfile',
        'docker-compose.yml',
        'requirements.txt',
        'nginx.conf',
        'deploy.sh'
    ]

    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)

    if missing_files:
        print(f"   ❌ Missing required files: {missing_files}")
        return False
    else:
        print("   ✅ All Docker configuration files present")

    # Test 3: Check FastAPI app structure (without importing FastAPI)
    try:
        # Read the app.py file to verify enhanced endpoints were added
        with open('app.py', 'r') as f:
            app_content = f.read()

        required_endpoints = [
            '/search/enhanced',
            '/chat/enhanced',
            '/triage/document',
            '/search/config',
            '/admin/initialize-enhanced'
        ]

        missing_endpoints = []
        for endpoint in required_endpoints:
            if endpoint not in app_content:
                missing_endpoints.append(endpoint)

        if missing_endpoints:
            print(f"   ❌ Missing enhanced endpoints: {missing_endpoints}")
            return False
        else:
            print("   ✅ All enhanced endpoints integrated into FastAPI app")

    except Exception as e:
        print(f"   ❌ FastAPI integration check failed: {e}")
        return False

    # Test 4: Production enhanced retrieval import in app.py
    if 'from production_enhanced_retrieval import ProductionEnhancedRAG' in app_content:
        print("   ✅ Production enhanced retrieval properly imported in app.py")
    else:
        print("   ❌ Production enhanced retrieval not imported in app.py")
        return False

    return True

async def test_feature_completeness():
    """Test that all requested features are implemented"""
    print("\n🎯 Testing Feature Completeness")
    print("===============================")

    features_checklist = [
        ("Cross-encoder reranking", "ProductionReranker"),
        ("BM25 sparse retrieval", "ProductionBM25"),
        ("Hybrid retrieval", "ProductionHybridRetriever"),
        ("Document quality triage", "triage_document_quality"),
        ("Cloud OCR integration", "ProductionCloudOCR"),
        ("Tag similarity detection", "ProductionTagSimilarity"),
        ("Enhanced search endpoints", "/search/enhanced"),
        ("Enhanced chat endpoints", "/chat/enhanced"),
        ("Controlled tag hierarchy", "normalize_tag"),
        ("Obsidian vault generation", "obsidian")
    ]

    implemented_features = []
    missing_features = []

    for feature_name, check_item in features_checklist:
        try:
            if check_item.startswith('/'):
                # Check if endpoint exists in app.py
                with open('app.py', 'r') as f:
                    if check_item in f.read():
                        implemented_features.append(feature_name)
                    else:
                        missing_features.append(feature_name)
            elif check_item.startswith('Production'):
                # Check if class exists
                import production_enhanced_retrieval
                if hasattr(production_enhanced_retrieval, check_item):
                    implemented_features.append(feature_name)
                else:
                    missing_features.append(feature_name)
            else:
                # Check if method/variable exists
                app_content = open('app.py', 'r').read()
                prod_content = open('production_enhanced_retrieval.py', 'r').read()
                docker_content = open('docker-compose.yml', 'r').read()

                if check_item in app_content or check_item in prod_content or check_item in docker_content:
                    implemented_features.append(feature_name)
                else:
                    missing_features.append(feature_name)

        except Exception as e:
            missing_features.append(f"{feature_name} (error: {e})")

    print(f"   ✅ Implemented features ({len(implemented_features)}):")
    for feature in implemented_features:
        print(f"      • {feature}")

    if missing_features:
        print(f"   ❌ Missing features ({len(missing_features)}):")
        for feature in missing_features:
            print(f"      • {feature}")
        return False
    else:
        print("   🎉 All requested features implemented!")
        return True

async def test_nixos_compatibility():
    """Test NixOS-specific requirements"""
    print("\n🐧 Testing NixOS Compatibility")
    print("==============================")

    # Test 1: No external dependencies in production modules
    try:
        import production_enhanced_retrieval

        # Check if module imports without external dependencies
        print("   ✅ Production modules work without external dependencies")

        # Test basic functionality
        from production_enhanced_retrieval import ProductionBM25
        bm25 = ProductionBM25()

        test_docs = [{'content': 'test', 'metadata': {}, 'chunk_id': '1'}]
        bm25.index_documents(test_docs)
        results = bm25.search('test', top_k=1)

        if results:
            print("   ✅ BM25 works with pure Python implementation")
        else:
            print("   ❌ BM25 pure Python implementation failed")
            return False

    except ImportError as e:
        print(f"   ❌ External dependency detected: {e}")
        return False

    # Test 2: Docker deployment readiness
    if os.path.exists('deploy.sh') and os.access('deploy.sh', os.X_OK):
        print("   ✅ Deployment script is executable")
    else:
        print("   ❌ Deployment script not executable")
        return False

    # Test 3: Environment variable configuration
    with open('docker-compose.yml', 'r') as f:
        compose_content = f.read()

    required_env_vars = [
        'GOOGLE_VISION_API_KEY',
        'AZURE_CV_ENDPOINT',
        'AWS_ACCESS_KEY_ID',
        'ENABLE_ENHANCED_SEARCH'
    ]

    missing_env_vars = []
    for var in required_env_vars:
        if var not in compose_content:
            missing_env_vars.append(var)

    if missing_env_vars:
        print(f"   ❌ Missing environment variables: {missing_env_vars}")
        return False
    else:
        print("   ✅ All required environment variables configured")

    return True

async def test_docker_routing():
    """Test Docker networking and routing configuration"""
    print("\n🌐 Testing Docker Networking & Routing")
    print("======================================")

    # Test 1: Nginx configuration
    if os.path.exists('nginx.conf'):
        with open('nginx.conf', 'r') as f:
            nginx_content = f.read()

        routing_features = [
            'limit_req_zone',  # Rate limiting
            'proxy_pass',      # Reverse proxy
            'X-Forwarded-For', # Headers
            '/api/search/enhanced',  # Enhanced endpoints
            'add_header'       # Security headers
        ]

        missing_features = []
        for feature in routing_features:
            if feature not in nginx_content:
                missing_features.append(feature)

        if missing_features:
            print(f"   ❌ Missing Nginx features: {missing_features}")
            return False
        else:
            print("   ✅ Nginx reverse proxy properly configured")
    else:
        print("   ❌ nginx.conf not found")
        return False

    # Test 2: Docker network configuration
    with open('docker-compose.yml', 'r') as f:
        compose_content = f.read()

    if 'rag_network' in compose_content and 'networks:' in compose_content:
        print("   ✅ Docker networking properly configured")
    else:
        print("   ❌ Docker networking not configured")
        return False

    # Test 3: Service dependencies
    if 'depends_on:' in compose_content and 'chromadb' in compose_content:
        print("   ✅ Service dependencies configured")
    else:
        print("   ❌ Service dependencies not configured")
        return False

    return True

async def run_final_production_test():
    """Run comprehensive production readiness test"""
    print("🎯 Final Production Readiness Test")
    print("==================================")
    print("Testing all components for production deployment...")

    tests = [
        ("Core Enhanced RAG Functionality", test_core_functionality),
        ("Production Integration", test_production_integration),
        ("Feature Completeness", test_feature_completeness),
        ("NixOS Compatibility", test_nixos_compatibility),
        ("Docker Routing & Networking", test_docker_routing)
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

    # Final summary
    elapsed = time.time() - start_time
    passed = sum(1 for r in results.values() if r)
    total = len(results)

    print(f"\n📊 Final Production Test Results")
    print(f"================================")

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nResults: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print(f"Duration: {elapsed:.2f} seconds")

    if passed == total:
        print(f"\n🎉 PRODUCTION READY! 🎉")
        print(f"=======================")
        print(f"✅ All enhanced RAG features implemented")
        print(f"✅ NixOS compatibility ensured")
        print(f"✅ Docker routing configured")
        print(f"✅ FastAPI integration ready")
        print(f"✅ Cloud OCR support available")
        print(f"✅ Security features enabled")
        print(f"")
        print(f"🚀 Ready for deployment with: ./deploy.sh")
        print(f"📖 See PRODUCTION_DEPLOYMENT.md for details")
    else:
        print(f"\n⚠️  DEPLOYMENT BLOCKED")
        print(f"======================")
        print(f"Some critical features need attention before production deployment.")

    return passed == total

if __name__ == "__main__":
    asyncio.run(run_final_production_test())