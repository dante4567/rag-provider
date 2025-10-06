"""
Enrichment Service V2 - Controlled Vocabulary & Advanced Features

Major improvements:
- Controlled vocabulary (no invented tags)
- Entities vs Topics separation
- Suggested tags for review
- Recency scoring
- Better title extraction
- Document type routing
"""

import hashlib
import json
import re
import math
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from src.services.llm_service import LLMService
from src.services.vocabulary_service import VocabularyService
from src.models.schemas import DocumentType


class EnrichmentService:
    """Enhanced enrichment with controlled vocabulary (formerly V2)"""

    def __init__(self, llm_service: LLMService, vocab_service: Optional[VocabularyService] = None):
        self.llm_service = llm_service

        # Load vocabulary service
        if vocab_service:
            self.vocab = vocab_service
        else:
            # Try to load from default location
            try:
                self.vocab = VocabularyService("vocabulary")
            except Exception as e:
                print(f"Warning: Could not load vocabulary service: {e}")
                self.vocab = None

    def generate_content_hash(self, content: str) -> str:
        """Generate SHA-256 hash for deduplication"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def calculate_recency_score(self, created_at: Optional[date] = None) -> float:
        """
        Calculate recency score with exponential decay

        - Today = 1.0
        - 1 month ago = 0.9
        - 6 months ago = 0.6
        - 1 year ago = 0.4
        - 2 years ago = 0.2
        - 5+ years ago = 0.05
        """
        if not created_at:
            created_at = date.today()

        today = date.today()
        age_days = (today - created_at).days

        # Exponential decay: score = e^(-lambda * age_days)
        # lambda = 0.003 gives ~6 month half-life
        decay_rate = 0.003
        score = math.exp(-decay_rate * age_days)

        return max(0.05, min(1.0, score))  # Clamp to [0.05, 1.0]

    def extract_title_from_content(self, content: str, filename: str) -> str:
        """
        Extract title using multiple strategies

        1. Look for title markers (# heading, Title:, etc.)
        2. Use first meaningful sentence
        3. Fall back to filename
        """
        # Strategy 1: Markdown heading
        heading_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if heading_match:
            title = heading_match.group(1).strip()
            if 5 <= len(title.split()) <= 15:
                return self.sanitize_title(title)

        # Strategy 2: Title: field
        title_field = re.search(r'^Title:\s*(.+)$', content, re.MULTILINE | re.IGNORECASE)
        if title_field:
            title = title_field.group(1).strip()
            if 5 <= len(title.split()) <= 15:
                return self.sanitize_title(title)

        # Strategy 3: First meaningful sentence (not too short, not too long)
        sentences = re.split(r'[.!?]\s+', content[:500])
        for sentence in sentences:
            words = sentence.strip().split()
            if 5 <= len(words) <= 15:
                return self.sanitize_title(sentence.strip())

        # Strategy 4: Clean up filename
        # Remove extension and common prefixes
        title = Path(filename).stem
        title = re.sub(r'^(document|file|untitled|scan)[-_\s]*', '', title, flags=re.IGNORECASE)
        title = title.replace('_', ' ').replace('-', ' ')
        title = re.sub(r'\s+', ' ', title).strip()

        return self.sanitize_title(title) if title else "Document"

    def sanitize_title(self, title: str, max_length: int = 100) -> str:
        """Clean and normalize title"""
        # Remove extra whitespace
        sanitized = re.sub(r'\s+', ' ', title).strip()

        # Remove special characters that cause issues
        sanitized = re.sub(r'[<>:"/\\|?*]', '', sanitized)

        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip()

        return sanitized or "Document"

    async def enrich_document(
        self,
        content: str,
        filename: str,
        document_type: DocumentType,
        created_at: Optional[date] = None,
        existing_metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Main enrichment function with controlled vocabulary

        Returns enriched metadata compatible with ChromaDB
        """
        existing_metadata = existing_metadata or {}

        # Generate content hash
        content_hash = self.generate_content_hash(content)

        # Extract title first (don't rely on LLM for this)
        extracted_title = self.extract_title_from_content(content, filename)

        # Calculate recency score
        recency_score = self.calculate_recency_score(created_at)

        # Build controlled vocabulary prompt
        prompt = self._build_controlled_enrichment_prompt(
            content=content,
            filename=filename,
            document_type=document_type,
            extracted_title=extracted_title
        )

        try:
            # Use Groq for enrichment
            llm_response_text, cost, model_used = await self.llm_service.call_llm(
                prompt=prompt,
                model_id="groq/llama-3.1-8b-instant",
                temperature=0.1
            )

            llm_data = self._parse_llm_response(llm_response_text)

            # Validate and clean with controlled vocabulary
            validated = self._validate_with_vocabulary(llm_data, created_at)

            # Build enriched metadata
            enriched = self._build_enriched_metadata(
                validated_data=validated,
                content_hash=content_hash,
                filename=filename,
                document_type=document_type,
                extracted_title=extracted_title,
                recency_score=recency_score,
                content=content,
                existing_metadata=existing_metadata,
                enrichment_cost=cost
            )

            return enriched

        except Exception as e:
            print(f"[ERROR] Enrichment V2 failed: {str(e)}")
            import traceback
            traceback.print_exc()

            # Fallback
            return self._fallback_metadata(
                content=content,
                content_hash=content_hash,
                filename=filename,
                document_type=document_type,
                extracted_title=extracted_title,
                recency_score=recency_score,
                existing_metadata=existing_metadata
            )

    def _build_controlled_enrichment_prompt(
        self,
        content: str,
        filename: str,
        document_type: DocumentType,
        extracted_title: str
    ) -> str:
        """Build enrichment prompt with controlled vocabulary"""

        # Get vocabulary lists
        all_topics = self.vocab.get_all_topics() if self.vocab else []
        all_places = self.vocab.get_all_places() if self.vocab else []

        # Truncate content
        content_sample = content[:3000]
        if len(content) > 3000:
            content_sample += "\n\n[...content truncated...]"

        # Build topic list for prompt
        topic_examples = all_topics[:20] if all_topics else [
            "school/admin", "kita/handover", "legal/custody",
            "education/concept", "admin/registration"
        ]

        prompt = f"""Extract metadata from this document using CONTROLLED VOCABULARIES.

**Filename**: {filename}
**Type**: {document_type}
**Extracted Title**: {extracted_title}

**Content**:
{content_sample}

IMPORTANT: Use ONLY the provided controlled vocabulary. Do not invent new tags.

Extract the following (return as JSON):

1. **summary**: 2-3 sentence summary of main content
2. **topics**: Array of topics from this CONTROLLED list:
   {json.dumps(topic_examples)}

   Only use topics from this list. If content matches multiple, choose the 3-5 most relevant.

3. **suggested_topics**: Array of NEW topics you think should be added to vocabulary
   (These will be reviewed by user, not used directly)

4. **entities**: Extract actual entities (NOT controlled):
   - organizations: Company/org names found in text
   - people_roles: Roles mentioned (e.g., "Teacher", "Principal") - NOT names
   - dates: Dates in ISO format (YYYY-MM-DD)
   - contacts: Email/phone if present

5. **places**: Places from content that match this list:
   {json.dumps(all_places[:15] if all_places else [])}
   Only use exact matches.

6. **quality_indicators**: Assess these (0-1 scores):
   - ocr_quality: How clean is the text? (1.0 = perfect, 0.5 = some issues, 0.0 = gibberish)
   - content_completeness: Is content complete? (1.0 = complete, 0.5 = partial, 0.0 = fragment)

Return ONLY this JSON structure (no markdown):
{{
  "summary": "Summary here",
  "topics": ["school/admin", "education/concept"],
  "suggested_topics": ["school/curriculum"],
  "entities": {{
    "organizations": ["Florianschule"],
    "people_roles": ["Principal", "Teacher"],
    "dates": ["2025-10-05"],
    "contacts": []
  }},
  "places": ["Essen"],
  "quality_indicators": {{
    "ocr_quality": 0.95,
    "content_completeness": 1.0
  }}
}}
"""
        return prompt

    def _parse_llm_response(self, response: str) -> Dict:
        """Parse LLM JSON response"""
        try:
            # Remove markdown code blocks
            cleaned = re.sub(r'^```json\n|\n```$', '', response.strip())
            cleaned = re.sub(r'^```\n|\n```$', '', cleaned.strip())
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
            return {}

    def _validate_with_vocabulary(self, llm_data: Dict, created_at: Optional[date]) -> Dict:
        """Validate extracted data against vocabulary, match projects"""

        validated = {}

        # Topics: Only keep valid ones
        proposed_topics = llm_data.get("topics", [])
        valid_topics = []
        invalid_topics = []

        if self.vocab:
            for topic in proposed_topics:
                if self.vocab.is_valid_topic(topic):
                    valid_topics.append(topic)
                else:
                    # Try to suggest closest match
                    suggested = self.vocab.suggest_topic(topic)
                    if self.vocab.is_valid_topic(suggested):
                        valid_topics.append(suggested)
                    else:
                        invalid_topics.append(topic)
        else:
            valid_topics = proposed_topics

        validated["topics"] = valid_topics
        validated["suggested_topics"] = llm_data.get("suggested_topics", []) + invalid_topics

        # Track suggested tags
        if self.vocab:
            for tag in validated["suggested_topics"]:
                self.vocab.track_suggestion(tag)

        # Places: Only keep valid ones
        proposed_places = llm_data.get("places", [])
        valid_places = []
        if self.vocab:
            valid_places = [p for p in proposed_places if self.vocab.is_valid_place(p)]
        else:
            valid_places = proposed_places

        validated["places"] = valid_places

        # Match projects based on topics
        matched_projects = []
        if self.vocab and valid_topics:
            matched_projects = self.vocab.match_projects_for_doc(valid_topics, created_at)

        validated["projects"] = matched_projects

        # Pass through other fields
        validated["summary"] = llm_data.get("summary", "")
        validated["entities"] = llm_data.get("entities", {})
        validated["quality_indicators"] = llm_data.get("quality_indicators", {})

        return validated

    def extract_enriched_lists(self, metadata: Dict) -> Dict:
        """Convert comma-separated strings in metadata back to lists"""
        return {
            "tags": [t.strip() for t in metadata.get("topics", "").split(",") if t.strip()],
            "key_points": [],  # Not stored in flat metadata
            "people": [p.strip() for p in metadata.get("people_roles", "").split(",") if p.strip()],
            "organizations": [o.strip() for o in metadata.get("organizations", "").split(",") if o.strip()],
            "locations": [l.strip() for l in metadata.get("places", "").split(",") if l.strip()],
            "dates": [d.strip() for d in metadata.get("dates", "").split(",") if d.strip()],
        }

    def _build_enriched_metadata(
        self,
        validated_data: Dict,
        content_hash: str,
        filename: str,
        document_type: DocumentType,
        extracted_title: str,
        recency_score: float,
        content: str,
        existing_metadata: Dict,
        enrichment_cost: float
    ) -> Dict:
        """Build flat metadata structure for ChromaDB"""

        # Get quality scores
        quality = validated_data.get("quality_indicators", {})
        ocr_quality = quality.get("ocr_quality", 0.8)
        completeness = quality.get("content_completeness", 1.0)

        # Calculate composite quality score
        quality_score = (ocr_quality * 0.6) + (completeness * 0.4)

        # Entities
        entities = validated_data.get("entities", {})

        # Define keys we're setting (to avoid duplicates from existing_metadata)
        known_keys = {
            "content_hash", "content_hash_short", "filename", "document_type",
            "title", "summary", "topics", "places", "projects",
            "suggested_topics", "organizations", "people_roles", "dates", "contacts",
            "quality_score", "recency_score", "ocr_quality",
            "enrichment_version", "enrichment_date", "enrichment_cost",
            "word_count", "char_count", "created_at", "enriched"
        }

        metadata = {
            # === IDENTITY ===
            "content_hash": content_hash,
            "content_hash_short": content_hash[:16],
            "filename": filename,
            "document_type": str(document_type),

            # === TITLE & SUMMARY ===
            "title": extracted_title,
            "summary": validated_data.get("summary", "")[:500],

            # === CONTROLLED VOCABULARY ===
            "topics": ",".join(validated_data.get("topics", [])),  # Controlled
            "places": ",".join(validated_data.get("places", [])),  # Controlled
            "projects": ",".join(validated_data.get("projects", [])),  # Auto-matched

            # === SUGGESTED (for review) ===
            "suggested_topics": ",".join(validated_data.get("suggested_topics", [])),

            # === EXTRACTED ENTITIES (not controlled) ===
            "organizations": ",".join(entities.get("organizations", [])[:10]),
            "people_roles": ",".join(entities.get("people_roles", [])[:10]),
            "dates": ",".join(entities.get("dates", [])[:10]),
            "contacts": ",".join(entities.get("contacts", [])[:5]),

            # === SCORING ===
            "quality_score": round(quality_score, 3),
            "recency_score": round(recency_score, 3),
            "ocr_quality": round(ocr_quality, 3),

            # === PROVENANCE ===
            "enrichment_version": "2.0",
            "enrichment_date": datetime.now().isoformat(),
            "enrichment_cost": round(enrichment_cost, 6),

            # === STATS ===
            "word_count": len(content.split()),
            "char_count": len(content),

            # === TIMESTAMPS ===
            "created_at": datetime.now().isoformat(),
            "enriched": True,

            # Preserve existing (that aren't in our known keys)
            **{k: str(v) for k, v in existing_metadata.items()
               if isinstance(v, (str, int, float, bool)) and k not in known_keys}
        }

        return metadata

    def _fallback_metadata(
        self,
        content: str,
        content_hash: str,
        filename: str,
        document_type: DocumentType,
        extracted_title: str,
        recency_score: float,
        existing_metadata: Dict
    ) -> Dict:
        """Fallback metadata if enrichment fails"""

        return {
            "content_hash": content_hash,
            "content_hash_short": content_hash[:16],
            "filename": filename,
            "document_type": str(document_type),
            "title": extracted_title,
            "summary": content[:500],
            "topics": "",
            "places": "",
            "projects": "",
            "organizations": "",
            "quality_score": 0.5,
            "recency_score": round(recency_score, 3),
            "enrichment_version": "2.0",
            "enriched": False,
            "word_count": len(content.split()),
            "created_at": datetime.now().isoformat(),
            **{k: str(v) for k, v in existing_metadata.items() if isinstance(v, (str, int, float, bool))}
        }
