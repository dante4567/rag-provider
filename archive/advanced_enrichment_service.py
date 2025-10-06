"""
Advanced Multi-Stage Enrichment Service

Uses multiple LLMs for specialized enrichment tasks:
- Stage 1: Fast tagging & classification (Groq - speed)
- Stage 2: Deep entity extraction (Claude - quality)
- Stage 3: OCR quality improvement (when needed)
- Stage 4: Significance scoring & confidence metrics
- Stage 5: Relationship & context analysis

Each document gets:
- Rich entity metadata (people, places, orgs with context)
- Confidence scores for extracted info
- Significance ratings
- Quality metrics
- Relationship links
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from src.services.llm_service import LLMService
from src.services.tag_taxonomy_service import TagTaxonomyService
from src.services.smart_triage_service import SmartTriageService
from src.models.schemas import DocumentType


class AdvancedEnrichmentService:
    """Multi-stage enrichment with multiple LLMs and quality metrics"""

    def __init__(self, llm_service: LLMService, tag_taxonomy: TagTaxonomyService, triage_service: SmartTriageService = None):
        self.llm_service = llm_service
        self.tag_taxonomy = tag_taxonomy
        self.triage_service = triage_service

    async def enrich_document(
        self,
        content: str,
        filename: str,
        document_type: DocumentType,
        existing_metadata: Optional[Dict] = None,
        enable_deep_enrichment: bool = True
    ) -> Dict:
        """
        Multi-stage enrichment pipeline

        Returns comprehensive metadata with confidence scores
        """
        existing_metadata = existing_metadata or {}

        # Generate content hash for deduplication
        import hashlib
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        # Refresh tag taxonomy
        await self.tag_taxonomy.refresh_tag_cache()

        # STAGE 1: Fast classification & tagging (Groq - $0.000001)
        stage1_result = await self._stage1_fast_classification(
            content, filename, document_type
        )

        # STAGE 2: Deep entity extraction (Claude - higher quality)
        if enable_deep_enrichment:
            stage2_result = await self._stage2_entity_extraction(
                content, stage1_result
            )
        else:
            stage2_result = {"entities": {}, "confidence": 0.5}

        # STAGE 3: OCR quality check (if low confidence from extraction)
        if document_type == DocumentType.pdf and stage2_result.get("confidence", 1.0) < 0.6:
            stage3_result = await self._stage3_ocr_quality(content, existing_metadata)
        else:
            stage3_result = {"ocr_quality": "good", "needs_reprocessing": False}

        # STAGE 4: Significance & quality scoring
        stage4_result = await self._stage4_significance_scoring(
            content, stage1_result, stage2_result
        )

        # STAGE 5: Tag validation & deduplication
        validated_tags = self.tag_taxonomy.validate_and_deduplicate_tags(
            stage1_result.get("tags", []),
            domain=stage1_result.get("domain", "general")
        )

        # Enrich tags with hierarchy
        enriched_tags = self.tag_taxonomy.enrich_tags_with_hierarchy(
            validated_tags,
            domain=stage1_result.get("domain")
        )

        # STAGE 6: Smart triage & actionable insights (if enabled)
        triage_result = {}
        if self.triage_service:
            from src.services.smart_triage_service import DocumentFingerprint

            # Generate fingerprint
            fingerprint = self.triage_service.generate_fingerprint(
                content=content,
                metadata={
                    "title": stage1_result.get("title", filename),
                    "domain": stage1_result.get("domain", "general"),
                    "created_at": datetime.now().isoformat()
                },
                entities=stage2_result.get("entities", {})
            )

            # Resolve entity aliases
            resolved_entities = self.triage_service.resolve_entity_aliases(
                stage2_result.get("entities", {})
            )

            # Triage decision
            triage_decision = self.triage_service.triage_document(
                content=content,
                metadata={
                    "title": stage1_result.get("title", filename),
                    "domain": stage1_result.get("domain", "general"),
                    "complexity": stage1_result.get("complexity", "intermediate"),
                    "significance_score": stage4_result.get("significance_score", 0.5)
                },
                entities=resolved_entities,
                fingerprint=fingerprint
            )

            triage_result = {
                "category": triage_decision.category,
                "confidence": triage_decision.confidence,
                "reasoning": " | ".join(triage_decision.reasoning[:3]),  # Top 3 reasons
                "actions_suggested": " | ".join(triage_decision.actions_suggested[:3]),
                "related_documents": ",".join(triage_decision.related_documents[:5]),
                "kb_updates_count": len(triage_decision.knowledge_updates),
                "is_duplicate": triage_decision.category == "duplicate",
                "is_junk": triage_decision.category == "junk",
                "is_actionable": "actionable" in triage_decision.category
            }

            print(f"[Stage6] Triage: {triage_decision.category} (confidence: {triage_decision.confidence:.2f})")
            if triage_decision.actions_suggested:
                print(f"[Stage6] Actions: {triage_decision.actions_suggested[0]}")

        # Build comprehensive flat metadata for ChromaDB
        enriched_metadata = self._build_comprehensive_metadata(
            content_hash=content_hash,
            filename=filename,
            document_type=document_type,
            content=content,
            stage1=stage1_result,
            stage2=stage2_result,
            stage3=stage3_result,
            stage4=stage4_result,
            stage6=triage_result,
            tags=enriched_tags,
            existing_metadata=existing_metadata
        )

        return enriched_metadata

    async def _stage1_fast_classification(
        self,
        content: str,
        filename: str,
        document_type: DocumentType
    ) -> Dict:
        """
        Stage 1: Fast classification, tagging, basic metadata
        Uses Groq (cheapest, fastest)
        """
        # Get tag suggestions from taxonomy
        tag_suggestions = self.tag_taxonomy.get_tag_suggestions_for_llm(
            content_preview=content[:500]
        )

        prompt = f"""Extract metadata from this document for knowledge management.

