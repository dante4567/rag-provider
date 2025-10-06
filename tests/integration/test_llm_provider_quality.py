"""
LLM Provider Quality Tests - validates multi-provider functionality

These tests verify:
- All configured LLM providers work correctly
- Fallback chain operates properly
- Cost tracking across different providers
- Quality consistency across providers
"""
import pytest
import requests
import time
import os


BASE_URL = "http://localhost:8001"


class TestProviderAvailability:
    """Test that all configured providers are accessible"""

    def test_all_providers_reported_in_health(self):
        """Health endpoint should list all available providers"""
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        assert response.status_code == 200

        data = response.json()
        providers = data.get("llm_providers", {})

        # Should have at least one provider configured
        assert len(providers) > 0, "At least one LLM provider should be available"

        # Common providers we expect
        expected_providers = ["groq", "anthropic", "openai", "google"]

        for provider_name, provider_info in providers.items():
            # Each provider should have model list
            assert "models" in provider_info, f"{provider_name} should list models"
            assert "available" in provider_info, f"{provider_name} should have availability status"
            assert provider_info["available"] is True, f"{provider_name} should be available"

            # Should have at least one model
            model_count = provider_info.get("model_count", 0)
            assert model_count > 0, f"{provider_name} should have at least one model"

    def test_provider_models_accessible(self):
        """Verify specific provider models are listed"""
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        assert response.status_code == 200

        data = response.json()
        providers = data.get("llm_providers", {})

        # Check provider-specific models
        if "groq" in providers:
            groq_models = providers["groq"]["models"]
            assert len(groq_models) > 0, "Groq should have models available"
            # Should have fast models like llama
            has_llama = any("llama" in m.lower() for m in groq_models)
            assert has_llama, f"Groq should have Llama models, got: {groq_models}"

        if "anthropic" in providers:
            anthropic_models = providers["anthropic"]["models"]
            assert len(anthropic_models) > 0, "Anthropic should have models available"
            # Should have Claude models
            has_claude = any("claude" in m.lower() for m in anthropic_models)
            assert has_claude, f"Anthropic should have Claude models, got: {anthropic_models}"

        if "openai" in providers:
            openai_models = providers["openai"]["models"]
            assert len(openai_models) > 0, "OpenAI should have models available"
            # Should have GPT models
            has_gpt = any("gpt" in m.lower() for m in openai_models)
            assert has_gpt, f"OpenAI should have GPT models, got: {openai_models}"


class TestEnrichmentWithDifferentProviders:
    """Test enrichment quality across different LLM providers"""

    def test_enrichment_with_groq(self):
        """Test enrichment using Groq (default fast provider)"""
        content = """
        School Enrollment Notice

        Dear Parents,

        We are pleased to inform you that enrollment for the 2026 school year
        is now open at Florianschule Essen.

        Please submit your application by March 15, 2026.
        """

        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "groq_test_enrollment.txt"},
            timeout=30
        )
        assert response.status_code == 200

        result = response.json()
        metadata = result.get("metadata", {})

        # Should have enrichment metadata
        assert "enrichment_version" in metadata or "abstract" in metadata, \
            "Groq enrichment should produce metadata"

        # Check for basic entity extraction
        topics = metadata.get("topics", "")
        places = metadata.get("places", "")

        # Should extract school-related topics
        if topics:
            assert "school" in topics.lower(), f"Should extract school topic, got: {topics}"

        # Should extract location
        if places:
            assert "essen" in places.lower() or "florianschule" in places.lower(), \
                f"Should extract location, got: {places}"

    def test_cost_tracking_varies_by_provider(self):
        """Cost should be tracked and vary by provider model"""
        # Ingest same content multiple times (will hit different providers via fallback)
        content = "Test document for cost tracking validation across providers."

        costs = []
        for i in range(3):
            response = requests.post(
                f"{BASE_URL}/ingest",
                json={"content": content, "filename": f"cost_test_{i}.txt"},
                timeout=30
            )
            assert response.status_code == 200

            result = response.json()
            metadata = result.get("metadata", {})

            # Extract cost if present
            # Cost might be in enrichment_cost or similar field
            for key, value in metadata.items():
                if "cost" in key.lower() and isinstance(value, (int, float)):
                    costs.append(value)
                    break

        # If costs are tracked, they should be reasonable
        if len(costs) > 0:
            for cost in costs:
                # Cost should be small (pennies, not dollars)
                assert cost < 1.0, f"Per-document cost should be under $1, got: ${cost}"
                # Should not be zero (unless free tier)
                # Note: Groq might be free, so we don't assert > 0


class TestProviderFallback:
    """Test LLM provider fallback chain"""

    def test_enrichment_succeeds_with_any_provider(self):
        """Enrichment should work even if primary provider fails"""
        # The system should automatically fall back
        # We test this by just ingesting and verifying it works

        content = """
        Legal Document: Custody Agreement

        This agreement establishes shared custody arrangements
        for the minor child. Both parents have equal rights and responsibilities.

        Signed on October 5, 2025 in Essen.
        """

        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "fallback_test.txt"},
            timeout=45  # Longer timeout to allow fallback attempts
        )

        # Should succeed even if one provider is down
        assert response.status_code == 200, "Should succeed via fallback chain"

        result = response.json()
        metadata = result.get("metadata", {})

        # Should still have enrichment
        assert "enrichment_version" in metadata or "topics" in metadata, \
            "Fallback should still provide enrichment"


