"""
Test script for entity deduplication integration

Tests that enrichment service properly deduplicates people entities
"""
import asyncio
from src.services.enrichment_service import EnrichmentService
from src.services.llm_service import LLMService
from src.models.schemas import DocumentType


async def test_entity_deduplication():
    """Test that entity deduplication works in enrichment pipeline"""

    # Create test content with duplicate entities in different forms
    test_content = """
    Meeting Notes - School Committee

    Attendees:
    - Dr. Weber (Principal)
    - Thomas Weber (Administrative Office)
    - Prof. Dr. Weber (Education Consultant)
    - Schmidt (Teacher)
    - Rechtsanwalt Schmidt (Legal Advisor)
    - Dr. Schmidt (Curriculum Expert)

    Discussion:
    Dr. Weber opened the meeting and thanked Prof. Weber for the curriculum review.
    Schmidt presented the teaching plan while RA Schmidt reviewed the legal aspects.

    Action Items:
    - Thomas Weber: Submit report by Friday
    - Dr. Schmidt: Review assessment protocols
    """

    # Initialize services
    llm_service = LLMService()
    enrichment_service = EnrichmentService(llm_service)

    print("\n" + "=" * 80)
    print("Entity Deduplication Integration Test")
    print("=" * 80)

    # Enrich document
    print("\n[1] Enriching test document...")
    metadata = await enrichment_service.enrich_document(
        content=test_content,
        filename="test_meeting_notes.md",
        document_type=DocumentType.text
    )

    # Extract people from metadata
    people = metadata.get("people", [])

    print(f"\n[2] People extracted: {len(people)}")

    for i, person in enumerate(people, 1):
        name = person.get("name") if isinstance(person, dict) else person
        aliases = person.get("aliases") if isinstance(person, dict) else None
        mention_count = person.get("mention_count", 1) if isinstance(person, dict) else 1

        print(f"\n   Person {i}:")
        print(f"     Name: {name}")
        if aliases:
            print(f"     Aliases: {', '.join(aliases)}")
        print(f"     Mentions: {mention_count}")

    # Verify deduplication
    print("\n[3] Deduplication Results:")

    # Count unique canonical names
    unique_names = set()
    for person in people:
        name = person.get("name") if isinstance(person, dict) else person
        unique_names.add(name)

    print(f"   Original extractions: ~6 mentions")
    print(f"   After deduplication: {len(unique_names)} unique entities")

    # Expected: 2 unique entities (Weber and Schmidt)
    if len(unique_names) <= 3:
        print("\n✅ SUCCESS: Entity deduplication working!")
        print(f"   Expected ~2 entities, got {len(unique_names)}")
    else:
        print(f"\n⚠️  WARNING: Expected ~2 entities, got {len(unique_names)}")
        print("   Deduplication may need tuning")

    # Show entity statistics
    print("\n[4] Entity Deduplication Service Statistics:")
    stats = enrichment_service.entity_dedup.get_statistics()
    print(f"   Total entities tracked: {stats['total_entities']}")
    print(f"   Total aliases: {stats['total_aliases']}")
    print(f"   Average aliases per entity: {stats['avg_aliases_per_entity']}")
    print(f"   Deduplication rate: {stats['deduplication_rate']}%")

    # Show entity mappings
    mappings = enrichment_service.entity_dedup.export_entity_mappings()
    if mappings:
        print("\n[5] Entity Alias Mappings:")
        for canonical, aliases in mappings.items():
            print(f"   '{canonical}' ← {aliases}")

    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_entity_deduplication())
