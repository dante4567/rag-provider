"""
TEST WITH REAL USER DATA

This script tests the RAG system with actual user documents from Downloads folder.
Tests upload → search → chat with real-world data.
"""

import asyncio
import requests
import time
from pathlib import Path
import sys

BASE_URL = "http://localhost:8001"

# Test documents from user's Downloads and synced folders
TEST_DOCUMENTS = [
    # From Downloads
    "~/Downloads/0 Transcript - Introduction.pdf",
    "~/Downloads/HIN_InfoBlatt_Datenschutz_2025.md",
    "~/Downloads/Custody-Models-Visual-Note.md",
    "~/Downloads/video_summary.txt",

    # From synced-documents
    "~/Documents/synced-documents/Advanced Topics - Paperless-ngx.pdf",
    "~/Documents/synced-documents/Hey Daniel, ja wir sind gut angekommen..txt",
    "~/Documents/synced-documents/Veranstaltungen 0425.pdf",
]

test_results = {
    "uploaded": 0,
    "failed_upload": 0,
    "searches": 0,
    "chats": 0,
    "total_cost": 0.0,
    "documents": []
}

def test_health():
    """Test 1: Check service is running"""
    print("\n" + "="*70)
    print("TESTING WITH REAL USER DATA")
    print("="*70 + "\n")

    print("1. Checking service health...")
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code == 200:
            health = resp.json()
            print(f"   ✅ Service healthy")
            print(f"   LLM Providers: {list(health.get('llm_providers', {}).keys())}")
            print(f"   ChromaDB: {health.get('chromadb', 'unknown')}")
            return True
        else:
            print(f"   ❌ Service unhealthy: {resp.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Cannot connect to service: {e}")
        print(f"\n   💡 Start the service with: docker-compose up -d")
        return False

def upload_document(file_path: str):
    """Upload a document to the RAG system"""
    path = Path(file_path).expanduser()

    if not path.exists():
        print(f"   ⚠️  File not found: {path.name}")
        test_results["failed_upload"] += 1
        return None

    print(f"\n   Uploading: {path.name} ({path.stat().st_size / 1024:.1f} KB)")

    try:
        # Disable auth for testing
        with open(path, 'rb') as f:
            files = {'file': (path.name, f, 'application/octet-stream')}

            # Try without auth first, then with if needed
            resp = requests.post(f"{BASE_URL}/ingest/file", files=files, timeout=60)

            if resp.status_code == 401:
                # Need auth - use default API key
                headers = {'X-API-Key': 'your_secure_api_key_here'}
                with open(path, 'rb') as f:
                    files = {'file': (path.name, f, 'application/octet-stream')}
                    resp = requests.post(
                        f"{BASE_URL}/ingest/file",
                        files=files,
                        headers=headers,
                        timeout=60
                    )

        if resp.status_code == 200:
            result = resp.json()
            doc_id = result.get('doc_id', 'unknown')
            chunks = result.get('chunks', 0)
            metadata = result.get('metadata', {})
            doc_type = metadata.get('document_type', 'unknown')

            # Extract enriched metadata
            title = metadata.get('title', path.name)
            summary = metadata.get('summary', '')
            tags = metadata.get('tags', [])
            key_points = metadata.get('key_points', [])

            print(f"   ✅ Uploaded successfully")
            print(f"      Document ID: {doc_id[:30]}...")
            print(f"      Title: {title}")
            print(f"      Type: {doc_type}")
            print(f"      Chunks: {chunks}")
            if tags:
                print(f"      Tags: {', '.join(tags[:5])}")
            if summary:
                print(f"      Summary: {summary[:80]}...")
            if key_points:
                print(f"      Key Points: {len(key_points)} extracted")

            test_results["uploaded"] += 1
            test_results["documents"].append({
                "file": path.name,
                "doc_id": doc_id,
                "chunks": chunks,
                "type": doc_type,
                "title": title,
                "tags": len(tags)
            })

            return doc_id
        else:
            print(f"   ❌ Upload failed: {resp.status_code}")
            print(f"      Error: {resp.text[:200]}")
            test_results["failed_upload"] += 1
            return None

    except Exception as e:
        print(f"   ❌ Upload error: {str(e)[:100]}")
        test_results["failed_upload"] += 1
        return None

