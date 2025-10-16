# Entity Linking & Reference Notes System

**Status:** ✅ Production Ready (October 16, 2025)
**Version:** 1.0
**Coverage:** 6 Entity Types with Full Template Support

## Overview

The RAG Provider implements a comprehensive entity linking system that automatically creates structured reference notes for all extracted entities. Each entity type has a specialized template with rich metadata support, concept linking, and bidirectional Dataview queries.

## Supported Entity Types

| Entity Type | Directory | Template Status | Features |
|-------------|-----------|----------------|----------|
| **Technologies** | `refs/technologies/` | ✅ Enhanced | Type, concept linking, vocabulary suggestions |
| **People** | `refs/persons/` | ✅ Enhanced | Contact info, roles, relationships, vCard export |
| **Organizations** | `refs/orgs/` | ✅ Enhanced | Industry, headquarters, contacts, projects |
| **Places** | `refs/places/` | ✅ Enhanced | GPS, address, contacts, OpenStreetMap integration |
| **Projects** | `refs/projects/` | ✅ Enhanced | Timeline, stakeholders, organizations, goals |
| **Daily Notes** | `refs/days/` | ✅ Standard | Document timeline, events, temporal linking |

## Entity Template Features

### 1. Technologies (`refs/technologies/`)

**Metadata Fields:**
- `type`: Software, Hardware, Platform, Tool, Framework
- `concept_id`: Link to controlled vocabulary (if available)
- `prefLabel`: Preferred label from vocabulary
- `altLabels`: Alternative names/synonyms
- `category`: Hierarchical classification (e.g., `technology/linux`)
- `suggested_for_vocab`: Boolean flag for vocabulary expansion

**Example:**
```markdown
---
name: Pop!_OS
type: technology
---

# Pop!_OS

**Type:** Software

> 💡 **Suggested for Vocabulary:** This technology is not yet in the controlled vocabulary. Consider adding it.

## Related Documents
[Dataview query showing all documents mentioning this technology]
```

**Concept Linking:**
- Automatically links to controlled vocabulary when `concept_id` present
- Displays alternative labels for search/discovery
- Suggests new technologies for vocabulary expansion

### 2. People (`refs/persons/`)

**Metadata Fields:**
- `name`: Full name
- `role`: Job title or relationship
- `email`: Contact email (vCard compatible)
- `phone`: Phone number (vCard compatible)
- `address`: Physical address
- `organization`: Employer/affiliation
- `birth_date`: Date of birth
- `contact_type`: `personal` (has contact info) or `reference` (mentioned only)
- `relationships`: List of related people with relationship types

**Example:**
```markdown
---
name: Daniel Teckentrup
role: Parent, Project Lead
contact_type: reference
type: person
---

# Daniel Teckentrup

**Role:** Parent, Project Lead

## Related Documents
[Dataview query...]

## Resources
- vCard: `daniel-teckentrup.vcf`
```

**Contact Integration:**
- vCard export for contacts with email/phone
- Relationship mapping with wikilinks to other person notes
- Distinguishes between personal contacts and references

### 3. Organizations (`refs/orgs/`)

**Metadata Fields:**
- `type`: Company, Non-Profit, Government, Educational Institution
- `industry`: Business sector/domain
- `headquarters`: Location/address
- `website`: Official website URL
- `contacts`: List of key contact people (wikilinks)
- `projects`: Related projects (wikilinks)
- `description`: Organization summary

**Example:**
```markdown
---
name: Anthropic
type: org
---

# Anthropic

**Type:** Technology Company
**Industry:** Artificial Intelligence
**Headquarters:** San Francisco, CA
**Website:** [https://anthropic.com](https://anthropic.com)

**Key Contacts:**
- [[refs/persons/daniel-teckentrup|Daniel Teckentrup]]

**Related Projects:**
- [[refs/projects/rag-provider|RAG Provider]]

## Related Documents
[Dataview query...]
```

**Cross-Entity Linking:**
- Links to employee/member person notes
- Links to project notes
- Enables organizational graph visualization

### 4. Places (`refs/places/`)

**Metadata Fields:**
- `type`: Home, School, Office, Restaurant, Medical, etc.
- `address`: Full address
- `latitude`: GPS latitude
- `longitude`: GPS longitude
- `contacts`: Related people (wikilinks)
- `category`: Classification (home, school, business, medical)
- `description`: Place description
- `notes`: Visit history, hours, etc.

