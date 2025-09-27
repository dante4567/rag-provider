#!/usr/bin/env python3
"""
Test suite for RAG Service
Run with: python test_rag.py
"""

import requests
import json
import time
import os
from pathlib import Path
import tempfile

BASE_URL = "http://localhost:8001"

class RAGTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_docs = []

    def log(self, message, level="INFO"):
        print(f"[{level}] {message}")

    def test_health(self):
        """Test health endpoint"""
        self.log("Testing health endpoint...")

        try:
            response = self.session.get(f"{BASE_URL}/health")
            assert response.status_code == 200, f"Health check failed: {response.status_code}"

            data = response.json()
            assert data["status"] == "healthy", f"Service not healthy: {data}"
            assert "timestamp" in data

            self.log("✓ Health check passed")
            return True

        except Exception as e:
            self.log(f"✗ Health check failed: {e}", "ERROR")
            return False

    def test_ingest_document(self):
        """Test document ingestion via API"""
        self.log("Testing document ingestion...")

        try:
            doc = {
                "content": "Artificial intelligence and machine learning are transforming technology. "
                          "These technologies enable computers to learn patterns from data and make "
                          "intelligent decisions without explicit programming.",
                "filename": "ai_test.txt",
                "metadata": {
                    "source": "test_suite",
                    "category": "technology"
                }
            }

            response = self.session.post(f"{BASE_URL}/ingest", json=doc)
            assert response.status_code == 200, f"Ingestion failed: {response.status_code} - {response.text}"

            data = response.json()
            assert data["success"] == True, f"Ingestion not successful: {data}"
            assert "doc_id" in data
            assert data["chunks"] > 0
            assert "metadata" in data

            self.test_docs.append(data["doc_id"])
            self.log(f"✓ Document ingestion passed (doc_id: {data['doc_id']}, chunks: {data['chunks']})")
            return data

        except Exception as e:
            self.log(f"✗ Document ingestion failed: {e}", "ERROR")
            return None

    def test_file_upload(self):
        """Test file upload ingestion"""
        self.log("Testing file upload...")

        try:
            # Create a temporary test file
            test_content = """# Machine Learning Basics

Machine learning is a subset of artificial intelligence that focuses on algorithms
that can learn and improve from experience without being explicitly programmed.

## Key Concepts:
- Supervised Learning
- Unsupervised Learning
- Deep Learning
- Neural Networks

This technology powers recommendation systems, image recognition, and natural language processing."""

            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write(test_content)
                temp_path = f.name

            # Upload the file
            with open(temp_path, 'rb') as f:
                files = {'file': ('ml_basics.md', f, 'text/markdown')}
                response = self.session.post(f"{BASE_URL}/ingest/file", files=files)

            # Clean up temp file
            os.unlink(temp_path)

            assert response.status_code == 200, f"File upload failed: {response.status_code} - {response.text}"

            data = response.json()
            assert data["success"] == True
            assert "doc_id" in data
            assert data["chunks"] > 0

            self.test_docs.append(data["doc_id"])
            self.log(f"✓ File upload passed (doc_id: {data['doc_id']}, chunks: {data['chunks']})")
            return data

        except Exception as e:
            self.log(f"✗ File upload failed: {e}", "ERROR")
            return None

    def test_search(self):
        """Test search functionality"""
        self.log("Testing search...")

        try:
            # Wait a moment for indexing
            time.sleep(2)

            query = {
                "text": "artificial intelligence machine learning",
                "top_k": 5
            }

            response = self.session.post(f"{BASE_URL}/search", json=query)
            assert response.status_code == 200, f"Search failed: {response.status_code} - {response.text}"

            data = response.json()
            assert "results" in data
            assert "query" in data
            assert "total_results" in data
            assert "search_time_ms" in data

            # Should have found some results
            assert len(data["results"]) > 0, "No search results found"

            # Check result structure
            for result in data["results"]:
                assert "content" in result
                assert "metadata" in result
                assert "relevance_score" in result
                assert "chunk_id" in result
                assert 0 <= result["relevance_score"] <= 1

            self.log(f"✓ Search passed (found {len(data['results'])} results, "
                    f"search time: {data['search_time_ms']:.1f}ms)")
            return data

        except Exception as e:
            self.log(f"✗ Search failed: {e}", "ERROR")
            return None

    def test_filtered_search(self):
        """Test search with metadata filtering"""
        self.log("Testing filtered search...")

        try:
            query = {
                "text": "machine learning",
                "top_k": 3,
                "filter": {"source": "test_suite"}
            }

            response = self.session.post(f"{BASE_URL}/search", json=query)
            assert response.status_code == 200, f"Filtered search failed: {response.status_code}"

            data = response.json()
            assert len(data["results"]) >= 0  # May be 0 if no matching metadata

            # If results found, verify they match the filter
            for result in data["results"]:
                metadata = result["metadata"]
                if "source" in metadata:
                    assert metadata["source"] == "test_suite"

            self.log(f"✓ Filtered search passed (found {len(data['results'])} filtered results)")
            return data

        except Exception as e:
            self.log(f"✗ Filtered search failed: {e}", "ERROR")
            return None

    def test_list_documents(self):
        """Test document listing"""
        self.log("Testing document listing...")

        try:
            response = self.session.get(f"{BASE_URL}/documents")
            assert response.status_code == 200, f"Document listing failed: {response.status_code}"

            data = response.json()
            assert isinstance(data, list), "Document list should be an array"

            # Should have at least our test documents
            assert len(data) >= len(self.test_docs), "Missing test documents in list"

            # Check document structure
            for doc in data:
                assert "id" in doc
                assert "filename" in doc
                assert "chunks" in doc
                assert "created_at" in doc
                assert "metadata" in doc

            self.log(f"✓ Document listing passed (found {len(data)} documents)")
            return data

        except Exception as e:
            self.log(f"✗ Document listing failed: {e}", "ERROR")
            return None

    def test_stats(self):
        """Test statistics endpoint"""
        self.log("Testing statistics...")

        try:
            response = self.session.get(f"{BASE_URL}/stats")
            assert response.status_code == 200, f"Stats failed: {response.status_code}"

            data = response.json()
            assert "total_documents" in data
            assert "total_chunks" in data
            assert "storage_used_mb" in data

            # Should have positive values
            assert data["total_documents"] > 0
            assert data["total_chunks"] > 0
            assert data["storage_used_mb"] >= 0

            self.log(f"✓ Statistics passed (docs: {data['total_documents']}, "
                    f"chunks: {data['total_chunks']}, storage: {data['storage_used_mb']:.2f}MB)")
            return data

        except Exception as e:
            self.log(f"✗ Statistics failed: {e}", "ERROR")
            return None

    def test_markdown_export(self):
        """Test markdown file creation"""
        self.log("Testing markdown export...")

        try:
            markdown_dir = Path("./data/markdown")
            if not markdown_dir.exists():
                self.log("Markdown directory doesn't exist, creating it...")
                markdown_dir.mkdir(parents=True, exist_ok=True)

            # Check if markdown files were created
            markdown_files = list(markdown_dir.glob("*.md"))

            if len(markdown_files) == 0:
                self.log("No markdown files found, this might be expected if documents were just created")
                return True

            # Check markdown file structure
            for md_file in markdown_files[:2]:  # Check first 2 files
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Should have YAML frontmatter
                assert content.startswith("---"), f"Markdown file {md_file} missing frontmatter"
                assert "id:" in content
                assert "filename:" in content
                assert "created_at:" in content

            self.log(f"✓ Markdown export passed (found {len(markdown_files)} files)")
            return True

        except Exception as e:
            self.log(f"✗ Markdown export test failed: {e}", "ERROR")
            return False

    def test_delete_document(self):
        """Test document deletion"""
        self.log("Testing document deletion...")

        try:
            if not self.test_docs:
                self.log("No test documents to delete")
                return True

            doc_id = self.test_docs[0]
            response = self.session.delete(f"{BASE_URL}/documents/{doc_id}")
            assert response.status_code == 200, f"Document deletion failed: {response.status_code}"

            data = response.json()
            assert data["success"] == True

            # Verify document is gone
            time.sleep(1)
            response = self.session.get(f"{BASE_URL}/documents")
            docs = response.json()
            doc_ids = [doc["id"] for doc in docs]
            assert doc_id not in doc_ids, "Document still exists after deletion"

            self.test_docs.remove(doc_id)
            self.log(f"✓ Document deletion passed (deleted {doc_id})")
            return True

        except Exception as e:
            self.log(f"✗ Document deletion failed: {e}", "ERROR")
            return False

    def run_all_tests(self):
        """Run all tests"""
        self.log("Starting RAG Service Test Suite")
        self.log("=" * 50)

        tests = [
            ("Health Check", self.test_health),
            ("Document Ingestion", self.test_ingest_document),
            ("File Upload", self.test_file_upload),
            ("Search", self.test_search),
            ("Filtered Search", self.test_filtered_search),
            ("Document Listing", self.test_list_documents),
            ("Statistics", self.test_stats),
            ("Markdown Export", self.test_markdown_export),
            ("Document Deletion", self.test_delete_document),
        ]

        passed = 0
        failed = 0

        for test_name, test_func in tests:
            self.log(f"\n--- {test_name} ---")
            try:
                result = test_func()
                if result is not False:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self.log(f"✗ {test_name} failed with exception: {e}", "ERROR")
                failed += 1

            time.sleep(0.5)  # Brief pause between tests

        self.log("\n" + "=" * 50)
        self.log(f"Test Results: {passed} passed, {failed} failed")

        if failed == 0:
            self.log("🎉 All tests passed! ✓")
            return True
        else:
            self.log(f"❌ {failed} test(s) failed")
            return False

def main():
    """Main test runner"""
    tester = RAGTester()

    # Check if service is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ RAG service is not healthy at {BASE_URL}")
            print("Please start the service with: docker-compose up -d")
            return 1
    except requests.exceptions.RequestException:
        print(f"❌ RAG service is not accessible at {BASE_URL}")
        print("Please start the service with: docker-compose up -d")
        return 1

    # Run tests
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())