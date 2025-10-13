"""
Obsidian Service V3 - RAG-First, Obsidian-Happy

Implements the complete RAG/Obsidian integration design:
- Immutable, pipeline-owned MD+YAML
- Rich graphs & dashboards "for free"
- Zero impact on chunking/embeddings
- Auto-generated entity stubs for backlinks
- Read-only vault with perfect integration

Filename: YYYY-MM-DD__doc_type__slug__shortid.md
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
        refs_dir: str = "./obsidian_vault/refs"
    ):
        self.output_dir = Path(output_dir)
        self.refs_dir = Path(refs_dir)

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
        Generate cross-platform safe filename: YYYY-MM-DD__doc_type__slug__shortid.md

        Example: 2025-10-02__correspondence.thread__kita-handover__7c1a.md

        Sanitization:
        - Removes path separators (/, \)
        - Removes null bytes
        - Restricts to safe characters
        - Max length enforcement
        """
        date_str = created_at.strftime('%Y-%m-%d')

        # Clean doc_type (remove 'DocumentType.' prefix + sanitize)
        type_str = str(doc_type).replace('DocumentType.', '')
        # Remove any path separators and dangerous chars
        type_str = type_str.replace('/', '-').replace('\\', '-').replace('\x00', '')
        type_str = slugify(type_str) or 'text'

        # Create slug (already safe from slugify)
        slug = self.create_slug(title)

        # Generate short ID
        short_id = self.generate_short_id(content)

        # Final safety check: remove any remaining path separators
        filename = f"{date_str}__{type_str}__{slug}__{short_id}.md"
        filename = filename.replace('/', '_').replace('\\', '_').replace('\x00', '')

        return filename

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

        # Build frontmatter dict (BLUEPRINT-COMPLIANT)
        frontmatter = {
            'id': id,
            'title': title,
            'source': source,
            'path': f"data/obsidian/{id}.md",  # Blueprint spec
            'doc_type': type_str,
            'semantic_document_type': metadata.get('semantic_document_type', 'unknown/uncategorized'),
            'created_at': created_at.strftime('%Y-%m-%d'),
            'ingested_at': ingested_at.strftime('%Y-%m-%d'),

            # Controlled vocabulary (top-level lists) - converted to wiki-links for clickability
            'people': [f"[[refs/persons/{slugify(p)}|{p}]]" for p in people] if people else [],
            'places': [f"[[refs/places/{slugify(p)}|{p}]]" for p in places] if places else [],
            'projects': [f"[[refs/projects/{slugify(p)}|{p}]]" for p in projects] if projects else [],
            'topics': topics if topics else [],  # Topics remain as plain strings (hierarchical paths)

            # Entities (FLATTENED for Obsidian Dataview compatibility)
            'organizations': [f"[[refs/orgs/{slugify(o)}|{o}]]" for o in orgs] if orgs else [],
            'people_detailed': people_objects if people_objects else [],  # Full person objects with relationships
            'dates': [f"[[refs/days/{d}]]" for d in dates] if dates else [],
            'dates_detailed': entities_data.get('dates_detailed', []),  # Full date context
            'numbers': numbers,

            # Summary (top-level)
            'summary': metadata.get('summary', ''),

            # Scores (FLAT for Dataview queries)
            'quality_score': float(metadata.get('quality_score', 0.0)),
            'novelty_score': float(metadata.get('novelty_score', 0.0)),
            'actionability_score': float(metadata.get('actionability_score', 0.0)),
            'recency_score': float(metadata.get('recency_score', 1.0)),
            'signalness': float(metadata.get('signalness', 0.0)),
            'do_index': metadata.get('do_index', True),

            # Provenance (FLATTENED for Dataview)
            'sha256': metadata.get('content_hash', '')[:16],
            'sha256_full': metadata.get('content_hash', ''),
            'source_ref': source,
            'file_size_mb': metadata.get('file_size_mb', 0.0),
            'ingestion_date': ingested_at.isoformat(),

            # Enrichment metadata (top-level)
            'enrichment_version': metadata.get('enrichment_version', 'v2.1'),
            'enrichment_cost_usd': metadata.get('enrichment_cost', 0.0),

            # Optional fields
            'page_span': metadata.get('page_span'),
            'canonical': metadata.get('canonical', True),

            # Auto-derived tags (for Obsidian graph/search)
            'tags': tags
        }

        # Remove empty/null values
        frontmatter = self._remove_empty(frontmatter)

        # Convert to YAML
        yaml_str = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False
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
        timeline: List[Dict[str, str]]
    ) -> str:
        """
        Build structured body (helps both humans and RAG)

        Sections:
        - Summary
        - Key Facts
        - Evidence/Excerpts
        - Outcomes/Decisions
        - Next Actions (optional)
        - Timeline (optional)
        """
        body_parts = []

        # Title (added by caller)
        # Main content will have title

        # Summary
        if summary:
            body_parts.append(f"> **Summary:** {summary}\n")

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

        # Key Facts
        if key_facts:
            body_parts.append("## Key Facts\n")
            for fact in key_facts:
                body_parts.append(f"- {fact}")
            body_parts.append("")

        # Evidence/Excerpts (main content)
        # Strip frontmatter to avoid nesting conflicts
        clean_content = self._strip_frontmatter(content)
        # Ensure proper paragraph spacing
        formatted_content = self._format_paragraphs(clean_content)
        body_parts.append("## Evidence / Excerpts\n")
        body_parts.append("_Note: This document was chunked for vector search. See `chunks` in frontmatter for count._\n")
        body_parts.append(formatted_content)
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

        # Determine directory
        entity_dir = self.refs_dir / f"{entity_type}s"
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

        stub_yaml = yaml.dump(stub_frontmatter, default_flow_style=False, allow_unicode=True)

        # Map entity types to correct frontmatter field names
        field_name_map = {
            'person': 'people',
            'project': 'projects',
            'place': 'places',
            'org': 'organizations',
            'day': 'dates'  # Daily notes query on 'dates' field
        }
        field_name = field_name_map.get(entity_type, f"{entity_type}s")

        # Build stub body with Dataview query
        if entity_type == 'day':
            # Daily note: Show documents mentioning this date with context
            stub_body = f"""# {name}

## Events on This Date

```dataview
TABLE file.link as "Document", summary as "Summary", dates_detailed as "Date Context"
WHERE contains(dates, "{name}")
SORT file.mtime DESC
LIMIT 50
```

**Note:** Shows all documents with events/deadlines on this date. The "Date Context" column shows details (meeting, deadline, birthday, etc.).
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

        body = self.build_body(
            content=content,
            summary=summary,
            source=source,
            key_facts=key_facts,
            outcomes=outcomes,
            next_actions=next_actions,
            timeline=timeline
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

        # Place stubs
        for place in places:
            self.create_entity_stub('place', place)

        # Organization stubs
        for org in organizations:
            self.create_entity_stub('org', org)

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