**Example:**
```markdown
---
name: Villa Luna Kita
address: Hauptstraße 45, 10827 Berlin, Germany
latitude: 52.4862
longitude: 13.3524
category: education/kindergarten
type: place
---

# Villa Luna Kita

**Type:** Educational Institution
**Address:** Hauptstraße 45, 10827 Berlin, Germany
**GPS:** 52.4862, 13.3524
**Map:** [OpenStreetMap](https://www.openstreetmap.org/?mlat=52.4862&mlon=13.3524#map=15/52.4862/13.3524)

**Related Contacts:**
- [[refs/persons/daniel-teckentrup|Daniel Teckentrup]]

**Category:** education/kindergarten

## Related Documents
[Dataview query...]

## Documents Mentioning This Place
[Backlink query...]
```

**Geographic Features:**
- OpenStreetMap integration (privacy-friendly)
- GPS coordinates for mapping/visualization
- Address normalization
- Contact-place relationship mapping

### 5. Projects (`refs/projects/`)

**Metadata Fields:**
- `status`: Active, Completed, On Hold, Cancelled
- `start_date`: Project start date (wikilink to daily note)
- `end_date`: Project end date (wikilink to daily note)
- `stakeholders`: List of people involved (wikilinks)
- `organizations`: Organizations involved (wikilinks)
- `category`: research, business, personal, etc.
- `goals`: List of objectives
- `description`: Project summary

**Example:**
```markdown
---
name: School Enrollment 2026
status: Active
type: project
---

# School Enrollment 2026

**Status:** Active

**Timeline:**
- Start: [[2026-01-05]]
- End: [[2026-09-01]]

**Stakeholders:**
- [[refs/persons/daniel-teckentrup|Daniel Teckentrup]]
- [[refs/persons/fanny-schmidt|Fanny Schmidt]]

**Organizations:**
- [[refs/orgs/villa-luna-kita|Villa Luna Kita]]

**Category:** personal/education

**Goals:**
- Secure kindergarten placement for Emma
- Complete all enrollment requirements by deadline
- Budget within €4,050 allocation

## Related Documents
[Dataview query...]

## Project Timeline
[Chronological document list...]
```

**Project Management:**
- Timeline visualization with date wikilinks
- Stakeholder tracking
- Organization involvement
- Goal/objective tracking

### 6. Daily Notes (`refs/days/`)

**Metadata Fields:**
- `date`: ISO date (YYYY-MM-DD)
- `week`: Wikilink to week note
- `month`: Wikilink to month note
- `documents`: List of documents created/modified this day

**Example:**
```markdown
---
date: '2025-10-16'
type: daily-note
week: '[[weeks/2025-W42]]'
month: '[[months/2025-10]]'
---

# Thursday, October 16, 2025

← [[weeks/2025-W42|Week 42]] | [[months/2025-10|October 2025]] →

## 🤖 LLM Conversations
- [[doc-id|Chat about Linux distributions]]

## 📄 Other Documents
- [[doc-id|Villa Luna enrollment planning]]

## Events on This Date
[Dataview query showing deadlines, meetings, etc.]
```

**Temporal Navigation:**
- Hierarchical time structure (day → week → month)
- Document creation tracking
- Event/deadline aggregation

## Document Sections

All main documents automatically include entity sections with wikilinks:

```markdown
## People
- [[refs/persons/daniel-teckentrup|Daniel Teckentrup]] (Parent)

## Technologies
- [[refs/technologies/obsidian|Obsidian]] (Software)

## Organizations
- [[refs/orgs/anthropic|Anthropic]] (AI Company)

## Projects
- [[refs/projects/school-2026|School 2026]] (Active)

## Important Dates
- [[2026-01-05]]: Project start
```

## Concept Linking System

### Controlled Vocabularies

Entities can link to controlled vocabularies via `concept_id`:

```yaml
# technologies.yaml
- id: tech_001
  prefLabel: "Docker"
  altLabels: ["Docker Engine", "Docker Desktop", "docker"]
  category: "technology/containers"
  type: "Platform"
```

When an entity is extracted, the system:
1. Attempts to match against controlled vocabulary
2. If match found: Sets `concept_id`, `prefLabel`, `altLabels`
3. If no match: Flags `suggested_for_vocab: true`
4. Reference note displays concept linking metadata

### Vocabulary Growth

The system supports dynamic vocabulary expansion:

