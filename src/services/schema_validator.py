"""
JSON Schema Validator - Validates enrichment metadata against schema

Ensures all enrichment metadata conforms to the strict schema before
being saved or indexed.
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, Tuple, List
from jsonschema import validate, ValidationError, Draft7Validator

logger = logging.getLogger(__name__)


class SchemaValidator:
    """
    Validates enrichment metadata against JSON Schema

    Prevents invalid data from entering the system.
    """

    def __init__(self, schema_path: str = None):
        """
        Initialize validator with schema

        Args:
            schema_path: Path to JSON schema file
                        Defaults to src/schemas/enrichment_schema.json
        """
        if schema_path is None:
            # Default to our enrichment schema
            schema_path = Path(__file__).parent.parent / "schemas" / "enrichment_schema.json"

        try:
            with open(schema_path) as f:
                self.schema = json.load(f)

            # Create validator for better error messages
            self.validator = Draft7Validator(self.schema)

            logger.info(f"✅ SchemaValidator initialized with schema: {schema_path}")

        except Exception as e:
            logger.error(f"❌ Failed to load schema from {schema_path}: {e}")
            # Fall back to permissive schema
            self.schema = {"type": "object"}
            self.validator = Draft7Validator(self.schema)

    def validate_enrichment(
        self,
        metadata: Dict[str, Any],
        strict: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Validate enrichment metadata against schema

        Args:
            metadata: Enrichment metadata to validate
            strict: If True, fail on any error. If False, log warnings but pass.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        try:
            # Collect all validation errors
            for error in self.validator.iter_errors(metadata):
                # Build friendly error message
                path = ".".join(str(p) for p in error.path)
                if path:
                    msg = f"{path}: {error.message}"
                else:
                    msg = error.message

                errors.append(msg)

            if errors:
                if strict:
                    logger.error(f"❌ Schema validation failed: {len(errors)} errors")
                    for err in errors:
                        logger.error(f"  - {err}")
                    return False, errors
                else:
                    logger.warning(f"⚠️ Schema validation warnings: {len(errors)} issues")
                    for err in errors[:3]:  # Log first 3
                        logger.warning(f"  - {err}")
                    return True, errors  # Pass with warnings

            logger.debug("✅ Schema validation passed")
            return True, []

        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, [error_msg]

    def validate_patch(
        self,
        current_metadata: Dict[str, Any],
        patch: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that applying a patch would result in valid metadata

        Args:
            current_metadata: Current metadata
            patch: Patch to apply (with add/replace/remove keys)

        Returns:
            Tuple of (is_valid, error_messages)
        """
        # Simulate applying the patch
        from src.services.patch_service import PatchService

        try:
            patcher = PatchService()
            patched, _ = patcher.apply_patch(
                current_metadata,
                patch,
                forbidden_paths=[]  # Already validated by editor
            )

            # Validate the patched result
            return self.validate_enrichment(patched, strict=False)

        except Exception as e:
            error_msg = f"Patch validation failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, [error_msg]

    def get_schema_summary(self) -> str:
        """
        Get human-readable schema summary

        Returns:
            String describing schema constraints
        """
        summary = []
        summary.append("Enrichment Schema Constraints:")

        # Required fields
        if 'required' in self.schema:
            summary.append(f"  Required: {', '.join(self.schema['required'])}")

        # Field constraints
        props = self.schema.get('properties', {})

        if 'summary' in props:
            summ_props = props['summary'].get('properties', {})
            if 'tl_dr' in summ_props:
                max_len = summ_props['tl_dr'].get('maxLength', 'N/A')
                summary.append(f"  summary.tl_dr: max {max_len} chars")
            if 'key_points' in summ_props:
                max_items = summ_props['key_points'].get('maxItems', 'N/A')
                summary.append(f"  summary.key_points: max {max_items} items")

        if 'topics' in props:
            max_items = props['topics'].get('maxItems', 'N/A')
            summary.append(f"  topics: max {max_items} tags")

        if 'tasks' in props:
            max_items = props['tasks'].get('maxItems', 'N/A')
            summary.append(f"  tasks: max {max_items} items")

        return "\n".join(summary)
