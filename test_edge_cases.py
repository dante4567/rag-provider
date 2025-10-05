"""
Edge case testing for RAG service endpoints
Tests large files, empty inputs, API failures, etc.
"""
import requests
import tempfile
import time
from pathlib import Path

BASE_URL = "http://localhost:8001"
HEADERS = {"X-API-Key": "your_secure_api_key_here"}  # From .env file


def api_post(endpoint, **kwargs):
    """Helper to make POST requests with auth headers"""
    if 'headers' not in kwargs:
        kwargs['headers'] = HEADERS
    else:
        kwargs['headers'].update(HEADERS)
    return requests.post(f"{BASE_URL}{endpoint}", **kwargs)


def api_get(endpoint, **kwargs):
    """Helper to make GET requests with auth headers"""
    if 'headers' not in kwargs:
        kwargs['headers'] = HEADERS
    else:
        kwargs['headers'].update(HEADERS)
    return requests.get(f"{BASE_URL}{endpoint}", **kwargs)


def test_large_file_upload():
    """Test uploading a large text file (>1MB)"""
    print("\n🧪 Testing large file upload (2MB)...")

    # Create 2MB file
    large_content = "This is a test line. " * 100000  # ~2MB
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(large_content)
        temp_path = f.name

    try:
        with open(temp_path, 'rb') as f:
            response = api_post(
                "/ingest/file",
                files={"file": ("large_test.txt", f, "text/plain")}
            )

        if response.status_code == 200:
            print(f"   ✅ Large file uploaded successfully")
            print(f"   📄 Doc ID: {response.json().get('document_id')}")
            return True
        else:
            print(f"   ❌ Failed: {response.status_code} - {response.text}")
            return False
    finally:
        Path(temp_path).unlink()


def test_empty_file_upload():
    """Test uploading an empty file"""
    print("\n🧪 Testing empty file upload...")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        # Write nothing
        temp_path = f.name

    try:
        with open(temp_path, 'rb') as f:
            response = api_post(
                "/ingest/file",
                files={"file": ("empty.txt", f, "text/plain")}
            )

        # Should either succeed with warning or fail gracefully
        if response.status_code in [200, 400]:
            print(f"   ✅ Handled gracefully: {response.status_code}")
            return True
        else:
            print(f"   ❌ Unexpected response: {response.status_code}")
            return False
    finally:
        Path(temp_path).unlink()


def test_empty_search_query():
    """Test search with empty query"""
    print("\n🧪 Testing empty search query...")

    response = api_post(
        "/search",
        json={"text": "", "top_k": 5}
    )

    if response.status_code in [200, 400, 422]:
        print(f"   ✅ Handled gracefully: {response.status_code}")
        return True
    else:
        print(f"   ❌ Unexpected response: {response.status_code}")
        return False


def test_search_no_results():
    """Test search for non-existent content"""
    print("\n🧪 Testing search with no matching results...")

    response = api_post(
        "/search",
        json={
            "text": "xyzzy_nonexistent_quantum_foobar_12345",
            "top_k": 5
        }
    )

    if response.status_code == 200:
        results = response.json().get("results", [])
        print(f"   ✅ Search returned {len(results)} results (expected 0 or few)")
        return True
    else:
        print(f"   ❌ Failed: {response.status_code}")
        return False


def test_very_large_top_k():
    """Test search with very large top_k value"""
    print("\n🧪 Testing search with top_k=1000...")

    response = api_post(
        "/search",
        json={"text": "test", "top_k": 1000}
    )

    if response.status_code in [200, 400, 422]:
        print(f"   ✅ Handled gracefully: {response.status_code}")
        return True
    else:
        print(f"   ❌ Unexpected response: {response.status_code}")
        return False


def test_chat_with_no_context():
    """Test chat when no documents are found"""
    print("\n🧪 Testing chat with query that returns no context...")

    response = api_post(
        "/chat",
        json={
            "message": "Tell me about xyzzy_nonexistent_topic_12345",
            "include_history": False
        }
    )

    if response.status_code == 200:
        answer = response.json().get("answer", "")
        print(f"   ✅ Chat responded: {answer[:100]}...")
        return True
    else:
        print(f"   ❌ Failed: {response.status_code}")
        return False