**Manual Addition:**
1. Review entities with `suggested_for_vocab: true`
2. Add to appropriate YAML file (`vocabulary/technologies.yaml`, etc.)
3. Re-ingest document to link to vocabulary

**Automated Suggestion:**
- Tracks frequency of suggested entities
- Prioritizes commonly extracted entities
- Suggests batch additions to vocabularies

## Dataview Queries

All reference notes include Dataview queries for backlinking:

### Standard Query (all entity types):
```dataview
TABLE file.link as "Document", summary as "Summary", topics as "Topics"
WHERE contains(field_name, "Entity Name")
SORT file.mtime DESC
LIMIT 50
```

### Place-Specific Query:
```dataview
TABLE file.link as "Document", summary as "Summary"
WHERE contains(file.outlinks, this.file.link)
SORT file.mtime DESC
LIMIT 50
```

### Project Timeline Query:
```dataview
TABLE dates as "Date", summary as "Summary"
WHERE contains(projects, "Project Name")
SORT dates ASC
LIMIT 100
```

## Cross-Entity Relationships

The system supports rich entity relationships:

### Person → Organization
```markdown
**Organization:** [[refs/orgs/anthropic|Anthropic]]
```

### Organization → People
```markdown
**Key Contacts:**
- [[refs/persons/daniel-teckentrup|Daniel Teckentrup]]
```

### Place → Contacts
```markdown
**Related Contacts:**
- [[refs/persons/emma-teckentrup|Emma Teckentrup]]
```

### Project → Stakeholders + Organizations
```markdown
**Stakeholders:**
- [[refs/persons/daniel-teckentrup|Daniel Teckentrup]]

**Organizations:**
- [[refs/orgs/villa-luna-kita|Villa Luna Kita]]
```

## Implementation Details

### Reference Note Creation

When a document is ingested:

1. **Entity Extraction:** LLM extracts entities from content
2. **Concept Linking:** Match entities to controlled vocabularies
3. **Metadata Enrichment:** Add type, category, relationships
4. **Reference Note Creation:**
   - Check if note exists (prevent overwrites)
   - Build frontmatter with entity-specific fields
   - Build body with appropriate template
   - Write to `refs/{entity_type}s/{slug}.md`
5. **Document Linking:** Add entity sections to main document

### File Naming

Entity slugs are created via `slugify()`:
- Lowercase
- Replace spaces with hyphens
- Remove special characters
- Example: "Villa Luna Kita" → "villa-luna-kita"

### Frontmatter Standards

All reference notes include:
- `type`: Entity type (technology, person, org, place, project, day)
- `name`: Display name
- `aliases`: Alternative names (optional)
- Entity-specific fields (see templates above)

## Testing & Validation

### Test Coverage

**Comprehensive Entity Test Document** (`comprehensive_entity_test.md`):
- ✅ 3 People extracted (Daniel, Fanny, Emma)
- ✅ 3 Organizations extracted (Villa Luna, Berlin Edu Dept, Anthropic)
- ✅ 6 Technologies extracted (Obsidian, Google Calendar, WhatsApp, Zoom, Excel, Notion)
- ✅ 1 Place extracted (Berlin)
- ✅ 11 Chunks created
- ✅ All entity types have reference notes
- ✅ All entity sections displayed in document
- ✅ Wikilinks functional across entity types

**LLM Chat Test Document** (`test_chat_linux_discussion.md`):
- ✅ 7 Chunks from 8 turns (strategic turn-based chunking)
- ✅ 11 Technologies extracted with concept linking
- ✅ 1 Organization (System76)
- ✅ Self-validation prevents false positives (e.g., "Virtual Machine" not classified as person)

**Place Enrichment Test** (`test_place_enrichment.md`):
- ✅ Place extraction working
- ✅ Reference notes created
- ✅ Template supports GPS/address metadata

### Validation Checklist

For each entity type, verify:
- [ ] Reference note created in correct directory
- [ ] Frontmatter includes entity-specific fields
- [ ] Body template renders correctly
- [ ] Dataview queries functional
- [ ] Wikilinks resolve to correct notes
- [ ] Cross-entity linking works (person → org, place → contacts, etc.)
- [ ] Concept linking metadata displayed (for technologies)
- [ ] Graceful degradation when metadata unavailable

## Future Enhancements

### Planned Features

