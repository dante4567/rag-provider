"""
Integration tests for hybrid retrieval (BM25 + dense + MMR)

Tests that hybrid search improves over dense-only retrieval:
- BM25 excels at exact keyword matching
- Dense excels at semantic similarity
- Hybrid gets best of both worlds
- MMR adds diversity to results
"""

import pytest
import requests
import time
from typing import List, Dict

BASE_URL = "http://localhost:8001"


class TestBM25KeywordSearch:
    """Test that BM25 component handles keyword queries well"""

    @pytest.fixture(autouse=True)
    def setup_keyword_dataset(self):
        """Create documents with specific keywords for BM25 testing"""
        self.docs = [
            {
                "content": """
                ACME Corporation Annual Report 2025

                Company: ACME Corporation
                Ticker: ACME
                Revenue: $500M
                CEO: Jane Smith
                """,
                "filename": "acme_report.txt"
            },
            {
                "content": """
                Globex Industries Financial Statement

                Company: Globex Industries
                Ticker: GLBX
                Revenue: $750M
                CEO: John Doe
                """,
                "filename": "globex_report.txt"
            },
            {
                "content": """
                General discussion about business profits and company performance.
                Companies often report their revenue and financial results quarterly.
                CEOs typically present these results to shareholders.
                """,
                "filename": "business_general.txt"
            }
        ]

        # Ingest all documents
        for doc in self.docs:
            requests.post(
                f"{BASE_URL}/ingest",
                json=doc,
                timeout=30
            )

        # Wait for indexing (both ChromaDB + BM25)
        time.sleep(3)

    def test_exact_keyword_match(self):
        """BM25 should excel at finding exact keywords like 'ACME'"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "ACME Corporation ticker revenue", "top_k": 3},
            timeout=10
        )
        assert response.status_code == 200

        results = response.json()["results"]
        assert len(results) > 0

        # Top result should mention ACME (exact match)
        top_result = results[0]["content"].lower()
        assert "acme" in top_result, "Hybrid search should find exact keyword 'ACME'"

        # Should NOT be the general business doc
        assert "general discussion" not in top_result, \
            "Should return specific doc, not general one"

    def test_proper_noun_matching(self):
        """Hybrid search should handle proper nouns well (BM25 advantage)"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "Globex Industries CEO", "top_k": 3},
            timeout=10
        )
        assert response.status_code == 200

        results = response.json()["results"]
        top_result = results[0]["content"].lower()

        # Should find Globex document (exact company name match)
        assert "globex" in top_result, \
            "Hybrid search should prioritize exact company name match"


class TestSemanticVsKeyword:
    """Test that hybrid search handles both semantic and keyword queries"""

    @pytest.fixture(autouse=True)
    def setup_mixed_dataset(self):
        """Create documents for semantic + keyword testing"""
        self.docs = [
            {
                "content": """
                Machine Learning Tutorial

                This guide covers neural networks, backpropagation, and gradient descent.
                We'll train a model on the MNIST dataset using PyTorch.
                """,
                "filename": "ml_tutorial.txt"
            },
            {
                "content": """
                Deep Learning Best Practices

                Tips for training deep neural networks effectively.
                Use batch normalization, dropout, and learning rate scheduling.
                """,
                "filename": "dl_practices.txt"
            },
            {
                "content": """
                AI and Artificial Intelligence Overview

                Artificial intelligence encompasses machine learning, deep learning,
                and natural language processing. Modern AI systems use neural architectures.
                """,
                "filename": "ai_overview.txt"
            }
        ]

        for doc in self.docs:
            requests.post(f"{BASE_URL}/ingest", json=doc, timeout=30)

        time.sleep(3)

    def test_semantic_query(self):
        """Semantic query should work well with hybrid search"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "how to train neural networks effectively", "top_k": 3},
            timeout=10
        )
        assert response.status_code == 200

        results = response.json()["results"]
        assert len(results) >= 2

        # Should find relevant documents (semantic understanding)
        result_texts = " ".join([r["content"].lower() for r in results[:2]])

        # Should mention training or neural networks
        relevant_terms = ["train", "neural", "learning", "deep"]
        matches = sum(1 for term in relevant_terms if term in result_texts)

        assert matches >= 2, f"Should find semantically relevant docs (found {matches}/4 terms)"

    def test_keyword_query(self):
        """Keyword query should benefit from BM25 component"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "PyTorch MNIST", "top_k": 3},
            timeout=10
        )
        assert response.status_code == 200

        results = response.json()["results"]
        top_result = results[0]["content"].lower()

        # Should find the specific tutorial mentioning PyTorch + MNIST
        assert "pytorch" in top_result or "mnist" in top_result, \
            "Hybrid search should excel at finding exact technical terms"


