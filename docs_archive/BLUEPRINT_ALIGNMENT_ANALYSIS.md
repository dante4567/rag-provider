# Blueprint Alignment Analysis - October 7, 2025

## User Questions

1. **"is this the right property type of rag in frontmatter? 1 string in brackets?"**
2. **"shoulnt there be more linking, tag usage perhaps even graph?"**
3. **".... and more info e.g. on persons, places......"**

---

## Current vs. Blueprint Comparison

### 1. Frontmatter Structure ⚠️ **MISALIGNED**

**Blueprint Spec** (`personal_rag_pipeline_full.md`):
```yaml
---
id: 2025-10-05_email-thread_kita-handover_7c1a
source: email
path: mail/2025/10/kita-handover-thread.md
created_at: 2025-10-02
ingested_at: 2025-10-05
doc_type: correspondence.thread
title: "Kita handover schedule discussion (Sep–Oct 2025)"

# Controlled vocabulary (top-level lists)
people: [Daniel, Mother, Kita Astronauten]
places: [Köln Südstadt, Essen Rüttenscheid]
projects: [custody-2025, school-2026]
topics: [kita, handover, schedule, pickup]

# Separate entities section
entities:
  orgs: [Kita XY]
  dates: ["2025-09-29", "2025-10-02"]
  numbers: []

summary: >
  Thread covers handover times, late pickups, and planned changes after autumn break.

# Scores (TOP-LEVEL, not nested)
quality_score: 0.94
novelty_score: 0.72
actionability_score: 0.80
signalness: 0.85
do_index: true

# Provenance (top-level)
provenance:
  sha256: "…"
  mailbox: "INBOX/kita"
  message_ids: ["<…>", "<…>"]
enrichment_version: v2.1
---
```

**Our Current Implementation** ❌:
```yaml
---
id: 20251007_upload-6e34e24c-f85d-4213-b31c-173254af4_4384
title: upload 6e34e24c f85d 4213 b31c 173254af4652 sample invoice
source: upload_6e34e24c-f85d-4213-b31c-173254af4652_sample_invoice.md
doc_type: text

# Lists (correct)
organizations:
- Acme Corporation
- Example Bank
topics:
- business/accounting
- business/finance

# Tags (added, not in blueprint)
tags:
- doc/text
- topic/business-accounting

# WRONG: Nested under 'rag:' instead of top-level
rag:
  quality_score: 1.0
  novelty_score: 0.6
  actionability_score: 0.6
  recency_score: 1.0
  signalness: 0.76
  do_index: true
  canonical: true
  enrichment_version: '2.0'
  enrichment_cost_usd: 5.0e-05
  provenance:
    sha256: 4384d5fbe8958df1
    sha256_full: 4384d5fbe8958df17708d467e1ebac24
---
```

### 2. Entities Structure ⚠️ **MISSING**

**Blueprint**:
```yaml
entities:
  orgs: [Kita XY, Example Corp]
  dates: ["2025-09-29", "2025-10-02"]
  numbers: ["+49-123-456", "€1,500"]
```

**Our Implementation**: ❌
- No `entities:` section
- Organizations mixed into top-level `organizations:` list
- No `dates:` extraction
- No `numbers:` extraction (phone, amounts, etc.)

### 3. Graph/Linking ⚠️ **PARTIAL**

**What We Have**:
- Basic wiki-links: `[[org:Acme Corporation]]`
- Entity stubs with Dataview queries
- Tags for hierarchical organization

**What's Missing** (per blueprint):
- Date entity links: `[[day:2025-10-07]]`
- Number/amount tracking
- Richer entity metadata (see below)
- Timeline visualization
- Cross-document relationship graphs

### 4. Person/Place Metadata ⚠️ **INSUFFICIENT**

**Blueprint Expectation**:
Each person/place should have:
- Aliases (multiple names/spellings)
- Relationships (parent → child, spouse, etc.)
- Locations (home, work, frequent places)
- Context (role in documents, relevance)
- Statistics (doc count, topics, timeline)

**Our Current Entity Stubs**:
```yaml
---
type: place
name: Köln
aliases: []
---

# Köln

```dataview
LIST FROM "10_normalized_md"
WHERE contains(places, "Köln")
SORT created_at DESC
```
```

**Missing**:
- Address/coordinates
- Type (city, building, institution)
- Relationships (part of region, contains locations)
- Context (why this place matters)
- Timeline (first/last mentioned, frequency)

---

