"""
Document Enrichment Service

Core enrichment for RAG pipeline:
- LLM-based summarization, tagging, entity extraction
- Content hash generation for deduplication
- Meaningful title generation
- Hierarchical tag assignment
- Signal-to-noise improvement for better RAG quality

This enrichment improves:
1. Search quality (better embeddings from cleaned content)
2. Retrieval relevance (rich metadata for filtering)
3. LLM context (summaries reduce token usage)
4. User experience (meaningful filenames, organized tags)
"""

import hashlib
import json
import re
from datetime import datetime
from typing import Dict, List, Optional

from src.services.llm_service import LLMService
from src.models.schemas import DocumentType


class EnrichmentService:
    """Service for enriching documents with LLM-generated metadata"""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    def generate_content_hash(self, content: str) -> str:
        """Generate SHA-256 hash for deduplication"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def sanitize_title(self, title: str, max_length: int = 100) -> str:
        """Clean and normalize title"""
        # Remove extra whitespace
        sanitized = re.sub(r'\s+', ' ', title).strip()
        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip()
        return sanitized or "Untitled"

    async def enrich_document(
        self,
        content: str,
        filename: str,
        document_type: DocumentType,
        existing_metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Main enrichment function - uses LLM to extract high-quality metadata

        Returns enriched metadata dict compatible with ChromaDB (flat key-value)
        """

        existing_metadata = existing_metadata or {}

        # Generate content hash first (for deduplication)
        content_hash = self.generate_content_hash(content)

        # Prepare enrichment prompt
        prompt = self._build_enrichment_prompt(content, filename, document_type)

        try:
            # Use Groq (cheapest at $0.000001/query)
            llm_response_text, cost, model_used = await self.llm_service.call_llm(
                prompt=prompt,
                model_id="groq/llama-3.1-8b-instant",
                temperature=0.1  # Low temperature for consistent JSON output
            )
            print(f"[DEBUG] LLM raw response length: {len(llm_response_text)}")
            print(f"[DEBUG] LLM raw response preview: {llm_response_text[:500]}")

            llm_data = self._parse_llm_response(llm_response_text)

            print(f"[DEBUG] Parsed LLM data keys: {list(llm_data.keys())}")
            print(f"[DEBUG] Parsed title: {llm_data.get('title', 'NONE')}")
            print(f"[DEBUG] Parsed tags: {llm_data.get('tags', [])}")

            # Build enriched metadata (flat structure for ChromaDB)
            enriched = self._build_flat_metadata(
                llm_data=llm_data,
                content_hash=content_hash,
                filename=filename,
                document_type=document_type,
                existing_metadata=existing_metadata,
                content_preview=content[:500]
            )

            return enriched

        except Exception as e:
            # Log the error
            print(f"[ERROR] Enrichment failed: {str(e)}")
            import traceback
            traceback.print_exc()

            # Fallback to basic metadata if LLM fails
            return self._fallback_metadata(
                content=content,
                content_hash=content_hash,
                filename=filename,
                document_type=document_type,
                existing_metadata=existing_metadata
            )

    def _build_enrichment_prompt(
        self,
        content: str,
        filename: str,
        document_type: DocumentType
    ) -> str:
        """Build LLM prompt for metadata extraction"""

        # Truncate content to avoid token limits (use first ~3000 chars)
        content_sample = content[:3000]
        if len(content) > 3000:
            content_sample += "\n\n[...content truncated...]"

        prompt = f"""Extract metadata from this document for a knowledge management system.

**Filename**: {filename}
**Type**: {document_type}

**Content**:
{content_sample}

Extract the following (return as JSON):

1. **title**: Descriptive title (5-12 words, captures core idea)
2. **summary**: 2-3 sentence summary of main points
3. **key_points**: Array of 3-5 key takeaways (short phrases)
4. **tags**: Array of relevant hierarchical tags. Use these categories:
   - Content workflow: cont/in/read, cont/in/extract, cont/zk/connect
   - Content type: literature, permanent, fleeting
   - Navigation: hub, project/active, index
   - Domain-specific tags based on content
5. **entities**: Object with arrays for people, organizations, locations, dates
6. **complexity**: One of: beginner, intermediate, advanced
7. **domain**: Main topic domain (e.g., technology, science, business)

Return ONLY this JSON structure (no markdown, no explanation):
{{
  "title": "Descriptive Title Here",
  "summary": "Summary text here",
  "key_points": ["point 1", "point 2", "point 3"],
  "tags": ["cont/in/read", "literature", "technology"],
  "entities": {{
    "people": ["Name1", "Name2"],
    "organizations": ["Org1"],
    "locations": ["Location1"],
    "dates": ["2025-10-05"]
  }},
  "complexity": "intermediate",
  "domain": "technology"
}}
"""
        return prompt

    def _parse_llm_response(self, response: str) -> Dict:
        """Parse LLM JSON response, handle errors gracefully"""
        try:
            # Remove markdown code blocks if present
            cleaned = re.sub(r'^```json\n|\n```$', '', response.strip())
            cleaned = re.sub(r'^```\n|\n```$', '', cleaned.strip())
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON from text
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
            return {}

    def _build_flat_metadata(
        self,
        llm_data: Dict,
        content_hash: str,
        filename: str,
        document_type: DocumentType,
        existing_metadata: Dict,
        content_preview: str
    ) -> Dict:
        """Build flat metadata structure compatible with ChromaDB"""

        # ChromaDB only supports: str, int, float, bool
        # So we flatten complex structures into strings

        metadata = {
            # Core identification
            "content_hash": content_hash,
            "content_hash_short": content_hash[:16],  # For display
            "filename": filename,
            "document_type": str(document_type),

            # LLM-enriched fields
            "title": self.sanitize_title(llm_data.get("title", filename)),
            "summary": llm_data.get("summary", content_preview)[:500],  # Limit length
            "domain": llm_data.get("domain", "general"),
            "complexity": llm_data.get("complexity", "intermediate"),

            # Tags as comma-separated string
            "tags": ",".join(llm_data.get("tags", [])),

            # Key points as numbered string
            "key_points": " | ".join(llm_data.get("key_points", [])[:5]),

            # Entities as comma-separated strings
            "people": ",".join(llm_data.get("entities", {}).get("people", [])[:10]),
            "organizations": ",".join(llm_data.get("entities", {}).get("organizations", [])[:10]),
            "locations": ",".join(llm_data.get("entities", {}).get("locations", [])[:10]),
            "dates": ",".join(llm_data.get("entities", {}).get("dates", [])[:10]),

            # Reading stats
            "word_count": len(content_preview.split()),
            "estimated_reading_time_min": max(1, len(content_preview.split()) // 200),

            # Timestamps
            "created_at": datetime.now().isoformat(),
            "enriched": True,

            # Preserve existing metadata
            **{k: str(v) for k, v in existing_metadata.items() if isinstance(v, (str, int, float, bool))}
        }

        return metadata

    def _fallback_metadata(
        self,
        content: str,
        content_hash: str,
        filename: str,
        document_type: DocumentType,
        existing_metadata: Dict
    ) -> Dict:
        """Fallback metadata if LLM enrichment fails"""

        return {
            "content_hash": content_hash,
            "content_hash_short": content_hash[:16],
            "filename": filename,
            "document_type": str(document_type),
            "title": filename,
            "summary": content[:200] + "..." if len(content) > 200 else content,
            "domain": "general",
            "complexity": "intermediate",
            "tags": f"{document_type}",
            "key_points": "",
            "people": "",
            "organizations": "",
            "locations": "",
            "dates": "",
            "word_count": len(content.split()),
            "estimated_reading_time_min": max(1, len(content.split()) // 200),
            "created_at": datetime.now().isoformat(),
            "enriched": False,
            **{k: str(v) for k, v in existing_metadata.items() if isinstance(v, (str, int, float, bool))}
        }

    def extract_tags_list(self, metadata: Dict) -> List[str]:
        """Extract tags list from flat metadata (for display/export)"""
        tags_str = metadata.get("tags", "")
        return [t.strip() for t in tags_str.split(",") if t.strip()]

    def extract_key_points_list(self, metadata: Dict) -> List[str]:
        """Extract key points list from flat metadata (for display/export)"""
        points_str = metadata.get("key_points", "")
        return [p.strip() for p in points_str.split("|") if p.strip()]

    def check_duplicate(self, content_hash: str, existing_hashes: List[str]) -> bool:
        """Check if this content hash already exists"""
        return content_hash in existing_hashes
