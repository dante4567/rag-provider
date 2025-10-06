"""
Real semantic quality tests - validates CORRECTNESS, not just API contracts

These tests verify:
- Search returns RELEVANT results (not just "something")
- Embeddings capture semantic meaning
- Results are ranked by actual relevance
"""
import pytest
import requests
import time
from typing import List, Dict


BASE_URL = "http://localhost:8001"


class TestSemanticSearchQuality:
    """Test that search actually returns semantically relevant results"""

    @pytest.fixture(autouse=True)
    def setup_golden_dataset(self):
        """Create a known dataset with clear semantic relationships"""
        self.golden_docs = [
            {
                "id": "doc_python_ml",
                "content": """
                Machine Learning with Python

                Python is the dominant language for machine learning and deep learning.
                Popular libraries include TensorFlow, PyTorch, and scikit-learn.
                These frameworks enable training neural networks on large datasets.
                """,
                "filename": "python_ml.txt"
            },
            {
                "id": "doc_java_enterprise",
                "content": """
                Java for Enterprise Applications

                Java is widely used in enterprise software development.
                Spring Framework and Java EE provide robust tools for building
                scalable business applications. Strong type safety and JVM performance
                make it ideal for large-scale systems.
                """,
                "filename": "java_enterprise.txt"
            },
            {
                "id": "doc_javascript_web",
                "content": """
                JavaScript and Modern Web Development

                JavaScript powers interactive websites and web applications.
                React, Vue, and Angular are popular frontend frameworks.
                Node.js enables JavaScript on the server side.
                """,
                "filename": "javascript_web.txt"
            },
            {
                "id": "doc_neural_networks",
                "content": """
                Neural Networks and Deep Learning

                Neural networks are computational models inspired by the human brain.
                Deep learning uses multiple layers to learn hierarchical representations.
                Convolutional networks excel at image recognition, while transformers
                dominate natural language processing tasks.
                """,
                "filename": "neural_networks.txt"
            },
            {
                "id": "doc_cooking_recipes",
                "content": """
                Italian Pasta Recipes

                Traditional Italian pasta dishes include carbonara, amatriciana, and aglio e olio.
                Fresh ingredients like San Marzano tomatoes, Parmigiano-Reggiano cheese,
                and extra virgin olive oil are essential for authentic flavor.
                """,
                "filename": "cooking.txt"
            }
        ]

        # Ingest all documents
        self.doc_ids = {}
        for doc in self.golden_docs:
            response = requests.post(
                f"{BASE_URL}/ingest",
                json={"content": doc["content"], "filename": doc["filename"]},
                timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                self.doc_ids[doc["id"]] = result.get("doc_id")

        # Wait for indexing
        time.sleep(3)

    def test_ml_query_finds_ml_docs(self):
        """Query about ML should return ML-related docs, NOT cooking"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "machine learning neural networks", "top_k": 3},
            timeout=10
        )
        assert response.status_code == 200

        results = response.json()["results"]
        assert len(results) >= 2, "Should return multiple results"

        # Get content from results
        result_texts = [
            r.get("content", r.get("text", "")).lower()
            for r in results[:3]
        ]

        # Top results should mention ML/neural/learning, NOT pasta/cooking
        top_3_text = " ".join(result_texts)

        # Positive assertions: ML terms should appear
        ml_terms = ["machine learning", "neural", "deep learning", "python"]
        ml_mentions = sum(1 for term in ml_terms if term in top_3_text)

        # Negative assertion: Cooking terms should NOT appear in top results
        cooking_terms = ["pasta", "carbonara", "recipe", "olive oil"]
        cooking_mentions = sum(1 for term in cooking_terms if term in top_3_text)

        assert ml_mentions >= 2, f"Top results should mention ML terms, found {ml_mentions}/4"
        assert cooking_mentions == 0, "Cooking document should NOT appear in ML search results"

    def test_programming_query_distinguishes_languages(self):
        """Query about web development should prefer JavaScript over Java"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "web frontend React interactive websites", "top_k": 3},
            timeout=10
        )
        assert response.status_code == 200

        results = response.json()["results"]
        top_result = results[0].get("content", results[0].get("text", "")).lower()

        # Top result should be JavaScript doc (mentions React/web)
        assert "javascript" in top_result or "react" in top_result, \
            "Web dev query should return JavaScript doc, not Java enterprise doc"

        # Should NOT be the Java enterprise doc
        assert "spring framework" not in top_result and "java ee" not in top_result, \
            "Java enterprise doc should not be top result for web dev query"

    def test_irrelevant_query_separation(self):
        """Cooking query should NOT return programming docs"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "pasta recipe Italian tomatoes cheese", "top_k": 3},
            timeout=10
        )
        assert response.status_code == 200

        results = response.json()["results"]

        # If we have results, top result should be about cooking
        if len(results) > 0:
            top_result = results[0].get("content", results[0].get("text", "")).lower()

            # Should mention food-related terms
            food_terms = ["pasta", "recipe", "tomato", "cheese", "cooking"]
            food_mentions = sum(1 for term in food_terms if term in top_result)

            # Should NOT be about programming
            code_terms = ["python", "java", "javascript", "framework", "neural"]
            code_mentions = sum(1 for term in code_terms if term in top_result)

            assert food_mentions >= 2, "Cooking query should return cooking content"
            assert code_mentions == 0, "Cooking query should NOT return programming docs"

    def test_semantic_ranking_order(self):
        """Results should be ranked by semantic relevance"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "deep learning convolutional networks image recognition", "top_k": 5},
            timeout=10
        )
        assert response.status_code == 200

        results = response.json()["results"]
        assert len(results) >= 2

        # First result should be neural networks doc (most specific match)
        top_result = results[0].get("content", results[0].get("text", "")).lower()
        assert "neural" in top_result or "deep learning" in top_result, \
            "Most relevant doc (neural networks) should rank first"

        # Cooking doc should be LAST or not in top 3
        if len(results) >= 3:
            top_3_texts = [
                r.get("content", r.get("text", "")).lower()
                for r in results[:3]
            ]
            cooking_in_top_3 = any("pasta" in t or "recipe" in t for t in top_3_texts)
            assert not cooking_in_top_3, "Irrelevant doc (cooking) should not be in top 3"

    def test_empty_results_handling(self):
        """Completely unrelated query should still work (may return distant matches)"""
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "quantum physics black holes cosmology", "top_k": 3},
            timeout=10
        )
        assert response.status_code == 200

        # Should return something (vector search always finds "closest" matches)
        # But we don't assert on content since nothing is truly relevant