**Filename**: {filename}
**Type**: {document_type}
**Content** (first 2500 chars):
{content[:2500]}

{tag_suggestions}

Return ONLY valid JSON:
{{
  "title": "Descriptive title (5-15 words)",
  "summary": "2-3 sentence summary",
  "key_points": ["point 1", "point 2", "point 3"],
  "tags": ["tag1", "category/subcategory", "specific/descriptive/tag"],
  "domain": "main domain (e.g., technology, health, legal, psychology)",
  "complexity": "beginner|intermediate|advanced",
  "content_type": "article|transcript|documentation|personal|academic|technical"
}}
"""

        try:
            response_text, cost, model = await self.llm_service.call_llm(
                prompt=prompt,
                model_id="groq/llama-3.1-8b-instant",
                temperature=0.1
            )

            print(f"[Stage1] Fast classification cost: ${cost:.6f}")

            data = self._parse_json_response(response_text)

            return {
                **data,
                "stage1_cost": cost,
                "stage1_model": model
            }

        except Exception as e:
            print(f"[Stage1] Error: {e}")
            return {
                "title": filename,
                "summary": content[:200],
                "key_points": [],
                "tags": [],
                "domain": "general",
                "complexity": "intermediate",
                "content_type": "unknown",
                "stage1_cost": 0,
                "stage1_model": "fallback"
            }

    async def _stage2_entity_extraction(
        self,
        content: str,
        stage1_result: Dict
    ) -> Dict:
        """
        Stage 2: Deep entity extraction with context
        Uses Claude (better quality for entity extraction)
        """
        prompt = f"""Extract detailed entities and relationships from this document.

**Domain**: {stage1_result.get('domain', 'general')}
**Title**: {stage1_result.get('title', 'Unknown')}

**Content** (first 3000 chars):
{content[:3000]}

