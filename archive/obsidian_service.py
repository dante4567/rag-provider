"""
Obsidian Service - SmartNotes/Zettelkasten Export

Generates Obsidian-compatible markdown files following the user's SmartNotes methodology:
- Descriptive filenames with content hash for deduplication
- YAML frontmatter with bibliographic metadata
- Dataview inline fields (project::, hub::, area::, up::)
- Hierarchical tags (#cont/in/read, #hub/moc, #project/active)
- LLM enrichment for summaries, tags, entities
- Permanent note structure compatible with note-sequences
"""

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.services.llm_service import LLMService
from src.models.schemas import DocumentType


class ObsidianService:
    """Service for generating Obsidian-compatible markdown exports"""

    def __init__(self, llm_service: LLMService, output_dir: str = "./obsidian_vault"):
        self.llm_service = llm_service
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_content_hash(self, content: str) -> str:
        """Generate SHA-256 hash of content for deduplication"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:8]

    def sanitize_filename(self, title: str, max_length: int = 100) -> str:
        """Convert title to valid filename (remove special chars, limit length)"""
        # Remove/replace invalid filename characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
        # Replace spaces with hyphens
        sanitized = re.sub(r'\s+', '-', sanitized)
        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')
        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip('-')
        return sanitized or "untitled"

    def extract_enriched_data_from_metadata(self, metadata: Dict) -> Dict:
        """Extract enriched data from ChromaDB metadata (already enriched by AdvancedEnrichmentService)"""

        # Parse comma-separated strings back to lists
        def parse_csv(value: str) -> List[str]:
            if not value:
                return []
            return [item.strip() for item in value.split(",") if item.strip()]

        # Extract entities
        entities = {
            "people": parse_csv(metadata.get("people", "")),
            "organizations": parse_csv(metadata.get("organizations", "")),
            "locations": parse_csv(metadata.get("locations", "")),
            "dates": parse_csv(metadata.get("dates", ""))
        }

        # Extract tags (already hierarchical from tag taxonomy)
        tags = parse_csv(metadata.get("tags", ""))
        tags_with_hash = [f"#{tag}" if not tag.startswith("#") else tag for tag in tags]

        return {
            "title": metadata.get("title", "Untitled"),
            "summary": metadata.get("summary", ""),
            "key_points": [],  # Not extracted in current enrichment
            "tags": tags_with_hash,
            "entities": entities,
            "complexity": metadata.get("complexity", "intermediate"),
            "reading_time": f"{metadata.get('estimated_reading_time_min', 0)} min",
            "significance": metadata.get("significance_score", 0.0),
            "quality_tier": metadata.get("quality_tier", "medium")
        }

    def determine_workflow_tags(self, document_type: DocumentType, source: str) -> List[str]:
        """Determine workflow tags based on document type and source"""
        tags = []

        # Input processing tags
        if document_type in [DocumentType.pdf, DocumentType.webpage]:
            tags.append("#cont/in/read")
            tags.append("#literature")
        elif document_type == DocumentType.email:
            tags.append("#cont/in/extract")
        else:
            tags.append("#cont/in/add")

        # Content type tags
        if "transcript" in source.lower():
            tags.append("#cont/transcript")

        return tags

    def generate_yaml_frontmatter(
        self,
        title: str,
        enriched_data: Dict,
        metadata: Dict,
        document_type: DocumentType,
        source: str,
        created_at: datetime,
        content_hash: str
    ) -> str:
        """Generate YAML frontmatter for Obsidian"""

        # Extract author from metadata if available
        author = metadata.get("author", "")

        # Combine enriched tags with workflow tags
        all_tags = enriched_data.get("tags", [])
        all_tags.extend(self.determine_workflow_tags(document_type, source))

        frontmatter = f"""---
title: "{title}"
author: "{author}"
type: {document_type}
date_added: {created_at.strftime('%Y-%m-%d')}
source: "{source}"
hash: {content_hash}
tags: {all_tags}
complexity: {enriched_data.get('complexity', 'intermediate')}
reading_time: {enriched_data.get('reading_time', '0 min')}
---

