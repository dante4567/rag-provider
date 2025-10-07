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
import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from slugify import slugify

from src.models.schemas import DocumentType


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
        Generate filename: YYYY-MM-DD__doc_type__slug__shortid.md

        Example: 2025-10-02__correspondence.thread__kita-handover__7c1a.md
        """
        date_str = created_at.strftime('%Y-%m-%d')

        # Clean doc_type (remove 'DocumentType.' prefix if present)
        type_str = str(doc_type).replace('DocumentType.', '')

        # Create slug
        slug = self.create_slug(title)

        # Generate short ID
        short_id = self.generate_short_id(content)

        return f"{date_str}__{type_str}__{slug}__{short_id}.md"

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

        # Project tags
        for project in projects:
            tags.append(f"project/{slugify(project)}")

        # Place tags
        for place in places:
            tags.append(f"place/{slugify(place)}")

        # Topic tags
        for topic in topics:
            tags.append(f"topic/{slugify(topic)}")

        # People tags
        for person in people:
            tags.append(f"person/{slugify(person)}")

        # Organization tags
        for org in organizations:
            tags.append(f"org/{slugify(org)}")

        return tags

    def build_frontmatter(
        self,
        id: str,
        title: str,
        source: str,
        doc_type: DocumentType,
        people: List[str],
        places: List[str],
        projects: List[str],
        topics: List[str],
        organizations: List[str],
        created_at: datetime,
        ingested_at: datetime,
        metadata: Dict[str, Any]
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
            'created_at': created_at.strftime('%Y-%m-%d'),
            'ingested_at': ingested_at.strftime('%Y-%m-%d'),

            # Controlled vocabulary (top-level lists)
            'people': people if people else [],
            'places': places if places else [],
            'projects': projects if projects else [],
            'topics': topics if topics else [],

            # Entities section (Blueprint spec - separate from controlled vocab)
            'entities': {
                'orgs': orgs,
                'dates': dates,
                'numbers': numbers
            },

            # Summary (top-level)
            'summary': metadata.get('summary', ''),

            # Scores (TOP-LEVEL per blueprint, not nested!)
            'quality_score': float(metadata.get('quality_score', 0.0)),
            'novelty_score': float(metadata.get('novelty_score', 0.0)),
            'actionability_score': float(metadata.get('actionability_score', 0.0)),
            'recency_score': float(metadata.get('recency_score', 1.0)),
            'signalness': float(metadata.get('signalness', 0.0)),
            'do_index': metadata.get('do_index', True),

            # Provenance (TOP-LEVEL per blueprint)
            'provenance': {
                'sha256': metadata.get('content_hash', '')[:16],
                'sha256_full': metadata.get('content_hash', ''),
                'source_ref': source,
                'file_size_mb': metadata.get('file_size_mb', 0.0),
                'ingestion_date': ingested_at.isoformat()
            },

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

    def build_xref_block(
        self,
        projects: List[str],
        places: List[str],
        people: List[str],
        organizations: List[str]
    ) -> str:
        """
        Build wiki-link xref block for Obsidian graph edges

        Wrapped in <!-- RAG:IGNORE --> so chunker excludes it
        Uses sanitized entity names for valid Obsidian links
        """
        if not any([projects, places, people, organizations]):
            return ""

        lines = ["<!-- RAG:IGNORE-START -->"]
        lines.append("")
        lines.append("## Xref")
        lines.append("")

        # Project links (with display text)
        for project in projects:
            safe_name = slugify(project) or project.replace(' ', '-')
            lines.append(f"[[project:{safe_name}|{project}]] ")

        # Place links (with display text)
        for place in places:
            safe_name = slugify(place) or place.replace(' ', '-')
            lines.append(f"[[place:{safe_name}|{place}]] ")

        # People links (with display text)
        for person in people:
            safe_name = slugify(person) or person.replace(' ', '-')
            lines.append(f"[[person:{safe_name}|{person}]] ")

        # Organization links (with display text)
        for org in organizations:
            safe_name = slugify(org) or org.replace(' ', '-')
            lines.append(f"[[org:{safe_name}|{org}]] ")

        lines.append("")
        lines.append("<!-- RAG:IGNORE-END -->")

        return "\n".join(lines)

    def build_body(
        self,
        content: str,
        summary: str,
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

        # Source link section (added for linking to originals)
        # Note: Source filename is in frontmatter, this adds visibility
        body_parts.append("## Source")
        body_parts.append("")
        body_parts.append("See `source` in frontmatter for original filename.")
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
        body_parts.append("## Evidence / Excerpts\n")
        body_parts.append(clean_content)
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
        entity_type: str,  # person, project, place, org
        name: str,
        aliases: List[str] = None
    ):
        """
        Create/update entity stub for backlinks

        Example: refs/people/Mother.md
        """
        aliases = aliases or []

        # Determine directory
        entity_dir = self.refs_dir / f"{entity_type}s"
        entity_dir.mkdir(exist_ok=True)

        # Create filename
        safe_name = slugify(name) or name.replace(' ', '-')
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

        stub_yaml = yaml.dump(stub_frontmatter, default_flow_style=False, allow_unicode=True)

        # Map entity types to correct frontmatter field names
        field_name_map = {
            'person': 'people',
            'project': 'projects',
            'place': 'places',
            'org': 'organizations',
            'day': 'days'
        }
        field_name = field_name_map.get(entity_type, f"{entity_type}s")

        # Build stub body with Dataview query
        stub_body = f"""# {name}

```dataview
LIST FROM "10_normalized_md"
WHERE contains({field_name}, "{name}")
SORT created_at DESC
```
"""

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

        # Parse metadata lists
        people = self._parse_csv(metadata.get('people_roles', ''))
        places = self._parse_csv(metadata.get('places', ''))
        projects = self._parse_csv(metadata.get('projects', ''))
        topics = self._parse_csv(metadata.get('topics', ''))
        organizations = self._parse_csv(metadata.get('organizations', ''))

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

        # Create entity stubs
        for person in people:
            self.create_entity_stub('person', person)

        for project in projects:
            self.create_entity_stub('project', project)

        for place in places:
            self.create_entity_stub('place', place)

        for org in organizations:
            self.create_entity_stub('org', org)

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

    print(f"\n✅ Exported to: {result}")
    print(f"\n📄 Content preview:")
    print("=" * 60)
    print(result.read_text()[:800])
    print("=" * 60)

    # Check entity stubs
    refs_created = list((Path("./test_obsidian_v3/refs")).rglob("*.md"))
    print(f"\n📁 Created {len(refs_created)} entity stubs:")
    for ref in refs_created:
        print(f"   - {ref.relative_to('./test_obsidian_v3')}")
