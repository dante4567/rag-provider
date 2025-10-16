"""
ChromaDB Adapter - Centralized format conversions

PURPOSE:
    ChromaDB only supports flat key-value metadata (strings, numbers, bools).
    Our API and enrichment services use nested Pydantic models.
    This adapter is the SINGLE SOURCE OF TRUTH for conversions.

DATA FORMATS:
    API Format (nested):
        {
            "entities": {
                "people": ["Name1", "Name2"],
                "organizations": ["Org1", "Org2"],
                "locations": ["Place1"],
                "technologies": ["Tech1"]
            }
        }

    ChromaDB Format (flat strings):
        {
            "people": "Name1,Name2",
            "organizations": "Org1,Org2",
            "locations": "Place1",
            "technologies": "Tech1"
        }

CRITICAL: All format conversions MUST go through this adapter.
"""

from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ChromaDBAdapter:
    """
    Adapter for converting between API format (nested) and ChromaDB format (flat).

    This class solves the impedance mismatch between:
    - Pydantic models (structured, validated, nested)
    - ChromaDB metadata (flat key-value, strings only)
    """

    # Field names for entity lists
    ENTITY_FIELDS = ["people", "organizations", "locations", "technologies"]

    # Field names for list fields (not entities)
    LIST_FIELDS = ["tags", "key_points", "dates", "dates_detailed", "people_detailed"]

    @staticmethod
    def flatten_entities_for_storage(
        people: List[str],
        organizations: List[str],
        locations: List[str],
        technologies: List[str]
    ) -> Dict[str, str]:
        """
        Convert entity lists to comma-separated strings for ChromaDB.

        Args:
            people: List of person names
            organizations: List of organization names
            locations: List of place names
            technologies: List of technology names

        Returns:
            Dict with comma-separated string values (empty string if no items)

        Example:
            >>> flatten_entities_for_storage(
            ...     people=["Alice", "Bob"],
            ...     organizations=["ACME Corp"],
            ...     locations=[],
            ...     technologies=["Python"]
            ... )
            {
                "people": "Alice,Bob",
                "organizations": "ACME Corp",
                "locations": "",
                "technologies": "Python"
            }
        """
        result = {}

        if people:
            result["people"] = ",".join(str(p).strip() for p in people if p)
        if organizations:
            result["organizations"] = ",".join(str(o).strip() for o in organizations if o)
        if locations:
            result["locations"] = ",".join(str(l).strip() for l in locations if l)
        if technologies:
            result["technologies"] = ",".join(str(t).strip() for t in technologies if t)

        return result

    @staticmethod
    def parse_entity_field(value: Any, field_name: str) -> List[str]:
        """
        Parse an entity field from ChromaDB format to list format.

        Handles multiple input formats:
        - String (comma-separated): "Name1,Name2" → ["Name1", "Name2"]
        - List: ["Name1", "Name2"] → ["Name1", "Name2"]
        - None/empty: → []

        Args:
            value: Field value from ChromaDB metadata
            field_name: Field name (for logging)

        Returns:
            List of parsed values (empty list if no data)

        Example:
            >>> parse_entity_field("Alice,Bob,Charlie", "people")
            ["Alice", "Bob", "Charlie"]

            >>> parse_entity_field(["Alice", "Bob"], "people")
            ["Alice", "Bob"]

            >>> parse_entity_field("", "people")
            []
        """
        if not value:
            return []

        if isinstance(value, str):
            if not value.strip():
                return []
            # Split on comma and clean
            return [item.strip() for item in value.split(",") if item.strip()]

        elif isinstance(value, list):
            # Already a list, just clean
            return [str(item).strip() for item in value if item]

        else:
            logger.warning(f"Unexpected type for {field_name}: {type(value)}, value: {value}")
            return [str(value)]

    @classmethod
    def parse_entities_from_storage(cls, metadata: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Parse all entity fields from ChromaDB metadata.

        Args:
            metadata: ChromaDB metadata dict

        Returns:
            Dict with entity field names mapped to lists

        Example:
            >>> parse_entities_from_storage({
            ...     "people": "Alice,Bob",
            ...     "organizations": "ACME Corp",
            ...     "locations": "",
            ...     "title": "Test Doc"
            ... })
            {
                "people": ["Alice", "Bob"],
                "organizations": ["ACME Corp"],
                "locations": [],
                "technologies": []
            }
        """
        result = {}

        for field in cls.ENTITY_FIELDS:
            value = metadata.get(field)
            result[field] = cls.parse_entity_field(value, field)

        return result

    @staticmethod
    def sanitize_for_chromadb(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize metadata dict for ChromaDB storage.

        ChromaDB requirements:
        - Only str, int, float, bool values
        - No None values
        - No nested dicts or lists

        Args:
            metadata: Raw metadata dict

        Returns:
            Sanitized metadata dict safe for ChromaDB
        """
        sanitized = {}

        for key, value in metadata.items():
            if value is None:
                continue

            # Handle basic types
            if isinstance(value, (str, int, float, bool)):
                sanitized[key] = value

            # Convert lists to comma-separated strings
            elif isinstance(value, list):
                # Skip empty lists
                if not value:
                    continue
                # Convert to comma-separated string
                sanitized[key] = ",".join(str(v) for v in value if v)

            # Convert dicts to JSON string (last resort)
            elif isinstance(value, dict):
                logger.debug(f"Converting dict field {key} to string (consider flattening)")
                import json
                sanitized[key] = json.dumps(value)

            # Convert everything else to string
            else:
                sanitized[key] = str(value)

        return sanitized


class MetadataContract:
    """
    Documentation of metadata contracts at different pipeline stages.

    This is not executable code - it's documentation showing the
    expected metadata shape at each stage of the ingestion pipeline.
    """

    # Stage 1: Enrichment Output (Pydantic model)
    ENRICHMENT_OUTPUT = {
        "title": "Document Title",
        "summary": "Document summary text",
        "entities": {
            "people": ["Name1", "Name2"],
            "organizations": ["Org1"],
            "locations": ["Place1"],
            "technologies": ["Tech1"]
        },
        "tags": ["tag1", "tag2"],
        "dates": ["2025-01-01"],
        # ... other fields
    }

    # Stage 2: Flattened for ChromaDB (via ChromaDBAdapter)
    CHROMADB_FORMAT = {
        "title": "Document Title",
        "summary": "Document summary text",
        "people": "Name1,Name2",  # ⭐ Flattened
        "organizations": "Org1",   # ⭐ Flattened
        "locations": "Place1",     # ⭐ Flattened
        "technologies": "Tech1",   # ⭐ Flattened
        "tags": "tag1,tag2",       # ⭐ Flattened
        "dates": "2025-01-01",     # ⭐ Flattened
        # ... other scalar fields
    }

    # Stage 3: Retrieved from ChromaDB (raw)
    CHROMADB_RETRIEVAL = {
        # Same as CHROMADB_FORMAT
        # But now we need to parse back to structured format
    }

    # Stage 4: Parsed for API Response (via ChromaDBAdapter)
    API_RESPONSE = {
        # Same as ENRICHMENT_OUTPUT
        # Entities reconstructed as nested objects
    }
