"""
Entity Enrichment Service

Aggregates entity information from all documents and enriches entity reference files.
"""

from typing import Dict, List, Any, Set
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import yaml
from slugify import slugify
from src.core.config import get_settings

import logging
logger = logging.getLogger(__name__)


class EntityEnrichmentService:
    """
    Enriches entity reference files with aggregated information from documents
    """

    def __init__(self):
        self.settings = get_settings()
        self.obsidian_path = Path(self.settings.obsidian_path)
        self.refs_dir = self.obsidian_path / "refs"

    def enrich_all_entities(self, vector_service):
        """
        Main entry point: enrich all entity types

        Args:
            vector_service: VectorService instance to query documents
        """
        logger.info("🔍 Starting entity enrichment...")

        # Get all documents from ChromaDB
        docs = self._get_all_documents(vector_service)

        if not docs:
            logger.warning("No documents found for entity enrichment")
            return

        logger.info(f"📚 Found {len(docs)} documents to analyze")

        # Aggregate entity information
        people_data = self._aggregate_people(docs)
        org_data = self._aggregate_organizations(docs)
        place_data = self._aggregate_places(docs)
        tech_data = self._aggregate_technologies(docs)

        # Update entity reference files
        self._update_entity_refs("persons", people_data)
        self._update_entity_refs("orgs", org_data)
        self._update_entity_refs("places", place_data)
        self._update_entity_refs("technologies", tech_data)

        logger.info(f"✅ Entity enrichment complete: {len(people_data)} people, {len(org_data)} orgs, {len(place_data)} places, {len(tech_data)} tech")

    def _get_all_documents(self, vector_service) -> List[Dict[str, Any]]:
        """
        Get all documents from ChromaDB
        """
        try:
            # Query with empty string to get all documents
            results = vector_service.collection.get(
                include=['metadatas', 'documents']
            )

            docs = []
            if results and results.get('metadatas'):
                for i, metadata in enumerate(results['metadatas']):
                    doc = {
                        'metadata': metadata,
                        'content': results['documents'][i] if i < len(results['documents']) else ''
                    }
                    docs.append(doc)

            return docs
        except Exception as e:
            logger.error(f"Failed to get documents from ChromaDB: {e}")
            return []

    def _aggregate_people(self, docs: List[Dict]) -> Dict[str, Dict]:
        """
        Aggregate information about people from all documents

        Returns dict of: {person_name: {roles, organizations, emails, first_seen, last_seen, doc_count, documents}}
        """
        people = defaultdict(lambda: {
            'roles': set(),
            'organizations': set(),
            'emails': set(),
            'phones': set(),
            'first_seen': None,
            'last_seen': None,
            'doc_count': 0,
            'documents': []
        })

        for doc in docs:
            metadata = doc.get('metadata', {})

            # Extract people
            people_list = metadata.get('people', [])
            if isinstance(people_list, str):
                people_list = [people_list]

            # Get document date
            doc_date = metadata.get('created_at') or metadata.get('created_date')
            doc_title = metadata.get('title', 'Untitled')
            doc_id = metadata.get('doc_id', '')

            # Get sender email (for emails)
            sender = metadata.get('sender', '')
            sender_email = self._extract_email(sender)

            # Get people with roles
            people_detailed = metadata.get('people_detailed', [])

            for person in people_list:
                if not person or len(person.strip()) < 2:
                    continue

                person_name = person.strip()

                # Track document (store metadata for WikiLink generation)
                people[person_name]['doc_count'] += 1
                people[person_name]['documents'].append({
                    'title': doc_title,
                    'doc_id': doc_id,
                    'date': doc_date,
                    'metadata': metadata  # Store full metadata for WikiLink generation
                })

                # Track dates
                if doc_date:
                    if not people[person_name]['first_seen'] or doc_date < people[person_name]['first_seen']:
                        people[person_name]['first_seen'] = doc_date
                    if not people[person_name]['last_seen'] or doc_date > people[person_name]['last_seen']:
                        people[person_name]['last_seen'] = doc_date

                # Extract role if available
                if people_detailed:
                    for p in people_detailed:
                        if isinstance(p, dict):
                            p_name = p.get('name', '')
                            p_role = p.get('role', '')
                            if p_name == person_name and p_role:
                                people[person_name]['roles'].add(p_role)
                        elif isinstance(p, str) and '|' in p:
                            # Format: "Name | Role"
                            parts = p.split('|')
                            if len(parts) == 2:
                                p_name, p_role = parts[0].strip(), parts[1].strip()
                                if p_name == person_name and p_role:
                                    people[person_name]['roles'].add(p_role)

                # Extract organizations
                orgs = metadata.get('organizations', [])
                if isinstance(orgs, str):
                    orgs = [orgs]
                for org in orgs:
                    if org:
                        people[person_name]['organizations'].add(org)

                # Check if this person is the sender
                if sender_email and person_name.lower() in sender.lower():
                    people[person_name]['emails'].add(sender_email)

        # Convert sets to lists for serialization
        result = {}
        for person_name, data in people.items():
            result[person_name] = {
                'roles': list(data['roles']),
                'organizations': list(data['organizations']),
                'emails': list(data['emails']),
                'phones': list(data['phones']),
                'first_seen': data['first_seen'],
                'last_seen': data['last_seen'],
                'doc_count': data['doc_count'],
                'documents': data['documents'][:10]  # Limit to 10 most recent
            }

        return result

    def _aggregate_organizations(self, docs: List[Dict]) -> Dict[str, Dict]:
        """
        Aggregate information about organizations
        """
        orgs = defaultdict(lambda: {
            'locations': set(),
            'people': set(),
            'first_seen': None,
            'last_seen': None,
            'doc_count': 0,
            'documents': []
        })

        for doc in docs:
            metadata = doc.get('metadata', {})

            orgs_list = metadata.get('organizations', [])
            if isinstance(orgs_list, str):
                orgs_list = [orgs_list]

            doc_date = metadata.get('created_at') or metadata.get('created_date')
            doc_title = metadata.get('title', 'Untitled')
            doc_id = metadata.get('doc_id', '')

            # Get associated people
            people_list = metadata.get('people', [])
            if isinstance(people_list, str):
                people_list = [people_list]

            # Get locations
            locations = metadata.get('locations', [])
            if isinstance(locations, str):
                locations = [locations]

            for org in orgs_list:
                if not org or len(org.strip()) < 2:
                    continue

                org_name = org.strip()

                orgs[org_name]['doc_count'] += 1
                orgs[org_name]['documents'].append({
                    'title': doc_title,
                    'doc_id': doc_id,
                    'date': doc_date,
                    'metadata': metadata
                })

                if doc_date:
                    if not orgs[org_name]['first_seen'] or doc_date < orgs[org_name]['first_seen']:
                        orgs[org_name]['first_seen'] = doc_date
                    if not orgs[org_name]['last_seen'] or doc_date > orgs[org_name]['last_seen']:
                        orgs[org_name]['last_seen'] = doc_date

                # Associate people
                for person in people_list:
                    if person:
                        orgs[org_name]['people'].add(person)

                # Associate locations
                for loc in locations:
                    if loc:
                        orgs[org_name]['locations'].add(loc)

        # Convert sets to lists
        result = {}
        for org_name, data in orgs.items():
            result[org_name] = {
                'locations': list(data['locations']),
                'people': list(data['people'])[:20],  # Limit
                'first_seen': data['first_seen'],
                'last_seen': data['last_seen'],
                'doc_count': data['doc_count'],
                'documents': data['documents'][:10]
            }

        return result

    def _aggregate_places(self, docs: List[Dict]) -> Dict[str, Dict]:
        """
        Aggregate information about places
        """
        places = defaultdict(lambda: {
            'organizations': set(),
            'people': set(),
            'first_seen': None,
            'last_seen': None,
            'doc_count': 0,
            'documents': []
        })

        for doc in docs:
            metadata = doc.get('metadata', {})

            places_list = metadata.get('locations', [])
            if isinstance(places_list, str):
                places_list = [places_list]

            doc_date = metadata.get('created_at') or metadata.get('created_date')
            doc_title = metadata.get('title', 'Untitled')
            doc_id = metadata.get('doc_id', '')

            orgs_list = metadata.get('organizations', [])
            if isinstance(orgs_list, str):
                orgs_list = [orgs_list]

            people_list = metadata.get('people', [])
            if isinstance(people_list, str):
                people_list = [people_list]

            for place in places_list:
                if not place or len(place.strip()) < 2:
                    continue

                place_name = place.strip()

                places[place_name]['doc_count'] += 1
                places[place_name]['documents'].append({
                    'title': doc_title,
                    'doc_id': doc_id,
                    'date': doc_date,
                    'metadata': metadata
                })

                if doc_date:
                    if not places[place_name]['first_seen'] or doc_date < places[place_name]['first_seen']:
                        places[place_name]['first_seen'] = doc_date
                    if not places[place_name]['last_seen'] or doc_date > places[place_name]['last_seen']:
                        places[place_name]['last_seen'] = doc_date

                for org in orgs_list:
                    if org:
                        places[place_name]['organizations'].add(org)

                for person in people_list:
                    if person:
                        places[place_name]['people'].add(person)

        # Convert sets to lists
        result = {}
        for place_name, data in places.items():
            result[place_name] = {
                'organizations': list(data['organizations']),
                'people': list(data['people'])[:20],
                'first_seen': data['first_seen'],
                'last_seen': data['last_seen'],
                'doc_count': data['doc_count'],
                'documents': data['documents'][:10]
            }

        return result

    def _aggregate_technologies(self, docs: List[Dict]) -> Dict[str, Dict]:
        """
        Aggregate information about technologies
        """
        tech = defaultdict(lambda: {
            'organizations': set(),
            'people': set(),
            'first_seen': None,
            'last_seen': None,
            'doc_count': 0,
            'documents': []
        })

        for doc in docs:
            metadata = doc.get('metadata', {})

            tech_list = metadata.get('technologies', [])
            if isinstance(tech_list, str):
                tech_list = [tech_list]

            doc_date = metadata.get('created_at') or metadata.get('created_date')
            doc_title = metadata.get('title', 'Untitled')
            doc_id = metadata.get('doc_id', '')

            orgs_list = metadata.get('organizations', [])
            if isinstance(orgs_list, str):
                orgs_list = [orgs_list]

            people_list = metadata.get('people', [])
            if isinstance(people_list, str):
                people_list = [people_list]

            for t in tech_list:
                if not t or len(t.strip()) < 2:
                    continue

                tech_name = t.strip()

                tech[tech_name]['doc_count'] += 1
                tech[tech_name]['documents'].append({
                    'title': doc_title,
                    'doc_id': doc_id,
                    'date': doc_date,
                    'metadata': metadata
                })

                if doc_date:
                    if not tech[tech_name]['first_seen'] or doc_date < tech[tech_name]['first_seen']:
                        tech[tech_name]['first_seen'] = doc_date
                    if not tech[tech_name]['last_seen'] or doc_date > tech[tech_name]['last_seen']:
                        tech[tech_name]['last_seen'] = doc_date

                for org in orgs_list:
                    if org:
                        tech[tech_name]['organizations'].add(org)

                for person in people_list:
                    if person:
                        tech[tech_name]['people'].add(person)

        # Convert sets to lists
        result = {}
        for tech_name, data in tech.items():
            result[tech_name] = {
                'organizations': list(data['organizations']),
                'people': list(data['people'])[:20],
                'first_seen': data['first_seen'],
                'last_seen': data['last_seen'],
                'doc_count': data['doc_count'],
                'documents': data['documents'][:10]
            }

        return result

    def _update_entity_refs(self, entity_dir: str, entity_data: Dict[str, Dict]):
        """
        Update entity reference files with enriched data

        Args:
            entity_dir: Directory name (persons, orgs, places, technologies)
            entity_data: Dict of entity_name -> enriched_data
        """
        refs_path = self.refs_dir / entity_dir

        if not refs_path.exists():
            logger.warning(f"Entity directory not found: {refs_path}")
            return

        for entity_name, data in entity_data.items():
            safe_name = slugify(entity_name)
            if not safe_name:
                continue

            file_path = refs_path / f"{safe_name}.md"

            if not file_path.exists():
                logger.debug(f"Entity stub not found: {file_path}")
                continue

            # Read existing file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Update frontmatter and body
                updated_content = self._inject_enrichment(content, entity_name, entity_dir, data)

                # Write back
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)

                logger.debug(f"✅ Enriched {entity_dir}/{safe_name}.md")

            except Exception as e:
                logger.error(f"Failed to update {file_path}: {e}")

    def _inject_enrichment(self, content: str, entity_name: str, entity_type: str, data: Dict) -> str:
        """
        Inject enrichment data into entity reference file
        """
        lines = content.split('\n')

        # Find frontmatter end
        frontmatter_end = -1
        in_frontmatter = False
        for i, line in enumerate(lines):
            if line.strip() == '---':
                if not in_frontmatter:
                    in_frontmatter = True
                else:
                    frontmatter_end = i
                    break

        if frontmatter_end == -1:
            # No frontmatter, add at top
            enrichment_section = self._build_enrichment_section(entity_name, entity_type, data)
            return enrichment_section + "\n\n" + content

        # Parse existing frontmatter
        frontmatter_lines = lines[1:frontmatter_end]
        frontmatter_text = '\n'.join(frontmatter_lines)

        try:
            frontmatter = yaml.safe_load(frontmatter_text) or {}
        except:
            frontmatter = {}

        # Add enrichment fields to frontmatter
        frontmatter['enriched'] = True
        frontmatter['enrichment_date'] = datetime.now().isoformat()
        frontmatter['doc_count'] = data.get('doc_count', 0)
        frontmatter['first_seen'] = data.get('first_seen')
        frontmatter['last_seen'] = data.get('last_seen')

        if entity_type == "persons":
            if data.get('roles'):
                frontmatter['roles'] = data['roles']
            if data.get('organizations'):
                frontmatter['organizations'] = data['organizations']
            if data.get('emails'):
                frontmatter['emails'] = data['emails']

        elif entity_type == "orgs":
            if data.get('locations'):
                frontmatter['locations'] = data['locations']
            if data.get('people'):
                frontmatter['key_people'] = data['people'][:10]

        elif entity_type == "places":
            if data.get('organizations'):
                frontmatter['related_orgs'] = data['organizations']

        # Rebuild frontmatter
        new_frontmatter = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)

        # Build enrichment section
        enrichment_body = self._build_enrichment_body(entity_name, entity_type, data)

        # Insert enrichment section after frontmatter, before dataview queries
        body_lines = lines[frontmatter_end + 1:]

        # Find where to insert (before dataview or at end of intro)
        insert_pos = 0
        for i, line in enumerate(body_lines):
            if '```dataview' in line:
                insert_pos = i
                break
        else:
            # No dataview found, insert after title
            for i, line in enumerate(body_lines):
                if line.startswith('# '):
                    insert_pos = i + 1
                    break

        # Reconstruct
        result = ['---', new_frontmatter.strip(), '---']
        result.extend(body_lines[:insert_pos])
        result.append(enrichment_body)
        result.extend(body_lines[insert_pos:])

        return '\n'.join(result)

    def _build_enrichment_section(self, entity_name: str, entity_type: str, data: Dict) -> str:
        """
        Build enrichment section for entities without existing files
        """
        return f"---\nname: {entity_name}\nenriched: true\n---\n\n# {entity_name}\n\n{self._build_enrichment_body(entity_name, entity_type, data)}"

    def _build_enrichment_body(self, entity_name: str, entity_type: str, data: Dict) -> str:
        """
        Build enrichment body section
        """
        lines = ["\n## Enriched Information\n"]

        # Stats
        doc_count = data.get('doc_count', 0)
        first_seen = data.get('first_seen', 'Unknown')
        last_seen = data.get('last_seen', 'Unknown')

        lines.append(f"📊 **Mentions:** {doc_count} documents")
        lines.append(f"📅 **First seen:** {first_seen}")
        lines.append(f"📅 **Last seen:** {last_seen}")
        lines.append("")

        # Entity-specific sections
        if entity_type == "persons":
            if data.get('roles'):
                lines.append("### Roles")
                for role in data['roles']:
                    lines.append(f"- {role}")
                lines.append("")

            if data.get('organizations'):
                lines.append("### Organizations")
                for org in data['organizations']:
                    org_slug = slugify(org)
                    lines.append(f"- [[refs/orgs/{org_slug}|{org}]]")
                lines.append("")

            if data.get('emails'):
                lines.append("### Contact")
                for email in data['emails']:
                    lines.append(f"- 📧 {email}")
                lines.append("")

        elif entity_type == "orgs":
            if data.get('locations'):
                lines.append("### Locations")
                for loc in data['locations']:
                    loc_slug = slugify(loc)
                    lines.append(f"- [[refs/places/{loc_slug}|{loc}]]")
                lines.append("")

            if data.get('people'):
                lines.append("### Key People")
                for person in data['people'][:10]:
                    person_slug = slugify(person)
                    lines.append(f"- [[refs/persons/{person_slug}|{person}]]")
                lines.append("")

        elif entity_type == "places":
            if data.get('organizations'):
                lines.append("### Organizations")
                for org in data['organizations']:
                    org_slug = slugify(org)
                    lines.append(f"- [[refs/orgs/{org_slug}|{org}]]")
                lines.append("")

        elif entity_type == "technologies":
            if data.get('organizations'):
                lines.append("### Used By")
                for org in data['organizations']:
                    org_slug = slugify(org)
                    lines.append(f"- [[refs/orgs/{org_slug}|{org}]]")
                lines.append("")

        # Recent documents with proper WikiLinks
        if data.get('documents'):
            lines.append("### Recent Documents")
            for doc in data['documents'][:5]:
                title = doc.get('title', 'Untitled')
                date = doc.get('date', '')

                # Get metadata to generate proper WikiLink filename
                doc_metadata = doc.get('metadata', {})
                if doc_metadata:
                    # Import here to avoid circular dependency
                    from src.services.obsidian_service import ObsidianService
                    obs_service = ObsidianService()
                    wikilink_name = obs_service.get_wikilink_name(doc_metadata)
                    lines.append(f"- {date}: [[{wikilink_name}|{title}]]")
                else:
                    # Fallback to doc_id if no metadata
                    doc_id = doc.get('doc_id', '')
                    lines.append(f"- {date}: [[{doc_id}|{title}]]")
            lines.append("")

        return '\n'.join(lines)

    def _extract_email(self, sender: str) -> str:
        """
        Extract email address from sender string like "Name <email@example.com>"
        """
        import re
        match = re.search(r'<(.+?)>', sender)
        if match:
            return match.group(1)
        # Check if entire string is email
        if '@' in sender and '.' in sender:
            return sender.strip()
        return ""