def search_documents(query: str, top_k: int = 3):
    """Search uploaded documents"""
    print(f"\n   Searching: '{query}'")

    try:
        search_data = {"text": query, "top_k": top_k}
        resp = requests.post(f"{BASE_URL}/search", json=search_data, timeout=30)

        if resp.status_code == 200:
            results = resp.json().get('results', [])
            print(f"   ✅ Found {len(results)} results")

            if results:
                top_result = results[0]
                print(f"      Top result relevance: {top_result.get('relevance_score', 0):.3f}")
                print(f"      Content preview: {top_result.get('content', '')[:80]}...")

            test_results["searches"] += 1
            return results
        else:
            print(f"   ❌ Search failed: {resp.status_code}")
            return []

    except Exception as e:
        print(f"   ❌ Search error: {str(e)[:100]}")
        return []

def chat_with_rag(question: str, model: str = "groq/llama-3.1-8b-instant"):
    """Chat using RAG (retrieval + LLM)"""
    print(f"\n   Question: '{question}'")
    print(f"   Using model: {model}")

    try:
        chat_data = {"question": question, "llm_model": model}

        # Try without auth first
        resp = requests.post(f"{BASE_URL}/chat", json=chat_data, timeout=60)

        if resp.status_code == 401:
            # Need auth
            headers = {'X-API-Key': 'your_secure_api_key_here'}
            resp = requests.post(f"{BASE_URL}/chat", json=chat_data, headers=headers, timeout=60)

        if resp.status_code == 200:
            result = resp.json()
            answer = result.get('answer', '')
            cost = result.get('cost', 0)
            model_used = result.get('model_used', 'unknown')
            sources = result.get('sources', [])

            print(f"   ✅ Chat response received")
            print(f"      Model: {model_used}")
            print(f"      Cost: ${cost:.6f}")
            print(f"      Sources used: {len(sources)}")
            print(f"      Answer: {answer[:200]}...")

            test_results["chats"] += 1
            test_results["total_cost"] += cost

            return answer
        else:
            print(f"   ❌ Chat failed: {resp.status_code}")
            print(f"      Error: {resp.text[:200]}")
            return None

    except Exception as e:
        print(f"   ❌ Chat error: {str(e)[:100]}")
        return None

def main():
    """Run real user data tests"""

    # Test 1: Health check
    if not test_health():
        print("\n❌ Service not available. Exiting.\n")
        return

    # Test 2: Upload real documents
    print(f"\n2. Uploading {len(TEST_DOCUMENTS)} user documents...")
    for doc_path in TEST_DOCUMENTS:
        upload_document(doc_path)

    # Wait for indexing
    if test_results["uploaded"] > 0:
        print(f"\n   Waiting 3 seconds for indexing...")
        time.sleep(3)

    # Test 3: Search real queries
    print(f"\n3. Testing search with real queries...")

    search_queries = [
        "data privacy information",
        "introduction transcript",
        "custody models",
        "video summary"
    ]

    for query in search_queries:
        search_documents(query)

    # Test 4: RAG chat
    print(f"\n4. Testing RAG chat with real questions...")

    questions = [
        "What is mentioned about data privacy?",
        "Can you summarize the introduction transcript?",
        "What custody models are discussed?"
    ]

    for question in questions:
        chat_with_rag(question)

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70 + "\n")

    print(f"Documents uploaded: {test_results['uploaded']}/{len(TEST_DOCUMENTS)}")
    print(f"Upload failures: {test_results['failed_upload']}")
    print(f"Searches performed: {test_results['searches']}")
    print(f"Chat queries: {test_results['chats']}")
    print(f"Total cost: ${test_results['total_cost']:.6f}")

    if test_results["uploaded"] > 0:
        print(f"\n✅ Successfully tested with real user data!")
        print(f"\nUploaded documents:")
        for doc in test_results["documents"]:
            tags_info = f", {doc['tags']} tags" if doc.get('tags', 0) > 0 else ""
            title_info = f" - {doc['title']}" if doc.get('title') != doc['file'] else ""
            print(f"  - {doc['file']}{title_info} ({doc['type']}, {doc['chunks']} chunks{tags_info})")

    # Email support instructions
    print("\n" + "="*70)
    print("HOW TO ADD EMAIL SUPPORT")
    print("="*70 + "\n")

    print("The system already supports .eml and .msg files!")
    print("\nTo test with emails:")
    print("1. Export emails from your email client:")
    print("   - Gmail: Select email → More → Download message")
    print("   - Outlook: Drag email to desktop (creates .msg)")
    print("   - Apple Mail: File → Save As → .eml format")
    print("\n2. Upload the .eml or .msg file:")
    print("   curl -X POST -F 'file=@email.eml' http://localhost:8001/ingest/file")
    print("\n3. Or use the Python API:")
    print("   upload_document('path/to/email.eml')")
    print("\n4. The system will extract:")
    print("   - Subject")
    print("   - From/To")
    print("   - Body text")
    print("   - Attachments (if configured)")

    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    main()