Return ONLY valid JSON with:
{{
  "entities": {{
    "people": [
      {{"name": "Full Name", "role": "description", "context": "why mentioned", "confidence": 0.0-1.0}}
    ],
    "organizations": [
      {{"name": "Org Name", "type": "company|institution|group", "context": "...", "confidence": 0.0-1.0}}
    ],
    "locations": [
      {{"name": "Place", "type": "city|country|region", "context": "...", "confidence": 0.0-1.0}}
    ],
    "concepts": [
      {{"name": "Key Concept", "definition": "brief explanation", "importance": "high|medium|low", "confidence": 0.0-1.0}}
    ],
    "dates": [
      {{"date": "YYYY-MM-DD or description", "event": "what happened", "confidence": 0.0-1.0}}
    ],
    "technologies": [
      {{"name": "Tech/Tool", "purpose": "what it's used for", "confidence": 0.0-1.0}}
    ]
  }},
  "relationships": [
    {{"entity1": "Name", "relation": "describes relationship", "entity2": "Name", "confidence": 0.0-1.0}}
  ],
  "overall_confidence": 0.0-1.0
}}

Confidence guidelines:
- 1.0: Explicitly stated, clear
- 0.8: Strong implication
- 0.6: Reasonable inference
- 0.4: Weak inference
- 0.2: Speculation
"""

        try:
            response_text, cost, model = await self.llm_service.call_llm(
                prompt=prompt,
                model_id="anthropic/claude-3-5-sonnet-latest",
                temperature=0.1
            )

            print(f"[Stage2] Entity extraction cost: ${cost:.6f}")

            data = self._parse_json_response(response_text)

            return {
                **data,
                "stage2_cost": cost,
                "stage2_model": model
            }

        except Exception as e:
            print(f"[Stage2] Error: {e}")
            return {
                "entities": {},
                "relationships": [],
                "overall_confidence": 0.5,
                "stage2_cost": 0,
                "stage2_model": "fallback"
            }

    async def _stage3_ocr_quality(
        self,
        content: str,
        existing_metadata: Dict
    ) -> Dict:
        """
        Stage 3: OCR quality assessment and potential re-processing suggestions
        """
        # Check for common OCR artifacts
        ocr_issues = []

        # Check 1: Excessive special characters
        special_char_ratio = len(re.findall(r'[^a-zA-Z0-9\s\.\,\!\?\-]', content)) / max(len(content), 1)
        if special_char_ratio > 0.15:
            ocr_issues.append("high_special_char_ratio")

        # Check 2: Broken words
        broken_words = len(re.findall(r'\b[a-z]{1,2}\s[a-z]{1,2}\b', content))
        if broken_words > 20:
            ocr_issues.append("broken_words")

        # Check 3: Missing spaces
        missing_spaces = len(re.findall(r'[a-z][A-Z]', content))
        if missing_spaces > 10:
            ocr_issues.append("missing_spaces")

        quality_score = 1.0 - (len(ocr_issues) * 0.2)

        return {
            "ocr_quality": "good" if quality_score > 0.7 else "poor" if quality_score < 0.4 else "moderate",
            "quality_score": max(0, quality_score),
            "issues": ocr_issues,
            "needs_reprocessing": quality_score < 0.6,
            "suggestions": self._get_ocr_suggestions(ocr_issues)
        }

    def _get_ocr_suggestions(self, issues: List[str]) -> List[str]:
        """Get suggestions for OCR improvement"""
        suggestions = []
        if "high_special_char_ratio" in issues:
            suggestions.append("Run OCR with better preprocessing (deskew, denoise)")
        if "broken_words" in issues:
            suggestions.append("Use dictionary-based post-processing")
        if "missing_spaces" in issues:
            suggestions.append("Apply word segmentation algorithm")
        return suggestions

    async def _stage4_significance_scoring(
        self,
        content: str,
        stage1_result: Dict,
        stage2_result: Dict
    ) -> Dict:
        """
        Stage 4: Assess document significance and quality
        """
        # Calculate significance based on multiple factors
        scores = {}

        # Entity richness (0-1)
        entities = stage2_result.get("entities", {})
        entity_count = sum(len(ent_list) for ent_list in entities.values() if isinstance(ent_list, list))
        scores["entity_richness"] = min(1.0, entity_count / 10)

        # Content depth (0-1)
        word_count = len(content.split())
        scores["content_depth"] = min(1.0, word_count / 1000)

        # Complexity alignment
        complexity = stage1_result.get("complexity", "intermediate")
        scores["complexity_score"] = {"beginner": 0.3, "intermediate": 0.6, "advanced": 0.9}.get(complexity, 0.5)

        # Key points quality (0-1)
        key_points = stage1_result.get("key_points", [])
        scores["key_points_quality"] = min(1.0, len(key_points) / 5)

        # Overall confidence from entity extraction
        scores["extraction_confidence"] = stage2_result.get("overall_confidence", 0.5)

        # Calculate overall significance
        significance = sum(scores.values()) / len(scores)

        return {
            "significance_score": round(significance, 3),
            "component_scores": scores,
            "quality_tier": "high" if significance > 0.7 else "medium" if significance > 0.4 else "low",
            "recommended_for_review": significance > 0.8 or stage2_result.get("overall_confidence", 1) < 0.6
        }

    def _build_comprehensive_metadata(
        self,
        content_hash: str,
        filename: str,
        document_type: DocumentType,
        content: str,
        stage1: Dict,
        stage2: Dict,
        stage3: Dict,
        stage4: Dict,
        stage6: Dict,
        tags: List[str],
        existing_metadata: Dict
    ) -> Dict:
        """Build flat metadata structure for ChromaDB"""

        # Extract entities into flat strings
        entities = stage2.get("entities", {})

        people_list = entities.get("people", [])
        people_names = [p.get("name", p) if isinstance(p, dict) else str(p) for p in people_list]
        people_contexts = [p.get("context", "") if isinstance(p, dict) else "" for p in people_list]
        people_confidence = [str(p.get("confidence", 0.5)) if isinstance(p, dict) else "0.5" for p in people_list]

        orgs_list = entities.get("organizations", [])
        orgs_names = [o.get("name", o) if isinstance(o, dict) else str(o) for o in orgs_list]

        locations_list = entities.get("locations", [])
        locations_names = [l.get("name", l) if isinstance(l, dict) else str(l) for l in locations_list]

        concepts_list = entities.get("concepts", [])
        concepts_names = [c.get("name", c) if isinstance(c, dict) else str(c) for c in concepts_list]

        technologies_list = entities.get("technologies", [])
        tech_names = [t.get("name", t) if isinstance(t, dict) else str(t) for t in technologies_list]

        dates_list = entities.get("dates", [])
        dates_strings = [d.get("date", d) if isinstance(d, dict) else str(d) for d in dates_list]

        # Build flat metadata
        metadata = {
            # Core identification
            "content_hash": content_hash,
            "content_hash_short": content_hash[:16],
            "filename": filename,
            "document_type": str(document_type),

            # Stage 1: Basic metadata
            "title": stage1.get("title", filename),
            "summary": stage1.get("summary", "")[:500],
            "domain": stage1.get("domain", "general"),
            "complexity": stage1.get("complexity", "intermediate"),
            "content_type": stage1.get("content_type", "unknown"),

            # Tags
            "tags": ",".join(tags),
            "tag_count": len(tags),

            # Key points
            "key_points": " | ".join(stage1.get("key_points", [])[:5]),
            "key_points_count": len(stage1.get("key_points", [])),

            # Stage 2: Entities (flat strings)
            "people": ",".join(people_names[:20]),
            "people_count": len(people_names),
            "people_contexts": " | ".join(people_contexts[:20]),
            "people_confidence": ",".join(people_confidence[:20]),

            "organizations": ",".join(orgs_names[:20]),
            "organizations_count": len(orgs_names),

            "locations": ",".join(locations_names[:20]),
            "locations_count": len(locations_names),

            "concepts": ",".join(concepts_names[:20]),
            "concepts_count": len(concepts_names),

            "technologies": ",".join(tech_names[:20]),
            "technologies_count": len(tech_names),

            "dates": ",".join(dates_strings[:20]),
            "dates_count": len(dates_strings),

            # Stage 3: OCR quality
            "ocr_quality": stage3.get("ocr_quality", "good"),
            "ocr_quality_score": stage3.get("quality_score", 1.0),
            "needs_ocr_reprocessing": stage3.get("needs_reprocessing", False),

            # Stage 4: Significance scores
            "significance_score": stage4.get("significance_score", 0.5),
            "quality_tier": stage4.get("quality_tier", "medium"),
            "entity_richness": stage4.get("component_scores", {}).get("entity_richness", 0.5),
            "content_depth": stage4.get("component_scores", {}).get("content_depth", 0.5),
            "extraction_confidence": stage4.get("component_scores", {}).get("extraction_confidence", 0.5),
            "recommended_for_review": stage4.get("recommended_for_review", False),

            # Stage 6: Triage & actionable insights
            "triage_category": stage6.get("category", "unknown"),
            "triage_confidence": stage6.get("confidence", 0.5),
            "triage_reasoning": stage6.get("reasoning", "")[:200],
            "triage_actions": stage6.get("actions_suggested", "")[:200],
            "related_doc_ids": stage6.get("related_documents", ""),
            "kb_updates_pending": stage6.get("kb_updates_count", 0),
            "is_duplicate": stage6.get("is_duplicate", False),
            "is_junk": stage6.get("is_junk", False),
            "is_actionable": stage6.get("is_actionable", False),

            # Costs
            "enrichment_cost_usd": stage1.get("stage1_cost", 0) + stage2.get("stage2_cost", 0),
            "enrichment_models": f"{stage1.get('stage1_model', 'unknown')},{stage2.get('stage2_model', 'unknown')}",

            # Stats
            "word_count": len(content.split()),
            "estimated_reading_time_min": max(1, len(content.split()) // 200),

            # Timestamps
            "created_at": datetime.now().isoformat(),
            "enriched_at": datetime.now().isoformat(),
            "enrichment_version": "2.0",  # Advanced multi-stage

            # Preserve existing metadata
            **{k: str(v) for k, v in existing_metadata.items() if isinstance(v, (str, int, float, bool))}
        }

        return metadata

    def _parse_json_response(self, response: str) -> Dict:
        """Parse LLM JSON response with error handling"""
        try:
            # Remove markdown code blocks
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

    def extract_enriched_lists(self, metadata: Dict) -> Dict:
        """Extract structured lists from flat metadata for display/export"""
        return {
            "tags": [t.strip() for t in metadata.get("tags", "").split(",") if t.strip()],
            "key_points": [p.strip() for p in metadata.get("key_points", "").split("|") if p.strip()],
            "people": [
                {
                    "name": name,
                    "context": context,
                    "confidence": float(conf)
                }
                for name, context, conf in zip(
                    metadata.get("people", "").split(","),
                    metadata.get("people_contexts", "").split("|"),
                    metadata.get("people_confidence", "").split(",")
                )
                if name.strip()
            ],
            "organizations": [o.strip() for o in metadata.get("organizations", "").split(",") if o.strip()],
            "locations": [l.strip() for l in metadata.get("locations", "").split(",") if l.strip()],
            "concepts": [c.strip() for c in metadata.get("concepts", "").split(",") if c.strip()],
            "technologies": [t.strip() for t in metadata.get("technologies", "").split(",") if t.strip()],
            "dates": [d.strip() for d in metadata.get("dates", "").split(",") if d.strip()]
        }
