"""
LLM-as-Editor Service - Generates safe JSON patches for enrichment improvement

This service takes critic feedback and generates validated JSON patches that:
1. Never modify forbidden fields (id, source, vector refs)
2. Stay within schema constraints (max lengths, item counts)
3. Respect controlled vocabulary
4. Only output valid JSON patches
"""

import logging
import json
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class EditorService:
    """
    LLM-based YAML editor that generates safe JSON patches

    Implements the "editor" half of the LLM-as-critic pattern.
    Takes critic suggestions and generates validated patches.
    """

    # Fields that MUST NEVER be modified
    FORBIDDEN_PATHS = [
        'id',
        'source.type',
        'source.path',
        'source.url',
        'source.content_hash',
        'rag.vector_ref.collection',
        'rag.vector_ref.doc_id',
        'doc_time.created',
    ]

    def __init__(self, llm_service):
        """
        Initialize editor service

        Args:
            llm_service: LLMService instance for calling LLM
        """
        self.llm_service = llm_service
        logger.info("🔧 EditorService initialized")

    def _build_editor_prompt(
        self,
        current_metadata: Dict[str, Any],
        critic_suggestions: str,
        body_text: str,
        controlled_vocab: Dict[str, List[str]]
    ) -> str:
        """
        Build the editor prompt with all context

        Args:
            current_metadata: Current enrichment metadata
            critic_suggestions: Suggestions from critic
            body_text: Original document text
            controlled_vocab: Available tags/topics

        Returns:
            Formatted prompt for LLM
        """
        # Format controlled vocabulary
        vocab_str = "\n".join([
            f"  {category}: {', '.join(tags)}"
            for category, tags in controlled_vocab.items()
        ])

        prompt = f"""You are a YAML Frontmatter Editor for a RAG enrichment system.

STRICT RULES - YOU MUST FOLLOW THESE:
1. Output ONLY a JSON object with keys: "add", "replace", "remove"
2. NEVER modify these forbidden fields: {', '.join(self.FORBIDDEN_PATHS)}
3. Constraints:
   - summary.tl_dr: ≤600 characters (not words, CHARACTERS)
   - summary.key_points: ≤5 items
   - topics: ≤5 tags, MUST be from controlled vocabulary below
   - people_roles: Use format "Name (role)" e.g. "John Doe (author)"
4. Use controlled vocabulary only - do not invent new tags
5. Do not hallucinate dates - omit if not explicit in document
6. Keep patches minimal - only fix what critic identified

CONTROLLED VOCABULARY:
{vocab_str}

CURRENT METADATA:
{json.dumps(current_metadata, indent=2)}

CRITIC FEEDBACK:
{critic_suggestions}

DOCUMENT TEXT (for context):
{body_text[:2000]}...

OUTPUT FORMAT (JSON only):
{{
  "add": {{
    "entities.places": ["New Place"],
    "tasks": [{{"text": "Do something", "due": "2025-10-15", "status": "todo"}}]
  }},
  "replace": {{
    "summary.tl_dr": "Improved summary under 600 chars"
  }},
  "remove": ["topics[2]"]
}}

Generate the patch now:"""

        return prompt

    async def generate_patch(
        self,
        current_metadata: Dict[str, Any],
        critic_suggestions: str,
        body_text: str,
        controlled_vocab: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        Generate a safe JSON patch from critic suggestions

        Args:
            current_metadata: Current enrichment metadata
            critic_suggestions: Text suggestions from critic
            body_text: Original document text
            controlled_vocab: Available tags (optional)

        Returns:
            JSON patch dict with keys: add, replace, remove

        Raises:
            ValueError: If LLM output is invalid or touches forbidden paths
        """
        # Default controlled vocab if not provided
        if controlled_vocab is None:
            controlled_vocab = {
                "topics": ["education", "health", "finance", "technology"],
                "projects": []
            }

        # Build prompt
        prompt = self._build_editor_prompt(
            current_metadata,
            critic_suggestions,
            body_text,
            controlled_vocab
        )

        try:
            # Call LLM with strict JSON output
            response = await self.llm_service.call_llm(
                messages=[{"role": "user", "content": prompt}],
                model="groq/llama-3.1-8b-instant",  # Fast and cheap for patches
                temperature=0.0,  # Deterministic
                max_tokens=1000
            )

            # Extract JSON from response
            patch = self._extract_json_patch(response)

            # Validate patch doesn't touch forbidden paths
            self._validate_patch_paths(patch)

            # Validate patch structure
            self._validate_patch_structure(patch)

            logger.info(f"✅ Generated patch with {len(patch.get('add', {}))} adds, "
                       f"{len(patch.get('replace', {}))} replaces, "
                       f"{len(patch.get('remove', []))} removes")

            return patch

        except Exception as e:
            logger.error(f"❌ Failed to generate patch: {e}")
            # Return empty patch rather than failing
            return {"add": {}, "replace": {}, "remove": []}

    def _extract_json_patch(self, llm_response: str) -> Dict[str, Any]:
        """
        Extract JSON patch from LLM response

        LLM might wrap JSON in markdown code blocks or add text.
        This extracts the JSON reliably.

        Args:
            llm_response: Raw LLM output

        Returns:
            Parsed JSON patch

        Raises:
            ValueError: If no valid JSON found
        """
        # Try direct parse first
        try:
            return json.loads(llm_response)
        except json.JSONDecodeError:
            pass

        # Look for JSON in code blocks
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', llm_response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Look for any JSON object
        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"No valid JSON found in LLM response: {llm_response[:200]}")

    def _validate_patch_paths(self, patch: Dict[str, Any]) -> None:
        """
        Ensure patch doesn't touch forbidden fields

        Args:
            patch: JSON patch to validate

        Raises:
            ValueError: If patch touches forbidden paths
        """
        for action in ['add', 'replace']:
            if action in patch:
                for path in patch[action].keys():
                    # Check if path starts with any forbidden path
                    for forbidden in self.FORBIDDEN_PATHS:
                        if path == forbidden or path.startswith(forbidden + '.'):
                            raise ValueError(
                                f"❌ Patch cannot modify forbidden field: {path}"
                            )

        # For remove, check the paths too
        if 'remove' in patch:
            for path in patch['remove']:
                # Remove array indices like "topics[2]"
                base_path = path.split('[')[0]
                for forbidden in self.FORBIDDEN_PATHS:
                    if base_path == forbidden or base_path.startswith(forbidden + '.'):
                        raise ValueError(
                            f"❌ Patch cannot remove forbidden field: {path}"
                        )

    def _validate_patch_structure(self, patch: Dict[str, Any]) -> None:
        """
        Validate patch has correct structure

        Args:
            patch: JSON patch to validate

        Raises:
            ValueError: If patch structure is invalid
        """
        # Must have at least one of: add, replace, remove
        if not any(k in patch for k in ['add', 'replace', 'remove']):
            raise ValueError("Patch must have at least one of: add, replace, remove")

        # add and replace must be dicts
        if 'add' in patch and not isinstance(patch['add'], dict):
            raise ValueError("Patch 'add' must be a dict")

        if 'replace' in patch and not isinstance(patch['replace'], dict):
            raise ValueError("Patch 'replace' must be a dict")

        # remove must be a list
        if 'remove' in patch and not isinstance(patch['remove'], list):
            raise ValueError("Patch 'remove' must be a list")

        # Validate constraints on known fields
        if 'add' in patch or 'replace' in patch:
            combined = {**patch.get('add', {}), **patch.get('replace', {})}

            # Check summary.tl_dr length (600 chars max)
            if 'summary.tl_dr' in combined:
                tl_dr = combined['summary.tl_dr']
                if len(tl_dr) > 600:
                    raise ValueError(
                        f"summary.tl_dr too long: {len(tl_dr)} chars (max 600)"
                    )

            # Check key_points count (5 max)
            if 'summary.key_points' in combined:
                points = combined['summary.key_points']
                if isinstance(points, list) and len(points) > 5:
                    raise ValueError(
                        f"summary.key_points too many: {len(points)} items (max 5)"
                    )

            # Check topics count (5 max)
            if 'topics' in combined:
                topics = combined['topics']
                if isinstance(topics, list) and len(topics) > 5:
                    raise ValueError(
                        f"topics too many: {len(topics)} tags (max 5)"
                    )