1. **Geographic Visualization**
   - Obsidian map plugin integration
   - Display places on interactive map
   - Cluster related places by category

2. **Timeline Visualization**
   - Project Gantt charts
   - Event calendar views
   - Deadline tracking

3. **Network Graph Enhancements**
   - Entity relationship visualization
   - Influence mapping
   - Collaboration patterns

4. **Automated GPS Extraction**
   - LLM-based address → GPS conversion
   - Geocoding service integration
   - Address normalization

5. **Vocabulary Management UI**
   - Review suggested entities
   - Batch vocabulary additions
   - Merge duplicate entities

6. **Entity Statistics**
   - Most mentioned people/orgs
   - Technology usage patterns
   - Project timeline analytics

## API Integration

### Enrichment Service

The enrichment service handles entity extraction and linking:

```python
from src.services.enrichment_service import EnrichmentService

enrichment = await enrichment_service.enrich_document(
    text=content,
    filename="document.md"
)

# Access entities
technologies = enrichment.get('entities', {}).get('technologies', [])
for tech in technologies:
    print(f"{tech['label']} - {tech['type']}")
    print(f"  Concept ID: {tech['concept_id']}")
    print(f"  Suggested for vocab: {tech['suggested_for_vocab']}")
```

### Obsidian Service

The Obsidian service creates reference notes:

```python
from src.services.obsidian_service import ObsidianService

obsidian = ObsidianService(output_dir="/data/obsidian")

# Create technology reference note
obsidian.create_entity_stub(
    entity_type='technology',
    name='Docker',
    person_data={  # tech_data passed via person_data param
        'type': 'Platform',
        'concept_id': 'tech_001',
        'prefLabel': 'Docker',
        'altLabels': ['Docker Engine', 'Docker Desktop'],
        'category': 'technology/containers',
        'suggested_for_vocab': False
    }
)
```

## Best Practices

### Entity Extraction

1. **Use Self-Validation:** Enable LLM self-validation to catch classification errors
2. **Review Suggested Entities:** Regularly review `suggested_for_vocab` flags
3. **Maintain Vocabularies:** Keep YAML files updated with commonly used terms
4. **Cross-Check Dates:** Ensure temporal entities link correctly to daily notes

### Reference Note Management

1. **Don't Overwrite:** Reference notes are created once (prevent data loss)
2. **Manual Enrichment:** Add metadata manually to reference notes as needed
3. **Batch Updates:** Use scripts to update frontmatter across multiple notes
4. **Backup Regular:** Git commit reference notes regularly

### Performance

1. **Limit Entity Counts:** Reference notes handle 50+ entities efficiently
2. **Query Optimization:** Dataview queries cached by Obsidian
3. **Lazy Loading:** Notes loaded on-demand (no startup penalty)
4. **Index Maintenance:** Obsidian indexes update incrementally

## Troubleshooting

### Common Issues

**Entity not linking to vocabulary:**
- Check vocabulary YAML file exists
- Verify `concept_id` format matches
- Re-ingest document after vocabulary update

**Reference note not created:**
- Check slugify() output (may have special characters)
- Verify directory permissions (`refs/{type}s/` must exist)
- Check Docker container has write access

**Wikilink not resolving:**
- Verify slug matches filename exactly
- Check for typos in manual links
- Ensure note exists in correct directory

**Dataview query showing no results:**
- Check field name matches metadata field
- Verify entity name matches exactly (case-sensitive)
- Test query in Obsidian query builder

## Architecture Summary

```
Document Ingestion
  ↓
Entity Extraction (LLM)
  ↓
Concept Linking (VocabularyService)
  ↓
Metadata Enrichment
  ↓
Reference Note Creation (ObsidianService)
  ├── Technologies → refs/technologies/
  ├── People → refs/persons/
  ├── Organizations → refs/orgs/
  ├── Places → refs/places/
  ├── Projects → refs/projects/
  └── Dates → refs/days/
  ↓
Document Export with Entity Sections
  ├## Technologies
  ├## People
  ├## Organizations
  ├## Projects
  └## Important Dates
```

## Related Documentation

- [Testing Guide](TESTING_GUIDE.md) - Entity extraction test suites
- [Architecture](../architecture/ARCHITECTURE.md) - System design overview
- [Maintenance](MAINTENANCE.md) - Vocabulary management

---

**Last Updated:** October 16, 2025
**Contributors:** Claude Code AI Assistant
**Status:** ✅ Production Ready
