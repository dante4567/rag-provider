#!/usr/bin/env python3
"""
Test simplified architecture functionality
"""

import requests
import json
import time

def test_simplified_service():
    """Test the simplified RAG service"""

    base_url = "http://localhost:8001"

    print("🧪 Testing Simplified RAG Architecture")
    print("=" * 50)

    # Test 1: Health check
    print("\n1. Testing health check...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            health = response.json()
            print(f"   ✅ Health check passed: {health['status']}")
        else:
            print(f"   ❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Health check error: {e}")
        return False

    # Test 2: Upload document
    print("\n2. Testing document upload...")
    try:
        test_content = "This is a test document for the simplified RAG architecture. It contains information about machine learning and artificial intelligence."

        files = {"file": ("test_simple.txt", test_content, "text/plain")}
        response = requests.post(f"{base_url}/ingest/file", files=files)

        if response.status_code == 200:
            upload_result = response.json()
            document_id = upload_result["document_id"]
            print(f"   ✅ Document uploaded: {document_id}")
            print(f"   📊 Chunks created: {upload_result.get('chunk_count', 'N/A')}")
        else:
            print(f"   ❌ Upload failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Upload error: {e}")
        return False

    # Test 3: Search documents
    print("\n3. Testing document search...")
    try:
        time.sleep(2)  # Give time for indexing

        search_data = {
            "text": "machine learning",
            "top_k": 3
        }

        response = requests.post(f"{base_url}/search", json=search_data)

        if response.status_code == 200:
            search_result = response.json()
            print(f"   ✅ Search completed: {search_result['total_results']} results")
            print(f"   ⚡ Processing time: {search_result['processing_time']:.3f}s")

            if search_result['results']:
                first_result = search_result['results'][0]
                print(f"   📄 Top result score: {first_result['score']:.3f}")
        else:
            print(f"   ❌ Search failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Search error: {e}")
        return False

    # Test 4: Chat with RAG
    print("\n4. Testing RAG chat...")
    try:
        chat_data = {
            "question": "What is this document about?",
            "llm_model": "groq/llama-3.1-8b-instant"
        }

        response = requests.post(f"{base_url}/chat", json=chat_data)

        if response.status_code == 200:
            chat_result = response.json()
            print(f"   ✅ Chat completed")
            print(f"   🤖 Model used: {chat_result['model_used']}")
            print(f"   💰 Cost: ${chat_result['cost']:.6f}")
            print(f"   📚 Sources: {len(chat_result['sources'])}")
            print(f"   💬 Answer: {chat_result['answer'][:100]}...")
        else:
            print(f"   ❌ Chat failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Chat error: {e}")
        return False

    # Test 5: System stats
    print("\n5. Testing system statistics...")
    try:
        response = requests.get(f"{base_url}/stats")

        if response.status_code == 200:
            stats = response.json()
            print(f"   ✅ Stats retrieved")
            print(f"   📊 Total documents: {stats.get('document_stats', {}).get('total_documents', 'N/A')}")
            print(f"   🔧 Features enabled: {len([f for f, enabled in stats.get('features', {}).items() if enabled])}")
        else:
            print(f"   ❌ Stats failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Stats error: {e}")
        return False

    print("\n🎉 All tests passed! Simplified architecture is working correctly.")
    return True

if __name__ == "__main__":
    success = test_simplified_service()
    exit(0 if success else 1)