## Critical Fixes Required

### Fix 1: Restructure Frontmatter ✅ TOP PRIORITY

**Move from**:
```yaml
rag:
  quality_score: 1.0
  novelty_score: 0.6
  provenance:
    sha256: ...
```

**To** (blueprint-compliant):
```yaml
# Scores (top-level)
quality_score: 1.0
novelty_score: 0.6
actionability_score: 0.6
signalness: 0.76
do_index: true

# Entities (separate section)
entities:
  orgs: [Acme Corporation, Example Bank]
  dates: ["2025-10-07", "2025-11-06"]
  numbers: ["$10,472", "+49-123-456"]

# Provenance (top-level)
provenance:
  sha256: 4384d5fbe8958df1
  sha256_full: 4384d5fbe8958df17708d467e1ebac24
  original_filename: sample_invoice.md
  file_size_mb: 0.001
  ingestion_date: 2025-10-07T21:46:54

# Enrichment metadata (top-level)
enrichment_version: v2.0
enrichment_cost_usd: 0.00005
```

### Fix 2: Add Entities Section ✅ REQUIRED

Extract and separate:
- `entities.orgs` - Organizations (from controlled vocab or detected)
- `entities.dates` - All dates mentioned (ISO format)
- `entities.numbers` - Amounts, phone numbers, IDs, etc.

### Fix 3: Enhanced Entity Metadata ✅ IMPORTANT

**Person Stub Enhancement**:
```yaml
---
type: person
name: Daniel Teckentrup
aliases: [Daniel, DT, Dante]
role: Parent
relationships:
  - type: parent_of
    target: Pola
  - type: co_parent
    target: Mother
locations:
  - Köln Südstadt (primary)
  - Essen Rüttenscheid (visits)
context: >
  Primary parent in custody arrangement. Involved in school, kita,
  legal proceedings. Active in school-2026 project.
---

# Daniel Teckentrup

> [!info] Quick Stats
> **Documents**: `$= ...`
> **Active Projects**: [[project:custody-2025]], [[project:school-2026]]
> **Locations**: [[place:Köln Südstadt]], [[place:Essen Rüttenscheid]]
> **Most Common Topics**: education, legal, family

## Recent Activity

```dataview
TABLE file.ctime as "Date", topics[0] as "Topic", rag.signalness as "Signal"
FROM "data/obsidian"
WHERE contains(people, "Daniel Teckentrup")
SORT file.ctime DESC
LIMIT 15
```

## Timeline View

```dataview
CALENDAR file.ctime
FROM "data/obsidian"
WHERE contains(people, "Daniel Teckentrup")
```

## By Project

```dataview
TABLE rows.file.link as "Documents", length(rows) as "Count"
FROM "data/obsidian"
WHERE contains(people, "Daniel Teckentrup")
GROUP BY projects[0] as "Project"
SORT length(rows) DESC
```

## Relationships

- **Child**: [[person:Pola]]
- **Co-parent**: [[person:Mother]]
- **Related**: [[person:Teacher]], [[person:Kita Staff]]
```

**Place Stub Enhancement**:
```yaml
---
type: place
name: Köln Südstadt
aliases: [Cologne Südstadt, Koeln Suedstadt]
place_type: neighborhood
parent_location: Köln
coordinates: [50.9167, 6.9500]
context: >
  Primary residence area. Home location for Daniel and Pola.
  Kita Astronauten location. School enrollment district.
---

# Köln Südstadt

> [!info] Location Info
> **Type**: Neighborhood
> **City**: [[place:Köln]]
> **Significance**: Primary residence, Kita location, school district

## Documents About This Location

```dataview
TABLE file.ctime as "Date", doc_type as "Type", summary
FROM "data/obsidian"
WHERE contains(places, "Köln Südstadt")
SORT file.ctime DESC
LIMIT 15
```

## Related Places

- [[place:Köln]] (parent city)
- [[place:Kita Astronauten]] (institution)
- [[place:Essen Rüttenscheid]] (related - co-parent location)

## Timeline

First mentioned: `$= dv.pages('"data/obsidian"').where(p => p.places?.includes("Köln Südstadt")).sort(p => p.created_at).first()?.created_at`

Last mentioned: `$= dv.pages('"data/obsidian"').where(p => p.places?.includes("Köln Südstadt")).sort(p => p.created_at, 'desc').first()?.created_at`
```

### Fix 4: Date Entity Linking ✅ HIGH VALUE