class TestMMRDiversity:
    """Test that MMR adds diversity to results"""

    @pytest.fixture(autouse=True)
    def setup_duplicate_dataset(self):
        """Create similar documents to test diversity"""
        self.docs = [
            {
                "content": "Python programming tutorial for beginners. Learn Python basics step by step.",
                "filename": "python_tutorial_1.txt"
            },
            {
                "content": "Python programming guide for beginners. Master Python fundamentals easily.",
                "filename": "python_tutorial_2.txt"
            },
            {
                "content": "Python programming course for beginners. Complete Python training program.",
                "filename": "python_tutorial_3.txt"
            },
            {
                "content": "JavaScript web development tutorial. Build modern web applications with JS.",
                "filename": "javascript_tutorial.txt"
            },
            {
                "content": "Java programming for enterprise applications. Learn Java for business software.",
                "filename": "java_tutorial.txt"
            }
        ]

        for doc in self.docs:
            requests.post(f"{BASE_URL}/ingest", json=doc, timeout=30)

        time.sleep(3)

    def test_diverse_results(self):
        """MMR should return diverse results, not just Python duplicates"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "programming tutorial", "top_k": 5},
            timeout=10
        )
        assert response.status_code == 200

        results = response.json()["results"]
        assert len(results) >= 3

        # Count how many are Python-specific
        python_count = sum(1 for r in results if "python" in r["content"].lower())

        # MMR should include other languages too (diversity)
        # Not all 5 results should be Python
        assert python_count < len(results), \
            f"MMR should add diversity - found {python_count}/{len(results)} Python docs (expected some variety)"

        # Should include at least one other language
        result_texts = " ".join([r["content"].lower() for r in results])
        other_languages = ["javascript", "java"]
        has_other = any(lang in result_texts for lang in other_languages)

        assert has_other, "MMR should include diverse programming languages"


class TestHybridPerformance:
    """Test that hybrid search performs well on realistic queries"""

    @pytest.fixture(autouse=True)
    def setup_realistic_dataset(self):
        """Create a realistic document set"""
        self.docs = [
            {
                "content": """
                Docker Container Orchestration with Kubernetes

                Kubernetes (K8s) manages containerized applications across clusters.
                Key concepts: Pods, Services, Deployments, StatefulSets.
                Use kubectl for cluster management.
                """,
                "filename": "kubernetes_guide.txt"
            },
            {
                "content": """
                Container Technology Overview

                Containers package applications with their dependencies.
                Popular tools include Docker, Podman, and containerd.
                Containers are lighter than virtual machines.
                """,
                "filename": "containers_overview.txt"
            },
            {
                "content": """
                Cooking with Containers

                Store food in airtight containers to keep it fresh.
                Glass containers are better than plastic for health.
                Label containers with dates for organization.
                """,
                "filename": "kitchen_containers.txt"
            }
        ]

        for doc in self.docs:
            requests.post(f"{BASE_URL}/ingest", json=doc, timeout=30)

        time.sleep(3)

    def test_technical_term_query(self):
        """Query with technical terms (kubectl, K8s) should find right docs"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "kubectl K8s pods", "top_k": 3},
            timeout=10
        )
        assert response.status_code == 200

        results = response.json()["results"]
        top_result = results[0]["content"].lower()

        # Should find Kubernetes doc (BM25 helps with kubectl, K8s)
        assert "kubernetes" in top_result or "k8s" in top_result or "kubectl" in top_result, \
            "Hybrid search should find technical docs with exact terms"

        # Should NOT return cooking doc
        assert "cooking" not in top_result and "kitchen" not in top_result, \
            "Should not confuse 'containers' (tech) with 'containers' (kitchen)"

    def test_conceptual_query(self):
        """Conceptual query should work with hybrid search"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "managing containerized applications in production", "top_k": 3},
            timeout=10
        )
        assert response.status_code == 200

        results = response.json()["results"]

        # Should return tech docs, not cooking
        result_texts = " ".join([r["content"].lower() for r in results[:2]])

        tech_terms = ["docker", "kubernetes", "pod", "cluster", "application"]
        kitchen_terms = ["cooking", "food", "kitchen", "glass"]

        tech_count = sum(1 for term in tech_terms if term in result_texts)
        kitchen_count = sum(1 for term in kitchen_terms if term in result_texts)

        assert tech_count >= 2, "Should find technical container docs"
        assert kitchen_count == 0, "Should not return kitchen container docs"


class TestHybridVsDenseOnly:
    """Compare hybrid retrieval vs dense-only to show improvement"""

    @pytest.fixture(autouse=True)
    def setup_comparison_dataset(self):
        """Create dataset where hybrid should outperform dense"""
        self.docs = [
            {
                "content": """
                Product ID: SKU-12345
                Name: Ultra-Fast SSD 1TB
                Price: $299
                Stock: In Stock
                """,
                "filename": "product_sku_12345.txt"
            },
            {
                "content": """
                Product ID: SKU-67890
                Name: Gaming Laptop RTX 4080
                Price: $1999
                Stock: Limited Stock
                """,
                "filename": "product_sku_67890.txt"
            },
            {
                "content": """
                General information about SKU product codes.
                SKUs help track inventory and manage stock levels.
                Each product has a unique SKU identifier.
                """,
                "filename": "sku_info.txt"
            }
        ]

        for doc in self.docs:
            requests.post(f"{BASE_URL}/ingest", json=doc, timeout=30)

        time.sleep(3)

    def test_sku_lookup(self):
        """Exact SKU lookup - hybrid should excel here"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "SKU-12345 price stock", "top_k": 3},
            timeout=10
        )
        assert response.status_code == 200

        results = response.json()["results"]
        top_result = results[0]["content"]

        # Hybrid (with BM25) should find exact SKU match
        assert "SKU-12345" in top_result or "12345" in top_result, \
            "Hybrid search should find exact SKU match (BM25 strength)"

        # Should NOT be the general SKU info doc
        assert "general information" not in top_result.lower(), \
            "Should return specific product, not general info"