def test_chat_very_long_message():
    """Test chat with very long message"""
    print("\n🧪 Testing chat with very long message (5000 chars)...")

    long_message = "This is a very long question. " * 200  # ~5000 chars

    response = api_post(
        "/chat",
        json={
            "message": long_message,
            "include_history": False
        }
    )

    if response.status_code in [200, 400, 413]:
        print(f"   ✅ Handled gracefully: {response.status_code}")
        return True
    else:
        print(f"   ❌ Unexpected response: {response.status_code}")
        return False


def test_unsupported_file_type():
    """Test uploading unsupported file type"""
    print("\n🧪 Testing unsupported file type (.xyz)...")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xyz', delete=False) as f:
        f.write("test content")
        temp_path = f.name

    try:
        with open(temp_path, 'rb') as f:
            response = api_post(
                "/ingest/file",
                files={"file": ("test.xyz", f, "application/octet-stream")}
            )

        # Should handle gracefully - either process as text or reject
        if response.status_code in [200, 400, 415]:
            print(f"   ✅ Handled gracefully: {response.status_code}")
            return True
        else:
            print(f"   ❌ Unexpected response: {response.status_code}")
            return False
    finally:
        Path(temp_path).unlink()


def test_special_characters_in_search():
    """Test search with special characters"""
    print("\n🧪 Testing search with special characters...")

    special_queries = [
        "test @#$%^&*()",
        "test 中文",
        "test émojis 🎉",
        "test\nwith\nnewlines"
    ]

    all_passed = True
    for query in special_queries:
        response = api_post(
            "/search",
            json={"text": query, "top_k": 5}
        )

        if response.status_code not in [200, 400]:
            print(f"   ❌ Failed for '{query[:20]}...': {response.status_code}")
            all_passed = False

    if all_passed:
        print(f"   ✅ All special character tests passed")
    return all_passed


def test_concurrent_requests():
    """Test handling of concurrent requests"""
    print("\n🧪 Testing concurrent requests (10 simultaneous)...")

    import concurrent.futures

    def make_request(i):
        response = api_post(
            "/search",
            json={"text": f"concurrent test {i}", "top_k": 5}
        )
        return response.status_code == 200

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request, i) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    success_count = sum(results)
    print(f"   ✅ {success_count}/10 requests succeeded")
    return success_count >= 8  # Allow some failures


def test_health_endpoint():
    """Test health check endpoint"""
    print("\n🧪 Testing health endpoint...")

    response = api_get("/health")

    if response.status_code == 200:
        print(f"   ✅ Health check passed: {response.json()}")
        return True
    else:
        print(f"   ❌ Health check failed: {response.status_code}")
        return False


def run_all_tests():
    """Run all edge case tests"""
    print("=" * 60)
    print("🧪 EDGE CASE TESTING SUITE")
    print("=" * 60)

    tests = [
        ("Health Check", test_health_endpoint),
        ("Large File Upload", test_large_file_upload),
        ("Empty File Upload", test_empty_file_upload),
        ("Empty Search Query", test_empty_search_query),
        ("Search No Results", test_search_no_results),
        ("Large top_k Value", test_very_large_top_k),
        ("Chat No Context", test_chat_with_no_context),
        ("Chat Long Message", test_chat_very_long_message),
        ("Unsupported File Type", test_unsupported_file_type),
        ("Special Characters", test_special_characters_in_search),
        ("Concurrent Requests", test_concurrent_requests),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            results.append((name, False))
        time.sleep(0.5)  # Brief pause between tests

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    print("\n" + "-" * 60)
    print(f"Results: {passed_count}/{total_count} tests passed ({passed_count/total_count*100:.1f}%)")

    if passed_count == total_count:
        print("🎉 All edge case tests passed!")
        return 0
    elif passed_count >= total_count * 0.8:
        print("⚠️  Most tests passed, some issues to address")
        return 1
    else:
        print("❌ Significant failures detected")
        return 2


if __name__ == "__main__":
    exit(run_all_tests())
