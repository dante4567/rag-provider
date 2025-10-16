"""
Obsidian Service V3 - RAG-First, Obsidian-Happy

Implements the complete RAG/Obsidian integration design:
- Immutable, pipeline-owned MD+YAML
- Rich graphs & dashboards "for free"
- Zero impact on chunking/embeddings
- Auto-generated entity stubs for backlinks
- Read-only vault with perfect integration

Filename: YYYY-MM-DDTHH-MM-SS_doc_type_slug_shortid.md
Example: 2025-10-02T14-30-45_email_kita-handover_7c1a.md
Schema: Single unified frontmatter (no Obsidian-only fields)
"""

import hashlib
import logging
import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from slugify import slugify

from src.models.schemas import DocumentType

logger = logging.getLogger(__name__)


class ObsidianService:
    """
    Generate RAG-first Obsidian notes with entity stubs (formerly V3)

    Philosophy:
    - Pipeline owns the canonical MD files (immutable)
    - Obsidian gets graph edges via auto-generated xrefs
    - Entity stubs created automatically for backlinks
    - Chunker ignores RAG:IGNORE blocks
    """

    def __init__(
        self,
        output_dir: str = "./obsidian_vault",
        refs_dir: str = "./obsidian_vault/refs",
        daily_note_service = None
    ):
        self.output_dir = Path(output_dir)
        self.refs_dir = Path(refs_dir)
        self.daily_note_service = daily_note_service

        # Create directory structure
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.refs_dir.mkdir(parents=True, exist_ok=True)

        # Entity stub directories
        (self.refs_dir / "people").mkdir(exist_ok=True)
        (self.refs_dir / "projects").mkdir(exist_ok=True)
        (self.refs_dir / "places").mkdir(exist_ok=True)
        (self.refs_dir / "orgs").mkdir(exist_ok=True)
        (self.refs_dir / "days").mkdir(exist_ok=True)

    def generate_short_id(self, content: str, length: int = 4) -> str:
        """Generate short hash ID (e.g., 7c1a)"""
        full_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        return full_hash[:length]

    def create_slug(self, title: str, max_length: int = 40) -> str:
        """Create URL-safe slug from title"""
        slug = slugify(title, max_length=max_length)
        return slug or "document"

    def generate_filename(
        self,
        title: str,
        doc_type: DocumentType,
        created_at: datetime,
        content: str
    ) -> str:
        """
        Generate cross-platform safe filename: YYYY-MM-DDTHH-MM-SS_doc_type_slug_shortid.md

        Example: 2025-10-02T14-30-45_email_kita-handover_7c1a.md

        Sanitization:
        - ISO 8601 datetime format (with T separator, colons replaced by dashes)
        - Removes path separators (/, \)
        - Removes null bytes
        - Restricts to safe characters
        - Max length enforcement
        """
        # ISO 8601 datetime with safe separators (colons → dashes for Windows compatibility)
        date_str = created_at.strftime('%Y-%m-%dT%H-%M-%S')

        # Clean doc_type (remove 'DocumentType.' prefix + sanitize)
        type_str = str(doc_type).replace('DocumentType.', '')
        # Remove any path separators and dangerous chars
        type_str = type_str.replace('/', '-').replace('\\', '-').replace('\x00', '')
        type_str = slugify(type_str) or 'text'

        # Create slug (already safe from slugify)
        slug = self.create_slug(title)

        # Generate short ID
        short_id = self.generate_short_id(content)

        # Single underscore separator (more readable)
        filename = f"{date_str}_{type_str}_{slug}_{short_id}.md"
        filename = filename.replace('/', '_').replace('\\', '_').replace('\x00', '')

        return filename

    def get_wikilink_name(self, metadata: Dict[str, Any]) -> str:
        """
        Generate WikiLink-ready filename (without .md) from metadata

        Used for creating [[wikilinks]] to other documents.
        Returns the filename stem that Obsidian will recognize.

        Args:
            metadata: Document metadata dict containing:
                - title: Document title
                - document_type: DocumentType or string
                - created_at or created_date: ISO date string
                - doc_id: Document ID (for short hash)

        Returns:
            Filename stem like "2021-08-31__email__einladung-elternabend__211d"
        """
        try:
            # Get date
            date_str = metadata.get('created_at', metadata.get('created_date', ''))
            if date_str:
                # Parse ISO format and extract date part
                if 'T' in date_str:
                    date_str = date_str.split('T')[0]
                # Already in YYYY-MM-DD format
            else:
                date_str = datetime.now().strftime('%Y-%m-%d')

            # Get document type
            doc_type = metadata.get('document_type', 'text')
            if isinstance(doc_type, DocumentType):
                type_str = str(doc_type).replace('DocumentType.', '')
            else:
                type_str = str(doc_type).replace('DocumentType.', '')
            type_str = slugify(type_str) or 'text'

            # Get title slug
            title = metadata.get('title', 'untitled')
            slug = self.create_slug(title)

            # Get short hash from doc_id
            doc_id = metadata.get('doc_id', '')
            if doc_id and len(doc_id) >= 8:
                # Use first 4 chars of doc_id as short hash
                short_id = doc_id[:4]
            else:
                # Fallback: hash the title
                short_id = self.generate_short_id(title)

            # Generate filename stem (without .md)
            filename_stem = f"{date_str}__{type_str}__{slug}__{short_id}"
            filename_stem = filename_stem.replace('/', '_').replace('\\', '_').replace('\x00', '')

            return filename_stem

        except Exception as e:
            logger.error(f"Failed to generate wikilink name from metadata: {e}")
            # Fallback to doc_id
            return metadata.get('doc_id', 'unknown')

    def derive_tags(
        self,
        doc_type: DocumentType,
        people: List[str],
        projects: List[str],
        places: List[str],
        topics: List[str],
        organizations: List[str]
    ) -> List[str]:
        """
        Auto-derive tags from metadata

        Format:
        - doc/{doc_type}
        - project/{project}
        - place/{place}
        - topic/{topic}
        - person/{person}
        - org/{org}
        """
        tags = []

        # Document type tag
        type_str = str(doc_type).replace('DocumentType.', '')
        tags.append(f"doc/{type_str}")

        # Project tags (time-bound categories)
        for project in projects:
            tags.append(f"project/{slugify(project)}")

        # Topic tags (categorical - suitable for tags)
        for topic in topics:
            tags.append(f"topic/{slugify(topic)}")

        # NOTE: People, places, orgs are NOT tags - they're entities with their own pages
        # They should be referenced via wiki-links in content, not as tags
        # Tags are for: document types, topics, projects, status
        # Links are for: specific people, places, organizations

        return tags

    def _format_people_for_frontmatter(self, people_objects: List[Dict[str, Any]]) -> List[str]:
        """
        Format people objects as simple strings for Dataview querying.
        Format: "Name | Role | Email | Phone"
        """
        if not people_objects:
            return []

        formatted = []
        for person in people_objects:
            parts = [person.get('name', 'Unknown')]
            if person.get('role'):
                parts.append(person['role'])
            if person.get('email'):
                parts.append(person['email'])
            if person.get('phone'):
                parts.append(person['phone'])
            formatted.append(' | '.join(parts))
        return formatted

    def _format_dates_for_frontmatter(self, dates_detailed: List[Dict[str, Any]]) -> List[str]:
        """
        Format date objects as simple strings for Dataview querying.
        Format: "Date | Context"
        """
        if not dates_detailed:
            return []

        formatted = []
        for date_info in dates_detailed:
            date_str = date_info.get('date', '')
            context = date_info.get('context', '')
            if date_str:
                if context:
                    formatted.append(f"{date_str} | {context}")
                else:
                    formatted.append(date_str)
        return formatted

    def _sanitize_yaml_string(self, value: str) -> str:
        """
        Sanitize string value for safe YAML embedding

        Handles:
        - Converts newlines to spaces (YAML multiline strings cause parsing issues)
        - Removes or escapes problematic characters
        - Trims excessive whitespace
        """
        if not value or not isinstance(value, str):
            return value

        # Replace newlines with spaces
        cleaned = value.replace('\n', ' ').replace('\r', ' ')

        # Collapse multiple spaces to single space
        cleaned = ' '.join(cleaned.split())

        # Limit length to prevent excessive frontmatter
        if len(cleaned) > 500:
            cleaned = cleaned[:497] + '...'

        return cleaned

    def build_frontmatter(
        self,
        id: str,
        title: str,
        source: str,
        doc_type: DocumentType,
        people: List[str],
        people_objects: List[Dict] = None,  # Full person objects with relationships
        places: List[str] = None,
        projects: List[str] = None,
        topics: List[str] = None,
        organizations: List[str] = None,
        technologies: List[str] = None,
        created_at: datetime = None,
        ingested_at: datetime = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Build unified frontmatter (Blueprint-compliant v2.1)

        Blueprint compliance: https://github.com/.../personal_rag_pipeline_full.md
        - Top-level scores (not nested)
        - Separate entities section (orgs, dates, numbers)
        - Top-level provenance
        """
        # Derive tags
        tags = self.derive_tags(doc_type, people, projects, places, topics, organizations)

        # Clean doc_type
        type_str = str(doc_type).replace('DocumentType.', '')

        # Extract entities from metadata
        entities_data = metadata.get('entities', {})
        dates = entities_data.get('dates', [])
        numbers = entities_data.get('numbers', [])
        # Organizations go into entities section per blueprint
        orgs = organizations if organizations else []

        # Build frontmatter dict (COMPLETE VERSION - All metadata preserved)
        frontmatter = {
            # === Core Identification ===
            'id': id,
            'title': title,
            'source': source,
            'path': f"data/obsidian/{id}.md",
            'doc_type': type_str,
            'semantic_document_type': metadata.get('semantic_document_type', 'unknown/uncategorized'),
            'created_at': created_at.strftime('%Y-%m-%d'),
            'ingested_at': ingested_at.strftime('%Y-%m-%d'),
            'status': 'pending',

            # === Email Threading (for conversation grouping) ===
            'thread_id': metadata.get('thread_id', ''),
            'message_id': metadata.get('message_id', ''),
            'in_reply_to': metadata.get('in_reply_to', ''),
            'references': metadata.get('references', ''),
            'sender': metadata.get('sender', ''),
            'recipients': metadata.get('recipients', ''),
            'subject': metadata.get('subject', ''),

            # === Attachment Context ===
            'has_attachments': metadata.get('has_attachments', False),
            'attachment_count': metadata.get('attachment_count', 0),
            'is_attachment': metadata.get('is_attachment', False),
            'parent_doc_id': metadata.get('parent_doc_id', ''),

            # === Summary ===
            'summary': self._sanitize_yaml_string(metadata.get('summary', '')),

            # === Entities (Plain text for easy Dataview queries) ===
            'people': people if people else [],
            'places': places if places else [],
            'topics': topics if topics else [],
            'organizations': orgs if orgs else [],
            'technologies': technologies if technologies else [],
            'dates': dates if dates else [],
            'numbers': numbers,

            # === Detailed Entity Data (Dataview-queryable arrays) ===
            'people_detailed': self._format_people_for_frontmatter(people_objects) if people_objects else [],
            'dates_detailed': self._format_dates_for_frontmatter(entities_data.get('dates_detailed', [])),

            # === Quality Scores (for filtering/sorting) ===
            'quality_score': float(metadata.get('quality_score', 0.0)),
            'novelty_score': float(metadata.get('novelty_score', 0.0)),
            'actionability_score': float(metadata.get('actionability_score', 0.0)),
            'recency_score': float(metadata.get('recency_score', 1.0)),
            'signalness': float(metadata.get('signalness', 0.0)),
            'do_index': metadata.get('do_index', True),

            # === Provenance (deduplication, troubleshooting) ===
            'sha256': metadata.get('content_hash', '')[:16],
            'sha256_full': metadata.get('content_hash', ''),
            'source_ref': source,
            'file_size_mb': metadata.get('file_size_mb', 0.0),
            'ingestion_date': ingested_at.isoformat(),

            # === Enrichment Metadata (cost tracking, versioning) ===
            'enrichment_version': metadata.get('enrichment_version', 'v2.1'),
            'enrichment_cost_usd': metadata.get('enrichment_cost', 0.0),

            # === Optional Fields ===
            'page_span': metadata.get('page_span'),
            'canonical': metadata.get('canonical', True),

            # === Projects & Tags ===
            'projects': [f"[[refs/projects/{slugify(p)}|{p}]]" for p in projects] if projects else [],
            'tags': tags
        }

        # Remove empty/null values
        frontmatter = self._remove_empty(frontmatter)

        # Convert to YAML (width=1000 prevents line wrapping of long wiki-links)
        yaml_str = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=1000
        )

        return f"---\n{yaml_str}---\n\n"

    def _strip_frontmatter(self, content: str) -> str:
        """
        Remove YAML frontmatter from content to avoid nesting conflicts

        If content starts with ---, remove everything until closing ---
        """
        if not content.strip().startswith('---'):
            return content

        lines = content.split('\n')
        if len(lines) < 3:
            return content

        # Find closing ---
        closing_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                closing_idx = i
                break

        if closing_idx:
            # Return content after frontmatter + newline separator
            return '\n'.join(lines[closing_idx + 1:]).lstrip('\n')

        return content

    def _auto_link_entities(
        self,
        content: str,
        entities: Dict[str, Any],
        link_all_occurrences: bool = False
    ) -> str:
        """
        Automatically create WikiLinks for entity mentions in content

        Args:
            content: Document content
            entities: Dict of entity types (people, places, organizations, technologies)
            link_all_occurrences: If True, link every mention. If False, only link first mention.

        Returns:
            Content with entity mentions replaced by WikiLinks
        """
        if not content or not entities:
            return content

        import re

        # Track linked entities to avoid double-linking
        linked_entities = set()

        # Build entity map: {name: (type, slug)}
        entity_map = {}

        # People
        for person in entities.get('people', []):
            if isinstance(person, dict):
                name = person.get('label', person.get('name', ''))
            else:
                name = person
            if name:
                entity_map[name] = ('persons', slugify(name))

        # Places
        for place in entities.get('places', []):
            if isinstance(place, dict):
                name = place.get('label', place.get('name', ''))
            else:
                name = place
            if name:
                entity_map[name] = ('places', slugify(name))

        # Organizations
        for org in entities.get('organizations', []):
            if isinstance(org, dict):
                name = org.get('label', org.get('name', ''))
            else:
                name = org
            if name:
                entity_map[name] = ('orgs', slugify(name))

        # Technologies
        for tech in entities.get('technologies', []):
            if isinstance(tech, dict):
                name = tech.get('label', tech.get('name', ''))
            else:
                name = tech
            if name:
                entity_map[name] = ('technologies', slugify(name))

        # Sort by length (longest first) to avoid partial matches
        # e.g., "Daniel Teckentrup" should be matched before "Daniel"
        sorted_entities = sorted(entity_map.keys(), key=len, reverse=True)

        # Split content into lines to preserve structure
        lines = content.split('\n')
        result_lines = []

        in_code_block = False
        in_yaml_frontmatter = False

        for line in lines:
            # Track code blocks
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                result_lines.append(line)
                continue

            # Track YAML frontmatter
            if line.strip() == '---':
                if not in_yaml_frontmatter:
                    in_yaml_frontmatter = True
                else:
                    in_yaml_frontmatter = False
                result_lines.append(line)
                continue

            # Skip linking in code blocks and frontmatter
            if in_code_block or in_yaml_frontmatter:
                result_lines.append(line)
                continue

            # Skip if line already has WikiLinks (don't double-link)
            if '[[' in line:
                result_lines.append(line)
                continue

            # Replace entity mentions with WikiLinks
            modified_line = line

            # Track created WikiLinks to prevent nesting
            wikilink_placeholders = {}
            placeholder_counter = 0

            for entity_name in sorted_entities:
                # Skip if already linked (in this session)
                if not link_all_occurrences and entity_name in linked_entities:
                    continue

                # Word boundary regex for case-insensitive matching
                # \b ensures we match whole words only
                pattern = r'\b(' + re.escape(entity_name) + r')\b'

                entity_type, entity_slug = entity_map[entity_name]
                wikilink = f"[[refs/{entity_type}/{entity_slug}|{entity_name}]]"

                # Check if entity exists in this line
                if re.search(pattern, modified_line, re.IGNORECASE):
                    # Replace first occurrence (or all if link_all_occurrences=True)
                    if link_all_occurrences:
                        modified_line = re.sub(pattern, wikilink, modified_line, flags=re.IGNORECASE)
                    else:
                        modified_line = re.sub(pattern, wikilink, modified_line, count=1, flags=re.IGNORECASE)
                        linked_entities.add(entity_name)

                    # Protect newly created WikiLinks from further replacements
                    # Extract all WikiLinks and replace with placeholders
                    wikilink_pattern = r'\[\[([^\]]+)\]\]'
                    matches = list(re.finditer(wikilink_pattern, modified_line))

                    # Replace from end to start to preserve positions
                    for match in reversed(matches):
                        placeholder = f"__WIKILINK_{placeholder_counter}__"
                        wikilink_placeholders[placeholder] = match.group(0)
                        modified_line = modified_line[:match.start()] + placeholder + modified_line[match.end():]
                        placeholder_counter += 1

            # Restore WikiLinks from placeholders
            for placeholder, wikilink in wikilink_placeholders.items():
                modified_line = modified_line.replace(placeholder, wikilink)

            result_lines.append(modified_line)

        return '\n'.join(result_lines)

    def _format_paragraphs(self, content: str) -> str:
        """
        Ensure proper paragraph spacing in markdown content

        - Add blank lines between paragraphs (double newline)
        - Preserve markdown formatting (headers, lists, code blocks)
        """
        if not content:
            return content

        lines = content.split('\n')
        formatted = []
        prev_empty = False
        in_code_block = False

        for line in lines:
            stripped = line.strip()

            # Track code blocks
            if stripped.startswith('```'):
                in_code_block = not in_code_block
                formatted.append(line)
                prev_empty = False
                continue

            # Inside code blocks, preserve exactly
            if in_code_block:
                formatted.append(line)
                continue

            # Empty line
            if not stripped:
                if not prev_empty:  # Only add one blank line
                    formatted.append('')
                    prev_empty = True
                continue

            # Non-empty line
            # If previous was text and this is text (not header/list), ensure spacing
            if formatted and not prev_empty:
                last_line = formatted[-1].strip()
                # Check if both are regular paragraphs (not headers, lists, etc.)
                is_special = (stripped.startswith('#') or stripped.startswith('-') or
                             stripped.startswith('*') or stripped.startswith('>') or
                             stripped.startswith('|'))
                was_special = (last_line.startswith('#') or last_line.startswith('-') or
                              last_line.startswith('*') or last_line.startswith('>') or
                              last_line.startswith('|'))

                # Add spacing between regular paragraphs
                if not is_special and not was_special and last_line:
                    formatted.append('')  # Add blank line

            formatted.append(line)
            prev_empty = False

        return '\n'.join(formatted)

    def build_xref_block(
        self,
        projects: List[str],
        places: List[str],
        people: List[str],
        organizations: List[str]
    ) -> str:
        """
        Build "Related" section with plain text entity references

        NO wiki-links - entities are stored in frontmatter and queried via Dataview
        This section is for human readability only
        Dataview queries in entity stub files will find documents via frontmatter fields
        """
        if not any([projects, places, people, organizations]):
            return ""

        # Build entity reference section with wiki-links for backlinks
        lines = ["## Related", ""]

        if people:
            # Create wiki-links to person stubs using slugified paths
            people_links = [f"[[refs/persons/{slugify(person)}|{person}]]" for person in people]
            lines.append("**People:** " + " · ".join(people_links))
            lines.append("")

        if places:
            # Create wiki-links to place stubs using slugified paths
            place_links = [f"[[refs/places/{slugify(place)}|{place}]]" for place in places]
            lines.append("**Places:** " + " · ".join(place_links))
            lines.append("")

        if organizations:
            # Create wiki-links to org stubs using slugified paths
            org_links = [f"[[refs/orgs/{slugify(org)}|{org}]]" for org in organizations]
            lines.append("**Organizations:** " + " · ".join(org_links))
            lines.append("")

        if projects:
            # Create wiki-links to project stubs using slugified paths
            project_links = [f"[[refs/projects/{slugify(project)}|{project}]]" for project in projects]
            lines.append("**Projects:** " + " · ".join(project_links))
            lines.append("")

        return "\n".join(lines)

    def build_body(
        self,
        content: str,
        summary: str,
        source: str,
        key_facts: List[str],
        outcomes: List[str],
        next_actions: List[str],
        timeline: List[Dict[str, str]],
        chunks: List[Dict[str, Any]] = None,
        people_detailed: List[Dict[str, Any]] = None,
        dates_detailed: List[Dict[str, Any]] = None,
        entities: Dict[str, Any] = None,
        is_attachment: bool = False,
        parent_doc_id: str = None
    ) -> str:
        """
        Build structured body (helps both humans and RAG)

        Sections:
        - Summary
        - Context (for attachments - shows parent document)
        - Key Facts
        - Evidence/Excerpts
        - Outcomes/Decisions
        - Next Actions (optional)
        - Timeline (optional)
        """
        entities = entities or {}
        body_parts = []

        # Title (added by caller)
        # Main content will have title

        # Summary
        if summary:
            body_parts.append(f"> **Summary:** {summary}\n")

        # Context section for attachments - show parent document relationship
        if is_attachment and parent_doc_id:
            body_parts.append("## Context")
            body_parts.append("")
            # Get parent filename for WikiLink (will be updated by entity enrichment if available)
            body_parts.append(f"📎 This file was attached to: [[{parent_doc_id}]]")
            body_parts.append("")
            # Note: This will be updated to proper filename after parent is indexed

        # Source link section - link to original in attachments/
        # Extract original filename (remove upload_UUID_ prefix)
        import re
        import os
        original_filename = re.sub(r'^upload_[a-f0-9-]+_', '', source)

        # Check if original exists in Obsidian attachments
        obsidian_base = Path(os.environ.get('OBSIDIAN_VAULT_PATH', '/data/obsidian'))
        attachment_path = obsidian_base / 'attachments' / original_filename

        body_parts.append("## Source")
        body_parts.append("")
        # Show source filename with wiki-link to attachment if exists
        # Extract base filename without upload ID prefix
        base_filename = original_filename
        if '_' in original_filename and original_filename.startswith('upload_'):
            # Remove upload_<uuid>_ prefix
            parts = original_filename.split('_', 2)
            if len(parts) >= 3:
                base_filename = parts[2]
        body_parts.append(f"📄 [[attachments/{original_filename}|{base_filename}]]")
        body_parts.append("")

        # Evidence/Excerpts (main content) - NOW COMES EARLY
        # Strip frontmatter to avoid nesting conflicts
        clean_content = self._strip_frontmatter(content)
        # Auto-link entities in content
        linked_content = self._auto_link_entities(clean_content, entities, link_all_occurrences=False)
        # Ensure proper paragraph spacing
        formatted_content = self._format_paragraphs(linked_content)
        body_parts.append("## Content\n")

        # Show chunking information if available
        if chunks:
            chunk_count = len(chunks)
            body_parts.append(f"_This document was split into {chunk_count} chunks for vector search:_\n")
            for i, chunk in enumerate(chunks, 1):
                chunk_preview = chunk.get('content', '')[:100].replace('\n', ' ')
                if len(chunk.get('content', '')) > 100:
                    chunk_preview += "..."
                body_parts.append(f"- **Chunk {i}**: {chunk_preview}")
            body_parts.append("")

        body_parts.append(formatted_content)
        body_parts.append("")

        # Key Facts
        if key_facts:
            body_parts.append("## Key Facts\n")
            for fact in key_facts:
                body_parts.append(f"- {fact}")
            body_parts.append("")

        # Outcomes/Decisions
        if outcomes:
            body_parts.append("## Outcomes / Decisions\n")
            for outcome in outcomes:
                body_parts.append(f"- {outcome}")
            body_parts.append("")

        # Next Actions
        if next_actions:
            body_parts.append("## Next Actions\n")
            for action in next_actions:
                body_parts.append(f"- [ ] {action}")
            body_parts.append("")

        # Timeline
        if timeline:
            body_parts.append("## Timeline\n")
            for event in timeline:
                timestamp = event.get('timestamp', '')
                description = event.get('description', '')
                body_parts.append(f"- {timestamp} -- {description}")
            body_parts.append("")

        # === ENTITY SECTIONS (now come after content) ===

        # People Details (Dataview-queryable format)
        if people_detailed:
            body_parts.append("## People")
            body_parts.append("")
            for person in people_detailed:
                name = person.get('name', 'Unknown')
                role = person.get('role')
                email = person.get('email')
                phone = person.get('phone')
                organization = person.get('organization')
                relationships = person.get('relationships', [])
                aliases = person.get('aliases', [])

                body_parts.append(f"### {name}")
                if role:
                    body_parts.append(f"Role:: {role}")
                if email:
                    body_parts.append(f"Email:: {email}")
                if phone:
                    body_parts.append(f"Phone:: {phone}")
                if organization:
                    # Make organization queryable with wikilink
                    body_parts.append(f"Organization:: [[{organization}]]")
                if aliases:
                    body_parts.append(f"Aliases:: {', '.join(aliases)}")
                if relationships:
                    # Make relationship persons queryable with wikilinks
                    rel_strs = [f"{r.get('type', '')}: [[{r.get('person', '')}]]" for r in relationships]
                    body_parts.append(f"Relationships:: {'; '.join(rel_strs)}")
                body_parts.append("")

        # Date Details (Dataview-queryable format with wiki-links)
        if dates_detailed:
            body_parts.append("## Important Dates")
            body_parts.append("")
            for date_info in dates_detailed:
                date_str = date_info.get('date', '')
                context = date_info.get('context', '')
                if date_str:
                    # Link dates as daily notes for Obsidian timeline navigation
                    # Use refs/days/ prefix so Obsidian can find the date stub files
                    if context:
                        body_parts.append(f"- [[refs/days/{date_str}|{date_str}]]: {context}")
                    else:
                        body_parts.append(f"- [[refs/days/{date_str}|{date_str}]]")
            body_parts.append("")

        # Technologies section (with concept linking metadata)
        technologies = entities.get('technologies', [])
        if technologies:
            body_parts.append("## Technologies")
            body_parts.append("")
            for tech in technologies:
                if isinstance(tech, dict):
                    tech_name = tech.get('label', tech.get('name', ''))
                    tech_type = tech.get('type', 'Software')
                    concept_id = tech.get('concept_id')
                    category = tech.get('category')

                    # Create wikilink to technology reference note
                    tech_slug = slugify(tech_name)
                    tech_link = f"[[refs/technologies/{tech_slug}|{tech_name}]]"

                    # Format: - [[refs/technologies/pop-os|Pop!_OS]] (Software)
                    if tech_type:
                        body_parts.append(f"- {tech_link} ({tech_type})")
                    else:
                        body_parts.append(f"- {tech_link}")
                else:
                    # Simple string format
                    tech_slug = slugify(tech)
                    body_parts.append(f"- [[refs/technologies/{tech_slug}|{tech}]]")
            body_parts.append("")

        # Organizations section
        organizations = entities.get('organizations', [])
        if organizations:
            body_parts.append("## Organizations")
            body_parts.append("")
            for org in organizations:
                if isinstance(org, dict):
                    org_name = org.get('label', org.get('name', ''))
                    org_type = org.get('type', 'Organization')
                    industry = org.get('industry')

                    # Create wikilink to organization reference note
                    org_slug = slugify(org_name)
                    org_link = f"[[refs/orgs/{org_slug}|{org_name}]]"

                    # Format: - [[refs/orgs/system76|System76]] (Technology Company)
                    if industry:
                        body_parts.append(f"- {org_link} ({industry})")
                    elif org_type and org_type != 'Organization':
                        body_parts.append(f"- {org_link} ({org_type})")
                    else:
                        body_parts.append(f"- {org_link}")
                else:
                    # Simple string format
                    org_slug = slugify(org)
                    body_parts.append(f"- [[refs/orgs/{org_slug}|{org}]]")
            body_parts.append("")

        # Places section
        places = entities.get('places', [])
        if places:
            body_parts.append("## Places")
            body_parts.append("")
            for place in places:
                if isinstance(place, dict):
                    place_name = place.get('label', place.get('name', ''))
                    place_type = place.get('type', 'Location')
                    address = place.get('address')
                    category = place.get('category')

                    # Create wikilink to place reference note
                    place_slug = slugify(place_name)
                    place_link = f"[[refs/places/{place_slug}|{place_name}]]"

                    # Format: - [[refs/places/berlin|Berlin]] (City)
                    # Or: - [[refs/places/villa-luna-kita|Villa Luna Kita]] (Educational Institution)
                    if category:
                        body_parts.append(f"- {place_link} ({category})")
                    elif place_type and place_type != 'Location':
                        body_parts.append(f"- {place_link} ({place_type})")
                    else:
                        body_parts.append(f"- {place_link}")

                    # Optionally show address if available
                    if address:
                        body_parts.append(f"  - 📍 {address}")
                else:
                    # Simple string format
                    place_slug = slugify(place)
                    body_parts.append(f"- [[refs/places/{place_slug}|{place}]]")
            body_parts.append("")

        # Projects section
        projects_list = entities.get('projects', [])
        if projects_list:
            body_parts.append("## Projects")
            body_parts.append("")
            for project in projects_list:
                if isinstance(project, dict):
                    project_name = project.get('label', project.get('name', ''))
                    status = project.get('status', 'Active')

                    # Create wikilink to project reference note
                    project_slug = slugify(project_name)
                    project_link = f"[[refs/projects/{project_slug}|{project_name}]]"

                    # Format: - [[refs/projects/school-2026|School 2026]] (Active)
                    body_parts.append(f"- {project_link} ({status})")
                else:
                    # Simple string format
                    project_slug = slugify(project)
                    body_parts.append(f"- [[refs/projects/{project_slug}|{project}]]")
            body_parts.append("")

        return "\n".join(body_parts)

    def create_entity_stub(
        self,
        entity_type: str,  # person, project, place, org, day
        name: str,
        aliases: List[str] = None,
        extra_links: Dict[str, str] = None,
        person_data: Dict[str, Any] = None  # For person entities: full metadata
    ):
        """
        Create/update entity stub for backlinks

        Example: refs/people/Mother.md, refs/days/2025-11-15.md

        Args:
            entity_type: Type of entity (person, project, place, org, day)
            name: Entity name (for days: ISO date like "2025-11-15")
            aliases: Alternative names
            extra_links: Additional links to include (e.g., {"vCard": "path/to/file.vcf"})
            person_data: For person entities, full metadata dict with:
                - role: Their role/title
                - email: Email address (vCard compatible)
                - phone: Phone number (vCard compatible)
                - address: Physical address (vCard compatible)
                - organization: Organization they belong to
                - birth_date: Date of birth
                - description: Bio/description
                - contact_type: auto-determined as 'personal' (has contact) or 'reference' (no contact)
        """
        aliases = aliases or []
        extra_links = extra_links or {}
        person_data = person_data or {}

        # Determine directory with correct pluralization
        plurals = {
            'person': 'persons',
            'technology': 'technologies',
            'org': 'orgs',
            'place': 'places',
            'project': 'projects',
            'day': 'days'
        }
        dir_name = plurals.get(entity_type, f"{entity_type}s")
        entity_dir = self.refs_dir / dir_name
        entity_dir.mkdir(parents=True, exist_ok=True)

        # Create cross-platform safe filename
        safe_name = slugify(name)
        if not safe_name:
            # Fallback: manual sanitization if slugify returns empty
            safe_name = name.replace(' ', '-').replace('/', '-').replace('\\', '-').replace('\x00', '')
            safe_name = ''.join(c for c in safe_name if c.isalnum() or c in '-_.')
            safe_name = safe_name or 'entity'  # Ultimate fallback
        file_path = entity_dir / f"{safe_name}.md"

        # Don't overwrite if exists (stubs are created once)
        if file_path.exists():
            return file_path

        # Build stub frontmatter
        stub_frontmatter = {
            'type': entity_type,
            'name': name,
            'aliases': aliases
        }

        # Add person-specific fields to frontmatter (vCard compatible)
        if entity_type == 'person' and person_data:
            if person_data.get('email'):
                stub_frontmatter['email'] = person_data['email']
            if person_data.get('phone'):
                stub_frontmatter['phone'] = person_data['phone']
            if person_data.get('address'):
                stub_frontmatter['address'] = person_data['address']
            if person_data.get('role'):
                stub_frontmatter['role'] = person_data['role']
            if person_data.get('organization'):
                stub_frontmatter['organization'] = person_data['organization']
            if person_data.get('birth_date'):
                stub_frontmatter['birth_date'] = person_data['birth_date']
            # Determine contact type: has contact info = personal, else = reference
            has_contact = person_data.get('email') or person_data.get('phone') or person_data.get('address')
            stub_frontmatter['contact_type'] = 'personal' if has_contact else 'reference'

        # Add place-specific fields to frontmatter
        if entity_type == 'place' and person_data:
            if person_data.get('address'):
                stub_frontmatter['address'] = person_data['address']
            if person_data.get('latitude'):
                stub_frontmatter['latitude'] = person_data['latitude']
            if person_data.get('longitude'):
                stub_frontmatter['longitude'] = person_data['longitude']
            if person_data.get('category'):
                stub_frontmatter['category'] = person_data['category']
            if person_data.get('type'):
                stub_frontmatter['place_type'] = person_data['type']
            if person_data.get('contacts'):
                stub_frontmatter['related_contacts'] = person_data['contacts']

        stub_yaml = yaml.dump(stub_frontmatter, default_flow_style=False, allow_unicode=True)

        # Map entity types to correct frontmatter field names
        field_name_map = {
            'person': 'people',
            'project': 'projects',
            'place': 'places',
            'org': 'organizations',
            'technology': 'technologies',
            'day': 'dates'  # Daily notes query on 'dates' field
        }
        field_name = field_name_map.get(entity_type, f"{entity_type}s")

        # Build stub body with Dataview query
        if entity_type == 'day':
            # Daily note: Show documents mentioning this date with context
            stub_body = f"""# {name}

## Events on This Date

```dataview
TABLE file.link as "Document", summary as "Summary", topics as "Topics"
WHERE contains(dates, "{name}")
SORT file.mtime DESC
LIMIT 50
```

**Note:** Shows all documents with events/deadlines on this date.

## All Documents Created on This Date

```dataview
TABLE file.link as "Document", summary as "Summary"
WHERE created_at = "{name}" OR ingested_at = "{name}"
SORT file.mtime DESC
LIMIT 50
```
"""
        elif entity_type == 'person':
            # Enhanced person stub with summary, contact info, and relationships
            stub_body = f"""# {name}\n\n"""

            # Summary section (if provided)
            if person_data.get('description'):
                stub_body += f"> {person_data['description']}\n\n"

            # Contact information section
            contact_parts = []
            if person_data.get('role'):
                role = person_data['role']
                org = person_data.get('organization', '')
                if org:
                    contact_parts.append(f"**Role:** {role} at {org}")
                else:
                    contact_parts.append(f"**Role:** {role}")

            if person_data.get('email') or person_data.get('phone'):
                contact_line = "**Contact:** "
                parts = []
                if person_data.get('email'):
                    parts.append(person_data['email'])
                if person_data.get('phone'):
                    parts.append(person_data['phone'])
                contact_line += " · ".join(parts)
                contact_parts.append(contact_line)

            if person_data.get('address'):
                contact_parts.append(f"**Address:** {person_data['address']}")

            if person_data.get('birth_date'):
                contact_parts.append(f"**Birth Date:** {person_data['birth_date']}")

            if contact_parts:
                stub_body += "\n".join(contact_parts) + "\n\n"

            # Relationships section with wiki-links
            relationships = person_data.get('relationships', [])
            if relationships:
                stub_body += "## Relationships\n\n"
                for rel in relationships:
                    rel_type = rel.get('type', 'related to')
                    rel_person = rel.get('person', '')
                    if rel_person:
                        # Convert to wiki-link for clickability and backlinks
                        rel_slug = slugify(rel_person)
                        rel_link = f"[[refs/persons/{rel_slug}|{rel_person}]]"
                        stub_body += f"- **{rel_type.title()}:** {rel_link}\n"
                stub_body += "\n"

            # Related documents section
            stub_body += f"""## Related Documents

```dataview
TABLE file.link as "Document", summary as "Summary", topics as "Topics"
WHERE contains(people, "{name}")
SORT file.mtime DESC
LIMIT 50
```

"""
        elif entity_type == 'technology':
            # Technology stub with concept linking metadata
            stub_body = f"""# {name}\n\n"""

            # Show concept linking metadata if available
            if person_data:  # Using person_data param to pass tech_data
                tech_type = person_data.get('type')
                if tech_type:
                    stub_body += f"**Type:** {tech_type}\n\n"

                concept_id = person_data.get('concept_id')
                if concept_id:
                    stub_body += f"**Concept ID:** `{concept_id}`\n"

                prefLabel = person_data.get('prefLabel')
                if prefLabel and prefLabel != name:
                    stub_body += f"**Preferred Label:** {prefLabel}\n"

                altLabels = person_data.get('altLabels', [])
                if altLabels:
                    labels_str = ", ".join(altLabels)
                    stub_body += f"**Alternative Labels:** {labels_str}\n"

                category = person_data.get('category')
                if category:
                    stub_body += f"**Category:** {category}\n"

                suggested = person_data.get('suggested_for_vocab', False)
                if suggested:
                    stub_body += f"\n> 💡 **Suggested for Vocabulary:** This technology is not yet in the controlled vocabulary. Consider adding it.\n"

                if any([tech_type, concept_id, prefLabel, altLabels, category]):
                    stub_body += "\n"

            # Related documents section
            stub_body += f"""## Related Documents

```dataview
TABLE file.link as "Document", summary as "Summary", topics as "Topics"
WHERE contains({field_name}, "{name}")
SORT file.mtime DESC
LIMIT 50
```

"""
        elif entity_type == 'place':
            # Place stub with location details
            stub_body = f"""# {name}\n\n"""

            # Show place metadata if available
            if person_data:  # Using person_data param to pass place_data
                place_type = person_data.get('type', 'Location')
                if place_type:
                    stub_body += f"**Type:** {place_type}\n\n"

                # Address information
                address = person_data.get('address')
                if address:
                    stub_body += f"**Address:** {address}\n"

                # GPS coordinates
                latitude = person_data.get('latitude')
                longitude = person_data.get('longitude')
                if latitude and longitude:
                    stub_body += f"**GPS:** {latitude}, {longitude}\n"
                    # Add OpenStreetMap link
                    stub_body += f"**Map:** [OpenStreetMap](https://www.openstreetmap.org/?mlat={latitude}&mlon={longitude}#map=15/{latitude}/{longitude})\n"

                # Related contacts
                contacts = person_data.get('contacts', [])
                if contacts:
                    stub_body += f"\n**Related Contacts:**\n"
                    for contact in contacts:
                        contact_slug = slugify(contact)
                        stub_body += f"- [[refs/persons/{contact_slug}|{contact}]]\n"

                # Description
                description = person_data.get('description')
                if description:
                    stub_body += f"\n> {description}\n"

                # Category (e.g., home, school, business, medical)
                category = person_data.get('category')
                if category:
                    stub_body += f"\n**Category:** {category}\n"

                # Visit history or notes
                notes = person_data.get('notes')
                if notes:
                    stub_body += f"\n**Notes:** {notes}\n"

                if any([address, latitude, longitude, contacts, description, category, notes]):
                    stub_body += "\n"

            # Related documents section
            stub_body += f"""## Related Documents

```dataview
TABLE file.link as "Document", summary as "Summary", topics as "Topics", dates as "Dates"
WHERE contains({field_name}, "{name}")
SORT file.mtime DESC
LIMIT 50
```

## Documents Mentioning This Place

```dataview
TABLE file.link as "Document", summary as "Summary"
WHERE contains(file.outlinks, this.file.link)
SORT file.mtime DESC
LIMIT 50
```

"""
        elif entity_type == 'org':
            # Organization stub with business details
            stub_body = f"""# {name}\n\n"""

            # Show organization metadata if available
            if person_data:  # Using person_data param to pass org_data
                org_type = person_data.get('type', 'Organization')
                if org_type:
                    stub_body += f"**Type:** {org_type}\n\n"

                # Industry/sector
                industry = person_data.get('industry')
                if industry:
                    stub_body += f"**Industry:** {industry}\n"

                # Headquarters/location
                headquarters = person_data.get('headquarters')
                if headquarters:
                    stub_body += f"**Headquarters:** {headquarters}\n"

                # Website
                website = person_data.get('website')
                if website:
                    stub_body += f"**Website:** [{website}]({website})\n"

                # Key contacts
                contacts = person_data.get('contacts', [])
                if contacts:
                    stub_body += f"\n**Key Contacts:**\n"
                    for contact in contacts:
                        contact_slug = slugify(contact)
                        stub_body += f"- [[refs/persons/{contact_slug}|{contact}]]\n"

                # Description
                description = person_data.get('description')
                if description:
                    stub_body += f"\n> {description}\n"

                # Related projects
                projects = person_data.get('projects', [])
                if projects:
                    stub_body += f"\n**Related Projects:**\n"
                    for project in projects:
                        project_slug = slugify(project)
                        stub_body += f"- [[refs/projects/{project_slug}|{project}]]\n"

                if any([industry, headquarters, website, contacts, description, projects]):
                    stub_body += "\n"

            # Related documents section
            stub_body += f"""## Related Documents

```dataview
TABLE file.link as "Document", summary as "Summary", topics as "Topics", dates as "Dates"
WHERE contains({field_name}, "{name}")
SORT file.mtime DESC
LIMIT 50
```

"""
        elif entity_type == 'project':
            # Project stub with timeline and stakeholders
            stub_body = f"""# {name}\n\n"""

            # Show project metadata if available
            if person_data:  # Using person_data param to pass project_data
                status = person_data.get('status', 'Active')
                if status:
                    stub_body += f"**Status:** {status}\n\n"

                # Timeline
                start_date = person_data.get('start_date')
                end_date = person_data.get('end_date')
                if start_date or end_date:
                    stub_body += f"**Timeline:**\n"
                    if start_date:
                        stub_body += f"- Start: [[{start_date}]]\n"
                    if end_date:
                        stub_body += f"- End: [[{end_date}]]\n"

                # Stakeholders
                stakeholders = person_data.get('stakeholders', [])
                if stakeholders:
                    stub_body += f"\n**Stakeholders:**\n"
                    for stakeholder in stakeholders:
                        stakeholder_slug = slugify(stakeholder)
                        stub_body += f"- [[refs/persons/{stakeholder_slug}|{stakeholder}]]\n"

                # Organizations involved
                organizations = person_data.get('organizations', [])
                if organizations:
                    stub_body += f"\n**Organizations:**\n"
                    for org in organizations:
                        org_slug = slugify(org)
                        stub_body += f"- [[refs/orgs/{org_slug}|{org}]]\n"

                # Description
                description = person_data.get('description')
                if description:
                    stub_body += f"\n> {description}\n"

                # Category (e.g., research, business, personal)
                category = person_data.get('category')
                if category:
                    stub_body += f"\n**Category:** {category}\n"

                # Goals/objectives
                goals = person_data.get('goals', [])
                if goals:
                    stub_body += f"\n**Goals:**\n"
                    for goal in goals:
                        stub_body += f"- {goal}\n"

                if any([start_date, end_date, stakeholders, organizations, description, category, goals]):
                    stub_body += "\n"

            # Related documents section
            stub_body += f"""## Related Documents

```dataview
TABLE file.link as "Document", summary as "Summary", topics as "Topics", dates as "Dates"
WHERE contains({field_name}, "{name}")
SORT file.mtime DESC
LIMIT 50
```

## Project Timeline

```dataview
TABLE dates as "Date", summary as "Summary"
WHERE contains({field_name}, "{name}")
SORT dates ASC
LIMIT 100
```

"""
        else:
            # Regular entity stub - use file.link to find backlinks
            stub_body = f"""# {name}

## Related Documents

```dataview
TABLE file.link as "Document", summary as "Summary", topics as "Topics"
WHERE contains({field_name}, "{name}")
SORT file.mtime DESC
LIMIT 50
```
"""

        # Add extra resources section if provided (no wiki-links)
        if extra_links:
            stub_body += "\n## Resources\n\n"
            for label, link in extra_links.items():
                # Extract just the filename from the path
                filename = link.split('/')[-1]
                stub_body += f"- {label}: `{filename}`\n"

        # Write stub
        stub_content = f"---\n{stub_yaml}---\n\n{stub_body}"
        file_path.write_text(stub_content, encoding='utf-8')

        return file_path

    def export_document(
        self,
        title: str,
        content: str,
        metadata: Dict[str, Any],
        document_type: DocumentType,
        created_at: Optional[datetime] = None,
        source: str = "rag_pipeline"
    ) -> Path:
        """
        Main export function

        Returns: Path to created markdown file
        """
        created_at = created_at or datetime.now()
        ingested_at = datetime.now()

        # Debug: Log what metadata we received
        logger.debug(f"export_document() received metadata:\n"
                    f"  - people field: {metadata.get('people', 'NOT FOUND')}\n"
                    f"  - dates field: {metadata.get('dates', 'NOT FOUND')}\n"
                    f"  - dates_detailed field: {metadata.get('entities', {}).get('dates_detailed', 'NOT FOUND')}")

        # Parse metadata lists
        # Handle both old format (people_roles string) and new format (people list of dicts/strings)
        people_raw = metadata.get('people', metadata.get('people_roles', ''))
        people_objects = []  # Full person objects with metadata
        people = []  # Just names for frontmatter/xref

        if isinstance(people_raw, list):
            # New format: list of dicts or strings
            for p in people_raw:
                if isinstance(p, dict):
                    people_objects.append(p)
                    people.append(p.get('name', ''))
                else:
                    people.append(p)
        else:
            # Old format: CSV string
            people = self._parse_csv(people_raw)

        # Handle both list and CSV string formats
        places = metadata.get('places', '')
        if isinstance(places, list):
            places = places
        else:
            places = self._parse_csv(places)

        projects = metadata.get('projects', '')
        if isinstance(projects, list):
            projects = projects
        else:
            projects = self._parse_csv(projects)

        topics = metadata.get('topics', '')
        if isinstance(topics, list):
            topics = topics
        else:
            topics = self._parse_csv(topics)

        organizations = metadata.get('organizations', '')
        if isinstance(organizations, list):
            organizations = organizations
        else:
            organizations = self._parse_csv(organizations)

        # Extract technologies from entities dict
        # Technologies can be EntityObject dicts or simple strings
        entities = metadata.get('entities', {})
        technologies_raw = entities.get('technologies', [])
        technologies = []
        for tech in technologies_raw:
            if isinstance(tech, dict):
                # Extract label from EntityObject
                tech_name = tech.get('label', tech.get('name', ''))
                if tech_name:
                    technologies.append(tech_name)
            else:
                # Simple string
                technologies.append(tech)

        # Generate ID and filename
        date_str = created_at.strftime('%Y-%m-%d')
        slug = self.create_slug(title)
        short_id = self.generate_short_id(content)
        doc_id = f"{created_at.strftime('%Y%m%d')}_{slug}_{short_id}"

        filename = self.generate_filename(title, document_type, created_at, content)
        file_path = self.output_dir / filename

        # Build frontmatter
        frontmatter = self.build_frontmatter(
            id=doc_id,
            title=title,
            source=source,
            doc_type=document_type,
            people=people,
            people_objects=people_objects,  # Add full objects with relationships
            places=places,
            projects=projects,
            topics=topics,
            organizations=organizations,
            technologies=technologies,
            created_at=created_at,
            ingested_at=ingested_at,
            metadata=metadata
        )

        # Build body
        summary = metadata.get('summary', '')
        key_facts = []  # TODO: Extract from metadata if available
        outcomes = []   # TODO: Extract from metadata
        next_actions = []  # TODO: Extract from metadata
        timeline = []   # TODO: Extract from metadata

        # Get entities dict from metadata
        entities = metadata.get('entities', {})
        dates_detailed = entities.get('dates_detailed', [])

        # Ensure places from frontmatter are in entities dict for document body
        if places and 'places' not in entities:
            entities['places'] = places
        elif places and 'places' in entities:
            # Merge frontmatter places with entities places
            existing_place_names = set()
            for p in entities.get('places', []):
                if isinstance(p, dict):
                    existing_place_names.add(p.get('label', p.get('name', '')))
                else:
                    existing_place_names.add(p)

            for place_name in places:
                if place_name and place_name not in existing_place_names:
                    entities['places'].append(place_name)

        # Map locations to places for document body display
        # Enrichment returns "locations" but we use "places" in templates
        if 'locations' in entities:
            if 'places' not in entities:
                entities['places'] = entities['locations']
            else:
                # Both exist - merge them (places takes precedence)
                locations_to_add = []
                existing_place_names = set()

                # Collect existing place names
                for p in entities.get('places', []):
                    if isinstance(p, dict):
                        existing_place_names.add(p.get('label', p.get('name', '')))
                    else:
                        existing_place_names.add(p)

                # Add locations that aren't already in places
                for loc in entities.get('locations', []):
                    loc_name = loc.get('label', loc.get('name', loc)) if isinstance(loc, dict) else loc
                    if loc_name and loc_name not in existing_place_names:
                        locations_to_add.append(loc)

                if locations_to_add:
                    entities['places'] = entities['places'] + locations_to_add

        # Get attachment context if applicable
        is_attachment = metadata.get('is_attachment', False)
        parent_doc_id = metadata.get('parent_doc_id', '')

        body = self.build_body(
            content=content,
            summary=summary,
            source=source,
            key_facts=key_facts,
            outcomes=outcomes,
            next_actions=next_actions,
            timeline=timeline,
            people_detailed=people_objects,
            dates_detailed=dates_detailed,
            entities=entities,
            is_attachment=is_attachment,
            parent_doc_id=parent_doc_id
        )

        # Build xref block
        xref = self.build_xref_block(projects, places, people, organizations)

        # Combine
        full_content = f"{frontmatter}# {title}\n\n{body}\n\n{xref}"

        # Write file
        file_path.write_text(full_content, encoding='utf-8')

        # Create entity stubs with resource links

        # People stubs with vCard links and full metadata
        # Use full person objects if available, otherwise fall back to names
        persons_to_process = people_objects if people_objects else [{'name': p} for p in people if p]

        for person_obj in persons_to_process:
            person_name = person_obj.get('name', '') if isinstance(person_obj, dict) else str(person_obj)
            if not person_name:
                continue

            # Check if vCard exists for this person
            vcard_filename = slugify(person_name) + '.vcf'
            # Use absolute path for Docker, relative for local dev
            import os
            is_docker = os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
            vcard_base = Path('/data/contacts') if is_docker else Path('data/contacts')
            vcard_path = vcard_base / vcard_filename

            extra_links = {}
            if vcard_path.exists():
                extra_links['vCard'] = f"../../../data/contacts/{vcard_filename}"

            # Pass full person data if it's a dict, otherwise empty dict
            person_data = person_obj if isinstance(person_obj, dict) else {}
            self.create_entity_stub('person', person_name, extra_links=extra_links, person_data=person_data)

        # Project stubs
        for project in projects:
            self.create_entity_stub('project', project)

        # Place stubs (can include location metadata)
        places_from_entities = entities.get('places', [])
        for place in places:
            # Check if we have enhanced place data from entities
            place_data = {}
            if isinstance(place, dict):
                # Place is already an EntityObject with metadata
                place_name = place.get('label', place.get('name', ''))
                place_data = {
                    'type': place.get('type', 'Location'),
                    'address': place.get('address'),
                    'latitude': place.get('latitude'),
                    'longitude': place.get('longitude'),
                    'contacts': place.get('contacts', []),
                    'description': place.get('description'),
                    'category': place.get('category'),
                    'notes': place.get('notes')
                }
            else:
                place_name = place
                # Try to find enhanced data in entities.places if it's there
                for enhanced_place in places_from_entities:
                    if isinstance(enhanced_place, dict):
                        if enhanced_place.get('label') == place or enhanced_place.get('name') == place:
                            place_data = {
                                'type': enhanced_place.get('type', 'Location'),
                                'address': enhanced_place.get('address'),
                                'latitude': enhanced_place.get('latitude'),
                                'longitude': enhanced_place.get('longitude'),
                                'contacts': enhanced_place.get('contacts', []),
                                'description': enhanced_place.get('description'),
                                'category': enhanced_place.get('category'),
                                'notes': enhanced_place.get('notes')
                            }
                            break

            if place_name:
                self.create_entity_stub('place', place_name, person_data=place_data)

        # Organization stubs
        for org in organizations:
            self.create_entity_stub('org', org)

        # Technology stubs (from entities.technologies with concept linking)
        technologies = entities.get('technologies', [])
        for tech in technologies:
            # Technology can be EntityObject dict or simple string
            if isinstance(tech, dict):
                tech_name = tech.get('label', tech.get('name', ''))
                tech_data = {
                    'type': tech.get('type', 'Software'),
                    'concept_id': tech.get('concept_id'),
                    'prefLabel': tech.get('prefLabel'),
                    'altLabels': tech.get('altLabels', []),
                    'category': tech.get('category'),
                    'suggested_for_vocab': tech.get('suggested_for_vocab', False)
                }
            else:
                tech_name = tech
                tech_data = {}

            if tech_name:
                self.create_entity_stub('technology', tech_name, person_data=tech_data)

        # Daily notes for extracted dates with iCal links
        dates = metadata.get('dates', [])
        if isinstance(dates, str):
            dates = self._parse_csv(dates)

        for date_str in dates:
            # Check if calendar event exists for this date
            # Events are named like: 2025-11-15_event-title.ics
            import glob
            calendar_dir = Path('data/calendar')
            ical_files = []
            if calendar_dir.exists():
                ical_files = list(calendar_dir.glob(f"{date_str}_*.ics"))

            extra_links = {}
            if ical_files:
                # Link to the first matching event
                ical_filename = ical_files[0].name
                extra_links['Calendar Event'] = f"../../../data/calendar/{ical_filename}"

            self.create_entity_stub('day', date_str, extra_links=extra_links)

        # Add document to daily note (for document's creation date)
        if self.daily_note_service:
            try:
                doc_type_str = str(document_type).replace('DocumentType.', '')
                self.daily_note_service.add_document_to_daily_note(
                    doc_date=created_at,
                    doc_title=title,
                    doc_type=doc_type_str,
                    doc_id=doc_id,
                    doc_filename=filename.replace('.md', '')  # Remove .md for wiki-links
                )
            except Exception as e:
                logger.error(f"Failed to add document to daily note: {e}")

        return file_path

    def _parse_csv(self, value: str) -> List[str]:
        """Parse comma-separated string into list"""
        if not value or value == "":
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    def _remove_empty(self, d: Dict) -> Dict:
        """Recursively remove empty values from dict"""
        if not isinstance(d, dict):
            return d

        return {
            k: self._remove_empty(v) if isinstance(v, dict) else v
            for k, v in d.items()
            if v not in [[], {}, "", None] and not (isinstance(v, dict) and not v)
        }


# Test
if __name__ == "__main__":
    test_metadata = {
        "summary": "Discussion about kita handover schedule changes for autumn break.",
        "people_roles": "Daniel,Mother",
        "places": "Köln Südstadt,Essen Rüttenscheid",
        "projects": "custody-2025,school-2026",
        "topics": "kita,handover,schedule,pickup",
        "organizations": "Kita Astronauten",
        "quality_score": 0.94,
        "novelty_score": 0.72,
        "actionability_score": 0.80,
        "recency_score": 0.95,
        "signalness": 0.85,
        "content_hash": "abc123def456",
        "enrichment_version": "v2.0"
    }

    service = ObsidianService("./test_obsidian_v3")

    content = """
This is a test email thread about kita handover schedules.

## Discussion Points

1. Late pickup on October 2nd approved
2. Schedule changes after autumn break
3. New handover times starting October 15th

Contact information: handover@kita-astronauten.de
"""

    result = service.export_document(
        title="Kita handover schedule discussion (Sep-Oct 2025)",
        content=content,
        metadata=test_metadata,
        document_type=DocumentType.email,
        created_at=datetime(2025, 10, 2),
        source="email"
    )

    logger.info(f"\n✅ Exported to: {result}")
    logger.info(f"\n📄 Content preview:")
    logger.info("=" * 60)
    logger.info(result.read_text()[:800])
    logger.info("=" * 60)

    # Check entity stubs
    refs_created = list((Path("./test_obsidian_v3/refs")).rglob("*.md"))
    logger.info(f"\n📁 Created {len(refs_created)} entity stubs:")
    for ref in refs_created:
        logger.info(f"   - {ref.relative_to('./test_obsidian_v3')}")