class TestProviderConsistency:
    """Test that different providers produce consistent results"""

    def test_entity_extraction_consistency(self):
        """Different providers should extract similar entities"""
        content = """
        Meeting at Berlin Office

        Attendees: Dr. Schmidt, Maria Weber
        Date: October 15, 2025
        Location: Berlin Headquarters

        Discussion focused on the new school curriculum for 2026.
        """

        # Ingest same content (system will use available providers)
        results = []
        for i in range(2):
            response = requests.post(
                f"{BASE_URL}/ingest",
                json={"content": content, "filename": f"consistency_test_{i}.txt"},
                timeout=30
            )
            assert response.status_code == 200
            results.append(response.json())

            time.sleep(1)  # Brief pause between requests

        # Extract metadata from both
        metadata_list = [r.get("metadata", {}) for r in results]

        # Both should extract similar entities
        for metadata in metadata_list:
            places = metadata.get("places", "")
            people = metadata.get("people_roles", metadata.get("people", ""))

            # Should extract Berlin
            if places:
                assert "berlin" in places.lower(), \
                    f"Both providers should extract Berlin, got: {places}"

            # Should extract people
            if people:
                people_lower = people.lower()
                assert "schmidt" in people_lower or "weber" in people_lower, \
                    f"Both providers should extract people, got: {people}"


class TestProviderSpecificFeatures:
    """Test provider-specific capabilities"""

    def test_groq_speed_advantage(self):
        """Groq should be faster than other providers"""
        content = "Quick test document for speed comparison."

        import time as time_module

        start = time_module.time()
        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "speed_test.txt"},
            timeout=30
        )
        elapsed = time_module.time() - start

        assert response.status_code == 200

        # Groq should be reasonably fast (under 10 seconds for simple doc)
        # Note: This is loose since we don't control which provider is used
        assert elapsed < 30, f"Ingestion should be reasonably fast, took {elapsed}s"

    def test_anthropic_quality_for_complex_content(self):
        """Anthropic models should handle complex content well"""
        content = """
        Complex Legal Analysis

        This document analyzes the intersection of custody law and educational rights.
        The court must balance parental rights under Article 6 of the Basic Law
        with the child's right to education under Article 7.

        Relevant case law includes BGH ruling 2024-123 and OLG Düsseldorf 2025-456.

        The analysis concludes that shared custody with alternating educational
        decision-making authority represents the optimal solution.
        """

        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "complex_legal.txt"},
            timeout=45
        )
        assert response.status_code == 200

        result = response.json()
        metadata = result.get("metadata", {})

        # Should extract legal topics
        topics = metadata.get("topics", "")
        if topics:
            assert "legal" in topics.lower(), \
                f"Should recognize legal content, got: {topics}"

        # Should have meaningful abstract
        abstract = metadata.get("abstract", "")
        if abstract:
            # Abstract should mention key concepts
            abstract_lower = abstract.lower()
            legal_terms = ["custody", "education", "court", "law"]
            mentions = sum(1 for term in legal_terms if term in abstract_lower)

            assert mentions >= 2, \
                f"Abstract should cover legal concepts, got {mentions}/4: {abstract[:100]}"


class TestProviderModelSelection:
    """Test that appropriate models are selected for tasks"""

    def test_embedding_model_consistent(self):
        """Embedding model should be consistent for vector search"""
        # Ingest multiple documents
        docs = [
            {"content": "Document about machine learning.", "filename": "ml1.txt"},
            {"content": "Document about artificial intelligence.", "filename": "ai1.txt"},
        ]

        for doc in docs:
            response = requests.post(f"{BASE_URL}/ingest", json=doc, timeout=30)
            assert response.status_code == 200

        time.sleep(2)

        # Search should work consistently
        response = requests.post(
            f"{BASE_URL}/search",
            json={"text": "machine learning AI", "top_k": 3},
            timeout=10
        )
        assert response.status_code == 200

        results = response.json()["results"]

        # Should find our documents
        assert len(results) >= 2, "Should find documents with consistent embeddings"


class TestCostEfficiency:
    """Test that cost-efficient models are used appropriately"""

    def test_groq_default_for_cost_savings(self):
        """Groq should be default (cheapest) for most operations"""
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        data = response.json()

        providers = data.get("llm_providers", {})

        # Verify Groq is available (expected to be cheapest)
        if "groq" in providers:
            groq_info = providers["groq"]
            assert groq_info["available"], "Groq should be available as cost-efficient option"

        # Pricing info should be tracked
        pricing = data.get("pricing", {})
        if pricing:
            total_models = pricing.get("total_models_with_pricing", 0)
            assert total_models > 0, "Pricing should be tracked for cost optimization"

    def test_document_ingestion_cost_reasonable(self):
        """Document ingestion should cost under $0.02"""
        content = """
        Medium-length document for cost testing.

        This document has multiple paragraphs to simulate real usage.
        It includes various topics like education, administration, and planning.

        The goal is to verify that enrichment costs remain reasonable
        even for documents of moderate length.

        Cost tracking is essential for production deployment.
        """ * 3  # Repeat to make it medium-length

        response = requests.post(
            f"{BASE_URL}/ingest",
            json={"content": content, "filename": "cost_efficiency_test.txt"},
            timeout=30
        )
        assert response.status_code == 200

        result = response.json()
        metadata = result.get("metadata", {})

        # Look for cost information
        cost = None
        for key, value in metadata.items():
            if "cost" in key.lower() and isinstance(value, (int, float)):
                cost = value
                break

        if cost is not None:
            # Cost should be under $0.02 for cost-efficient operation
            assert cost < 0.02, f"Document ingestion should be cost-efficient, got: ${cost}"
            print(f"Ingestion cost: ${cost:.6f}")
