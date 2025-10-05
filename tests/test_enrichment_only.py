"""Quick test of enrichment service"""
import asyncio
import sys
sys.path.insert(0, '/Users/danielteckentrup/Documents/my-git/rag-provider')

from src.services.llm_service import LLMService
from src.services.enrichment_service import EnrichmentService
from src.core.dependencies import get_settings
from src.models.schemas import DocumentType

async def test_enrichment():
    settings = get_settings()
    llm_service = LLMService(settings)
    enrichment_service = EnrichmentService(llm_service)

    test_content = """This summary is for this video - Dr. Russell Barkley explains Adult ADHD (with actionable tips).

The video discusses executive function deficits in ADHD adults, time blindness, working memory issues, and practical strategies for managing symptoms."""

    print("Testing enrichment service...")
    print(f"Content length: {len(test_content)} chars\n")

    result = await enrichment_service.enrich_document(
        content=test_content,
        filename="adhd_summary.txt",
        document_type=DocumentType.text
    )

    print("Enrichment result:")
    for key, value in result.items():
        if len(str(value)) > 100:
            print(f"  {key}: {str(value)[:100]}...")
        else:
            print(f"  {key}: {value}")

if __name__ == "__main__":
    asyncio.run(test_enrichment())