**Create date stubs**: `refs/days/2025-10-07.md`

```yaml
---
type: day
date: 2025-10-07
day_of_week: Tuesday
week_number: 41
month: October
year: 2025
---

# 2025-10-07 (Tuesday)

> [!calendar] Week 41, October 2025

## Documents Created/Received

```dataview
LIST summary
FROM "data/obsidian"
WHERE created_at = "2025-10-07"
SORT file.ctime ASC
```

## Documents Mentioning This Date

```dataview
LIST summary
FROM "data/obsidian"
WHERE contains(string(file), "2025-10-07") OR contains(entities.dates, "2025-10-07")
```

## Events & Deadlines

```dataview
TASK
FROM "data/obsidian"
WHERE contains(entities.dates, "2025-10-07")
```

## Statistics

- Documents created: `$= ...`
- Documents mentioning: `$= ...`
- Avg quality: `$= ...`
```

**Link to dates in documents**:
```markdown
## Timeline

- [[day:2025-10-07]] -- Invoice sent
- [[day:2025-11-06]] -- Payment due
- [[day:2025-09-29]] -- Project kickoff
```

### Fix 5: Graph Visualization Enhancements ✅

**Add cross-document links**:
```markdown
<!-- RAG:IGNORE-START -->

## Related Documents

### Same Project
- [[2025-09-15__text__website-redesign-proposal]] (proposal)
- [[2025-10-01__text__project-kickoff-meeting]] (kickoff)
- [[2025-10-07__text__invoice-2025-1042]] (current)

### Same Client
- [[2025-08-20__text__acme-initial-contact]]
- [[2025-09-01__pdf__acme-contract]]

### Related Topics
- [[topic:web-development]] (primary)
- [[topic:ui-design]] (component)
- [[topic:invoicing]] (process)

<!-- RAG:IGNORE-END -->
```

---

## Implementation Priority

### Phase 1: Frontmatter Restructure (2-3 hours) 🔴 CRITICAL
- [ ] Move scores from `rag:` to top-level
- [ ] Create `entities:` section with orgs, dates, numbers
- [ ] Move `provenance:` to top-level
- [ ] Move `enrichment_version`, `enrichment_cost_usd` to top-level
- [ ] Update all existing documents
- [ ] Update `obsidian_service.py`

### Phase 2: Entity Enhancement (3-4 hours) 🟡 HIGH VALUE
- [ ] Enhanced person stubs (aliases, relationships, context, stats)
- [ ] Enhanced place stubs (type, coordinates, parent, context)
- [ ] Enhanced org stubs (industry, role, context)
- [ ] Date entity stubs (day/week/month views)

### Phase 3: Entities Extraction (2-3 hours) 🟡 HIGH VALUE
- [ ] Extract dates from content (regex + NER)
- [ ] Extract numbers (amounts, phones, IDs)
- [ ] Populate `entities.dates` and `entities.numbers`
- [ ] Link to date stubs

### Phase 4: Graph Enhancement (2-3 hours) 🟢 NICE TO HAVE
- [ ] Cross-document links (same project, same client, same topic)
- [ ] Temporal navigation (prev/next in timeline)
- [ ] Related documents section
- [ ] Graph view optimization (better clustering)

---

## Example: Corrected Frontmatter

### Before (Current - WRONG):
```yaml
---
id: 20251007_invoice_4384
title: Invoice #2025-1042
source: sample_invoice.md
doc_type: text
organizations:
- Acme Corporation
- Example Bank
topics:
- business/accounting
- business/finance
tags:
- doc/text
- org/acme-corporation
rag:
  quality_score: 1.0
  novelty_score: 0.6
  actionability_score: 0.6
  recency_score: 1.0
  signalness: 0.76
  do_index: true
  canonical: true
  enrichment_version: '2.0'
  enrichment_cost_usd: 5.0e-05
  provenance:
    sha256: 4384d5fbe8958df1
    sha256_full: 4384d5fbe8958df17708d467e1ebac24
---
```

