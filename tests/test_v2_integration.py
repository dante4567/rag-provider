#!/usr/bin/env python3
"""
Test V2 Integration - Validate services work correctly

Tests:
1. VocabularyService loads correctly
2. EnrichmentServiceV2 can be initialized
3. ObsidianServiceV2 can be initialized
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_vocabulary_service():
    """Test vocabulary service loads"""
    print("\n" + "="*60)
    print("TEST 1: VocabularyService")
    print("="*60)

    try:
        # Direct import to avoid __init__.py dependency issues
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "vocabulary_service",
            "src/services/vocabulary_service.py"
        )
        vocab_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vocab_module)
        VocabularyService = vocab_module.VocabularyService

        vocab = VocabularyService("vocabulary")

        topics = vocab.get_all_topics()
        projects = vocab.get_active_projects()
        places = vocab.get_all_places()

        print(f"✅ Loaded {len(topics)} topics")
        print(f"✅ Loaded {len(projects)} projects")
        print(f"✅ Loaded {len(places)} places")

        # Test validation
        assert vocab.is_valid_topic("school/admin"), "Valid topic check failed"
        assert not vocab.is_valid_topic("nonexistent/topic"), "Invalid topic check failed"

        print("✅ Topic validation working")

        return True
    except Exception as e:
        print(f"❌ VocabularyService test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_enrichment_v2_init():
    """Test EnrichmentServiceV2 initialization"""
    print("\n" + "="*60)
    print("TEST 2: EnrichmentServiceV2 Initialization")
    print("="*60)

    try:
        from src.services.enrichment_service_v2 import EnrichmentServiceV2
        from src.services.vocabulary_service import VocabularyService
        from src.services.llm_service import LLMService
        from src.core.dependencies import get_settings

        # Initialize dependencies
        settings = get_settings()
        llm_service = LLMService(settings)
        vocab_service = VocabularyService("vocabulary")

        # Initialize V2
        enrichment_v2 = EnrichmentServiceV2(llm_service, vocab_service)

        print("✅ EnrichmentServiceV2 initialized")

        # Test title extraction
        test_content = "# School Enrollment Information\n\nThis document contains information about school enrollment."
        title = enrichment_v2.extract_title_from_content(test_content, "enrollment.pdf")
        print(f"✅ Title extraction: '{title}'")

        # Test recency scoring
        from datetime import date
        score_today = enrichment_v2.calculate_recency_score(date.today())
        score_old = enrichment_v2.calculate_recency_score(date(2020, 1, 1))
        print(f"✅ Recency scoring: today={score_today:.3f}, 2020={score_old:.3f}")

        assert score_today > score_old, "Recency scoring logic incorrect"

        return True
    except Exception as e:
        print(f"❌ EnrichmentServiceV2 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_obsidian_v2_init():
    """Test ObsidianServiceV2 initialization"""
    print("\n" + "="*60)
    print("TEST 3: ObsidianServiceV2 Initialization")
    print("="*60)

    try:
        from src.services.obsidian_service_v2 import ObsidianServiceV2
        from src.models.schemas import DocumentType
        import tempfile

        # Create temp output dir
        with tempfile.TemporaryDirectory() as temp_dir:
            obsidian_v2 = ObsidianServiceV2(output_dir=temp_dir)

            print("✅ ObsidianServiceV2 initialized")

            # Test metadata parsing
            test_metadata = {
                "topics": "school/admin,education/concept",
                "places": "Essen",
                "projects": "school-2026",
                "organizations": "Test School",
                "quality_score": 0.94
            }

            parsed = obsidian_v2.parse_metadata_lists(test_metadata)
            print(f"✅ Metadata parsing: {len(parsed['topics'])} topics parsed")

            # Test YAML generation
            from datetime import datetime
            yaml_output = obsidian_v2.build_clean_yaml_frontmatter(
                title="Test Document",
                metadata=test_metadata,
                document_type=DocumentType.pdf,
                created_at=datetime.now(),
                content_hash="abc123"
            )

            # Verify YAML is valid
            import yaml
            yaml_data = yaml.safe_load(yaml_output.split('---')[1])
            assert 'title' in yaml_data, "YAML missing title"
            assert yaml_data['type'] == 'pdf', "YAML type incorrect"

            print("✅ YAML generation working")
            print(f"   Sample output:")
            print(yaml_output[:200] + "...")

        return True
    except Exception as e:
        print(f"❌ ObsidianServiceV2 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n🧪 V2 Integration Tests")
    print("="*60)

    results = {
        "VocabularyService": test_vocabulary_service(),
        "EnrichmentServiceV2": test_enrichment_v2_init(),
        "ObsidianServiceV2": test_obsidian_v2_init()
    }

    print("\n" + "="*60)
    print("RESULTS SUMMARY")
    print("="*60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")

    all_passed = all(results.values())

    if all_passed:
        print("\n🎉 All tests passed! V2 integration ready.")
        return 0
    else:
        print("\n❌ Some tests failed. Review errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
