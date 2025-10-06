"""
Obsidian Service V2 - Clean YAML Export for SmartNotes

Improvements:
- Clean YAML formatting (no Python str representations)
- Uses V2 enrichment metadata (entities vs topics)
- Proper list formatting
- Compatible with Dataview queries
- Follows SmartNotes methodology
"""

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import yaml

from src.models.schemas import DocumentType


class ObsidianServiceV2:
    """Generate clean Obsidian-compatible markdown with proper YAML"""

    def __init__(self, output_dir: str = "./obsidian_vault"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_content_hash(self, content: str) -> str:
        """Generate short SHA-256 hash"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:8]

    def sanitize_filename(self, title: str, max_length: int = 100) -> str:
        """Convert title to valid filename"""
        # Remove invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
        # Replace spaces with hyphens
        sanitized = re.sub(r'\s+', '-', sanitized)
        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')
        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip('-')
        return sanitized or "document"

    def parse_metadata_lists(self, metadata: Dict) -> Dict:
        """Parse comma-separated strings from V2 enrichment into lists"""

        def parse_csv(value: str) -> List[str]:
            if not value or value == "":
                return []
            return [item.strip() for item in value.split(",") if item.strip()]

        return {
            # Controlled vocabulary
            "topics": parse_csv(metadata.get("topics", "")),
            "places": parse_csv(metadata.get("places", "")),
            "projects": parse_csv(metadata.get("projects", "")),

            # Suggested (for review)
            "suggested_topics": parse_csv(metadata.get("suggested_topics", "")),

            # Extracted entities
            "organizations": parse_csv(metadata.get("organizations", "")),
            "people_roles": parse_csv(metadata.get("people_roles", "")),
            "dates": parse_csv(metadata.get("dates", "")),
            "contacts": parse_csv(metadata.get("contacts", ""))
        }

    def build_clean_yaml_frontmatter(
        self,
        title: str,
        metadata: Dict,
        document_type: DocumentType,
        created_at: datetime,
        content_hash: str
    ) -> str:
        """
        Generate clean YAML frontmatter

        Outputs proper YAML that Obsidian can parse correctly
        """

        # Parse V2 metadata
        parsed = self.parse_metadata_lists(metadata)

        # Build frontmatter dict
        frontmatter_dict = {
            "id": f"{created_at.strftime('%Y%m%d')}_{content_hash}",
            "title": title,
            "source": metadata.get("filename", ""),
            "type": str(document_type).replace("DocumentType.", ""),  # Clean enum
            "created_at": created_at.strftime('%Y-%m-%d'),
            "ingested_at": metadata.get("enrichment_date", datetime.now().isoformat())[:10],

            # Summary
            "summary": metadata.get("summary", "")[:200],  # Truncate for YAML

            # Controlled vocabulary
            "topics": parsed["topics"],
            "places": parsed["places"],
            "projects": parsed["projects"],

            # Entities (extracted, not controlled)
            "entities": {
                "organizations": parsed["organizations"],
                "people_roles": parsed["people_roles"],
                "dates": parsed["dates"],
                "contacts": parsed["contacts"]
            },

            # Scoring
            "quality_score": float(metadata.get("quality_score", 0.0)),
            "recency_score": float(metadata.get("recency_score", 1.0)),

            # Suggested (for review)
            "suggested_topics": parsed["suggested_topics"],

            # Provenance
            "hash": content_hash,
            "enrichment_version": metadata.get("enrichment_version", "2.0")
        }

        # Remove empty fields to keep YAML clean
        frontmatter_dict = {k: v for k, v in frontmatter_dict.items()
                           if v not in [[], {}, "", None, 0.0]}

        # Use PyYAML for proper formatting
        yaml_str = yaml.dump(
            frontmatter_dict,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False
        )

        return f"---\n{yaml_str}---\n\n"

    def build_dataview_fields(self, metadata: Dict, parsed: Dict) -> str:
        """
        Generate Dataview inline fields

        Format: field:: value
        """
        lines = []

        # Project links
        for project in parsed.get("projects", []):
            lines.append(f"project:: [[{project}]]")

        # Add custom dataview fields if present
        if metadata.get("hub"):
            lines.append(f"hub:: [[{metadata['hub']}]]")
        if metadata.get("area"):
            lines.append(f"area:: {metadata['area']}")

        return "\n".join(lines) + "\n\n" if lines else ""

    def build_document_body(
        self,
        content: str,
        metadata: Dict,
        parsed: Dict
    ) -> str:
        """Build clean markdown body"""

        body_parts = []

        # Summary (if not in frontmatter)
        summary = metadata.get("summary", "")
        if summary:
            body_parts.append(f"## Summary\n\n{summary}\n")

        # Organizations mentioned
        if parsed.get("organizations"):
            body_parts.append("## Organizations\n\n")
            for org in parsed["organizations"]:
                body_parts.append(f"- {org}\n")
            body_parts.append("\n")

        # Key dates
        if parsed.get("dates"):
            body_parts.append("## Key Dates\n\n")
            for date_str in parsed["dates"]:
                body_parts.append(f"- {date_str}\n")
            body_parts.append("\n")

        # Main content
        body_parts.append("## Content\n\n")
        body_parts.append(content)

        # Suggested topics (for review)
        if parsed.get("suggested_topics"):
            body_parts.append("\n\n---\n\n")
            body_parts.append("## Metadata Review\n\n")
            body_parts.append("**Suggested Topics** (review and approve):\n")
            for topic in parsed["suggested_topics"]:
                body_parts.append(f"- [ ] `{topic}`\n")

        return "".join(body_parts)

    def export_document(
        self,
        title: str,
        content: str,
        metadata: Dict,
        document_type: DocumentType,
        created_at: Optional[datetime] = None
    ) -> Path:
        """
        Export document to Obsidian vault

        Returns: Path to created file
        """

        created_at = created_at or datetime.now()
        content_hash = self.generate_content_hash(content)

        # Parse metadata
        parsed = self.parse_metadata_lists(metadata)

        # Generate filename: YYYYMMDD_title_hash.md
        safe_title = self.sanitize_filename(title)
        filename = f"{created_at.strftime('%Y%m%d')}_{safe_title}_{content_hash}.md"
        file_path = self.output_dir / filename

        # Build document
        parts = []

        # 1. YAML frontmatter
        parts.append(self.build_clean_yaml_frontmatter(
            title, metadata, document_type, created_at, content_hash
        ))

        # 2. Dataview fields
        parts.append(self.build_dataview_fields(metadata, parsed))

        # 3. Document body
        parts.append(self.build_document_body(content, metadata, parsed))

        # Write file
        file_path.write_text("".join(parts), encoding='utf-8')

        return file_path

    def export_to_obsidian(
        self,
        title: str,
        content: str,
        metadata: Dict,
        document_type: DocumentType = DocumentType.text,
        created_at: Optional[datetime] = None
    ) -> str:
        """
        Main export function (backward compatible)

        Returns: Path to created file (as string)
        """
        path = self.export_document(title, content, metadata, document_type, created_at)
        return str(path)


# Example usage and test
if __name__ == "__main__":
    # Test metadata (from V2 enrichment)
    test_metadata = {
        "filename": "Schulkonzept.pdf",
        "summary": "School concept document covering educational philosophy and methods.",
        "topics": "school/admin,education/concept",
        "places": "Essen,Florianschule Essen",
        "projects": "school-2026",
        "suggested_topics": "school/curriculum,education/methodology",
        "organizations": "Florianschule,Stadt Essen",
        "people_roles": "Principal,Teacher",
        "dates": "2025-10-05",
        "quality_score": 0.94,
        "recency_score": 0.95,
        "enrichment_version": "2.0",
        "enrichment_date": "2025-10-05T21:25:00"
    }

    service = ObsidianServiceV2("./test_obsidian")

    result = service.export_to_obsidian(
        title="Schulkonzept - Florianschule Essen",
        content="# Educational Concept\n\nThis document describes...",
        metadata=test_metadata,
        document_type=DocumentType.pdf
    )

    print(f"✅ Exported to: {result}")
    print("\nGenerated YAML preview:")
    print(Path(result).read_text()[:500])