### After (Blueprint-Compliant - CORRECT):
```yaml
---
id: 2025-10-07_invoice_acme-website-redesign_4384
source: invoice
path: data/obsidian/2025-10-07__invoice__acme-website-redesign__4384.md
created_at: 2025-10-07
ingested_at: 2025-10-07
doc_type: invoice
title: "Invoice #2025-1042 - Website Redesign"

# Controlled vocabulary
people: []
places: []
projects: [website-redesign-2025]
topics: [business/accounting, business/finance, business/invoicing]

# Entities (separate section)
entities:
  orgs: [Acme Corporation, Example Bank]
  dates: ["2025-10-07", "2025-11-06"]
  numbers: ["$10,472", "$8,800", "$1,672", "1234-5678-9012", "DE89370400440532013000"]

summary: >
  Invoice #2025-1042 for Website Redesign project with Acme Corporation.
  Services: UI Design (20h), Development (40h), Testing (10h).
  Total: $10,472 due November 6, 2025.

# Scores (top-level)
quality_score: 1.0
novelty_score: 0.6
actionability_score: 0.6
recency_score: 1.0
signalness: 0.76
do_index: true
canonical: true

# Provenance (top-level)
provenance:
  sha256: 4384d5fbe8958df1
  sha256_full: 4384d5fbe8958df17708d467e1ebac24fd9419889ba3d75017ca20b56ba7ce28
  original_filename: sample_invoice.md
  file_size_mb: 0.001
  ingestion_date: 2025-10-07T21:46:54

# Enrichment metadata
enrichment_version: v2.0
enrichment_cost_usd: 0.00005

# Tags (Obsidian-specific)
tags:
- doc/invoice
- topic/business-accounting
- topic/business-finance
- org/acme-corporation
- org/example-bank
- project/website-redesign-2025
- status/new
- quality/high
---
```

---

## Answers to User Questions

### Q1: "is this the right property type of rag in frontmatter? 1 string in brackets?"

**Answer**: ❌ NO. Our current structure is WRONG.

**Problem**: We nested scores under `rag:` section, but blueprint specifies top-level scores.

**Fix**: Move `quality_score`, `novelty_score`, `actionability_score`, `signalness`, `do_index` to top-level. Keep only Obsidian-specific helpers (if any) under a separate namespace.

### Q2: "shoulnt there be more linking, tag usage perhaps even graph?"

**Answer**: ✅ YES, ABSOLUTELY.

**Current gaps**:
1. No date entity links (`[[day:2025-10-07]]`)
2. No cross-document links (related docs in same project/topic/client)
3. No temporal navigation (prev/next document timeline)
4. No entity relationships (person → child, place → parent city)
5. Limited graph clustering (could use more semantic links)

**Fixes needed**:
- Date entity stubs + links
- Related documents section
- Entity relationship metadata
- Timeline navigation
- Better graph clustering via tags

### Q3: ".... and more info e.g. on persons, places......"

**Answer**: ✅ YES, entity metadata is too sparse.

**Current person stub**:
```yaml
type: person
name: Daniel
aliases: []
```

**Should be**:
```yaml
type: person
name: Daniel Teckentrup
aliases: [Daniel, DT, Dante]
role: Parent
relationships:
  - type: parent_of
    target: Pola
  - type: co_parent
    target: Mother
locations: [Köln Südstadt, Essen Rüttenscheid]
active_projects: [custody-2025, school-2026]
context: Primary parent in custody arrangement...
first_mentioned: 2024-01-15
last_mentioned: 2025-10-07
document_count: 150
primary_topics: [education, legal, family]
```

---

## Next Steps

**Immediate** (today):
1. Fix frontmatter structure (move scores to top-level)
2. Add `entities:` section (orgs, dates, numbers)
3. Extract dates and numbers from content

**Short-term** (this week):
4. Enhance entity stubs (person, place, org metadata)
5. Create date entity stubs
6. Add cross-document links
7. Improve graph visualization

**Medium-term** (next week):
8. Temporal navigation
9. Entity relationship tracking
10. Advanced Dataview dashboards

---

## Blueprint Compliance Score

**Before Fixes**: 60/100
- ✅ Markdown + YAML format
- ✅ Controlled vocabulary (topics, projects)
- ✅ Basic entity stubs
- ❌ Wrong frontmatter structure (nested scores)
- ❌ Missing entities section
- ❌ No date/number extraction
- ❌ Sparse entity metadata
- ❌ Limited graph linking

**After Fixes**: 95/100 (target)
- ✅ Blueprint-compliant frontmatter
- ✅ Complete entities section
- ✅ Date/number extraction
- ✅ Rich entity metadata
- ✅ Enhanced graph linking
- ✅ Temporal navigation
- ✅ Cross-document relationships

---

*Analysis completed: October 7, 2025*
*Blueprint: personal_rag_pipeline_full.md (2025-10-05)*
*Current status: Structural misalignment, requires refactoring*