class TestSemanticChunkRetrieval:
    """Test that chunking preserves semantic context"""

    def test_structured_doc_chunking(self):
        """Structured document should chunk along semantic boundaries"""
        content = """
# Python Programming Guide

## Introduction to Python
Python is a high-level programming language known for its readability.
It uses indentation to define code blocks.

## Data Structures
Python provides built-in data structures like lists, tuples, and dictionaries.
Lists are mutable, while tuples are immutable.

## Functions and Classes
Functions are defined using the def keyword.
Classes enable object-oriented programming in Python.
"""
        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "python_guide.md"},
            timeout=30
        )
        assert response.status_code == 200

        result = response.json()
        # Should create multiple chunks (one per section)
        assert result["chunks"] >= 3, f"Expected 3+ chunks for structured doc, got {result['chunks']}"

        time.sleep(2)

        # Search for section-specific content
        search_response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "lists tuples dictionaries mutable", "top_k": 2},
            timeout=10
        )
        assert search_response.status_code == 200

        results = search_response.json()["results"]
        if len(results) > 0:
            top_result = results[0].get("content", results[0].get("text", ""))

            # Should retrieve the Data Structures section specifically
            assert "data structures" in top_result.lower() or \
                   "lists" in top_result.lower() or \
                   "tuples" in top_result.lower(), \
                   "Should retrieve chunk containing data structures content"

    def test_chunk_context_preservation(self):
        """Chunks should maintain section context in metadata"""
        content = """
# Machine Learning Course

## Week 1: Linear Regression
Linear regression models the relationship between variables.
Uses least squares method for optimization.

## Week 2: Classification
Classification assigns items to predefined categories.
Common algorithms include logistic regression and decision trees.
"""
        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "ml_course.md"},
            timeout=30
        )
        assert response.status_code == 200

        doc_id = response.json().get("doc_id")
        assert doc_id is not None

        time.sleep(2)

        # Search for classification content
        search_response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "classification decision trees categories", "top_k": 2},
            timeout=10
        )
        assert search_response.status_code == 200

        results = search_response.json()["results"]

        # Verify we get the right section
        if len(results) > 0:
            for result in results:
                metadata = result.get("metadata", {})
                content = result.get("content", result.get("text", "")).lower()

                # If this is our doc, check metadata preservation
                if "classification" in content and "decision trees" in content:
                    # Should have section context if available
                    # (This is implementation-dependent, so we check gracefully)
                    if "section_title" in metadata:
                        assert "classification" in metadata["section_title"].lower() or \
                               "week 2" in metadata["section_title"].lower(), \
                               "Chunk metadata should preserve section title"
                    break


class TestCrossDocumentRetrieval:
    """Test retrieval across multiple documents"""

    def test_multi_document_concept_search(self):
        """Search should find concept across multiple documents"""
        docs = [
            {
                "content": "Neural networks require large amounts of training data to achieve high accuracy.",
                "filename": "training_data.txt"
            },
            {
                "content": "Data augmentation techniques can artificially expand training datasets.",
                "filename": "data_augmentation.txt"
            },
            {
                "content": "Transfer learning allows models to leverage pre-trained weights from large datasets.",
                "filename": "transfer_learning.txt"
            }
        ]

        for doc in docs:
            requests.post(f"{BASE_URL}/ingest", json=doc, timeout=30)

        time.sleep(2)

        # Search for concept that spans all docs
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "training data for neural networks", "top_k": 5},
            timeout=10
        )
        assert response.status_code == 200

        results = response.json()["results"]

        # Should return multiple relevant chunks from different docs
        assert len(results) >= 2, "Should find relevant content from multiple documents"

        # All top results should be about training data / neural networks
        result_texts = " ".join([
            r.get("content", r.get("text", "")).lower()
            for r in results[:3]
        ])

        relevant_terms = ["training", "data", "neural", "model", "dataset"]
        matches = sum(1 for term in relevant_terms if term in result_texts)

        assert matches >= 3, f"Top results should be about training data, found {matches}/5 relevant terms"