"""
        return frontmatter

    def generate_dataview_metadata(self, metadata: Dict) -> str:
        """Generate dataview inline metadata fields"""
        lines = []

        # Add dataview fields if available
        if metadata.get("project"):
            lines.append(f"project:: [[{metadata['project']}]]")
        if metadata.get("hub"):
            lines.append(f"hub:: [[{metadata['hub']}]]")
        if metadata.get("area"):
            lines.append(f"area:: {metadata['area']}")
        if metadata.get("up"):
            lines.append(f"up:: [[{metadata['up']}]]")

        return "\n".join(lines) + "\n\n" if lines else ""

    def generate_literature_note_header(
        self,
        title: str,
        enriched_data: Dict,
        metadata: Dict,
        document_type: DocumentType,
        source: str
    ) -> str:
        """Generate literature note header (for external sources)"""

        if document_type not in [DocumentType.pdf, DocumentType.webpage]:
            return ""

        header = f"""# Literature Note: {title}

## Bibliographic Information

- **Title**:: {title}
- **Author(s)**:: {metadata.get('author', 'Unknown')}
- **Type**:: {document_type}
- **Publication**:: {metadata.get('publication', '')}
- **Date**:: {metadata.get('publication_date', '')}
- **Source**:: {source}

## Summary

{enriched_data.get('summary', '')}

## Key Points

"""
        for i, point in enumerate(enriched_data.get('key_points', []), 1):
            header += f"{i}. {point}\n"

        return header + "\n"

    def format_content_as_permanent_note(self, content: str, enriched_data: Dict) -> str:
        """Format content as Zettelkasten permanent note structure"""

        # Split content into paragraphs (atomic ideas)
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

        formatted = "## Notes\n\n"

        for i, para in enumerate(paragraphs[:10], 1):  # Limit to first 10 paragraphs
            # Each paragraph is an atomic note within the note-sequence
            formatted += f"### {i}. Atomic Note\n\n"
            formatted += f"{para}\n\n"

        # Add entities section if available
        entities = enriched_data.get('entities', {})
        if any(entities.values()):
            formatted += "## Entities\n\n"
            if entities.get('people'):
                formatted += f"**People**: {', '.join([f'[[{p}]]' for p in entities['people']])}\n\n"
            if entities.get('organizations'):
                formatted += f"**Organizations**: {', '.join([f'[[{o}]]' for o in entities['organizations']])}\n\n"
            if entities.get('locations'):
                formatted += f"**Locations**: {', '.join(entities['locations'])}\n\n"

        return formatted

    async def export_to_obsidian(
        self,
        doc_id: str,
        content: str,
        enriched_metadata: Dict,
        document_type: DocumentType,
        source: str
    ) -> Tuple[Path, Dict]:
        """
        Export document to Obsidian-compatible markdown using already-enriched metadata

        Args:
            doc_id: Document ID
            content: Document content
            enriched_metadata: Metadata already enriched by AdvancedEnrichmentService
            document_type: Type of document
            source: Source filename or URL

        Returns:
            Tuple of (file_path, enriched_data)
        """

        # Generate content hash for deduplication
        content_hash = self.generate_content_hash(content)

        # Extract enriched data from metadata (already processed by AdvancedEnrichmentService)
        enriched_data = self.extract_enriched_data_from_metadata(enriched_metadata)
        title = enriched_data.get("title", "Untitled")

        # Generate filename: {descriptive-title}_{hash}.md
        sanitized_title = self.sanitize_filename(title)
        filename = f"{sanitized_title}_{content_hash}.md"
        file_path = self.output_dir / filename

        # Check for duplicates
        if file_path.exists():
            # File already exists (same content hash) - skip
            return file_path, enriched_data

        # Build markdown document
        markdown_content = ""

        # 1. YAML frontmatter
        markdown_content += self.generate_yaml_frontmatter(
            title=title,
            enriched_data=enriched_data,
            metadata=enriched_metadata,
            document_type=document_type,
            source=source,
            created_at=datetime.now(),
            content_hash=content_hash
        )

        # 2. Dataview inline metadata (enriched_metadata has all fields)
        markdown_content += self.generate_dataview_metadata(enriched_metadata)

        # 3. Literature note header (if applicable)
        markdown_content += self.generate_literature_note_header(
            title=title,
            enriched_data=enriched_data,
            metadata=enriched_metadata,
            document_type=document_type,
            source=source
        )

        # 4. Content formatted as permanent notes
        markdown_content += self.format_content_as_permanent_note(content, enriched_data)

        # 5. Footer with metadata
        markdown_content += f"\n\n---\n*Document ID*: `{doc_id}`\n*Content Hash*: `{content_hash}`\n"

        # Write to file
        file_path.write_text(markdown_content, encoding='utf-8')

        return file_path, enriched_data

    def find_duplicate(self, content_hash: str) -> Optional[Path]:
        """Check if a document with this content hash already exists"""
        for md_file in self.output_dir.glob(f"*_{content_hash}.md"):
            return md_file
        return None
