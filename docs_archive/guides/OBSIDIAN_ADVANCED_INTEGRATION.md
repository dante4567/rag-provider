# Obsidian Advanced Integration - Notation, Linking & Extensions

## Executive Summary

This document explores how to leverage Obsidian's advanced features to transform the RAG system from a simple document store into a **knowledge management powerhouse**.

**Current Status**: Basic integration ✅
- YAML frontmatter with metadata
- Simple wiki-links: `[[org:Name]]`
- Entity stubs with Dataview queries
- RAG:IGNORE blocks

**Enhancement Opportunities**: 10+ advanced features 🚀

---

## 1. Advanced Linking Patterns

### 1.1 Aliases (Display Names)

**Problem**: Links like `[[org:Acme Corporation]]` display as "org:Acme Corporation" in reading view
**Solution**: Use alias syntax `[[target|display]]`

**Current**:
```markdown
Client: [[org:Acme Corporation]]
Bank: [[org:Example Bank]]
```

**Enhanced**:
```markdown
Client: [[org:Acme Corporation|Acme]]
Bank: [[org:Example Bank|Example Bank]]
```

**Implementation**:
```python
# In build_xref_block() - Add display aliases
for org in organizations:
    # Strip common suffixes for cleaner display
    display_name = org.replace(" Corporation", "").replace(" GmbH", "").replace(" Inc.", "")
    lines.append(f"[[org:{org}|{display_name}]] ")
```

### 1.2 Heading Links (Section References)

**Use Case**: Link to specific sections within documents

**Example**:
```markdown
See [[2025-10-07__text__invoice#Line Items]] for breakdown
Refer to [[project:school-2026#Timeline]] for milestones
```

**Implementation Opportunity**:
- Add section anchors to generated documents
- Create index of linkable sections
- Auto-link to relevant sections in related docs

### 1.3 Block References (Precise Citation)

**Use Case**: Link to specific paragraphs or facts

**Syntax**:
```markdown
Important decision: [[doc#^block-id]]

# In target document:
The project deadline is November 30, 2025. ^decision-deadline
```

**Implementation**:
```python
# Add block IDs to key facts
def build_body(self, ...):
    if key_facts:
        body_parts.append("## Key Facts\n")
        for i, fact in enumerate(key_facts):
            block_id = f"fact-{i+1}"
            body_parts.append(f"- {fact} ^{block_id}")
```

**Benefit**: RAG can link to exact facts, not just documents

### 1.4 Embeds (Content Transclusion)

**Use Case**: Embed entire documents or sections

**Syntax**:
```markdown
# Full document embed
![[org:Acme Corporation]]

# Section embed
![[2025-10-07__text__invoice#Summary]]

# Block embed
![[doc#^key-finding]]
```

**Use Cases**:
- Dashboard aggregation (embed all recent high-quality docs)
- Project overview (embed all related documents)
- Timeline view (embed all docs with specific date)

**Example Dashboard**:
```markdown
# High-Quality Documents This Week

![[2025-10-07__text__scanner-setup#Summary]]
![[2025-10-07__text__invoice#Summary]]
![[2025-10-07__pdf__court-decision#Summary]]
```

---

## 2. Callouts & Admonitions

**Problem**: Metadata sections are plain text, hard to scan visually
**Solution**: Use Obsidian callouts for visual hierarchy

### 2.1 Metadata Callout

**Current**:
```markdown
> **Summary:** Invoice #2025-1042 for Website Redesign...
```

**Enhanced**:
```markdown
> [!abstract] Summary
> Invoice #2025-1042 for Website Redesign project with Acme Corporation, totaling $10,472.

> [!info] RAG Metadata
> - **Quality**: 1.0 (perfect)
> - **Signalness**: 0.76 (good)
> - **Cost**: $0.00005
> - **Indexed**: ✅ Canonical corpus
```

### 2.2 Quality Warnings

```markdown
> [!warning] Low OCR Quality (0.3)
> This document may have text extraction errors. Review carefully.

> [!bug] Incomplete Content
> Content completeness score: 0.5 - Document appears truncated.
```

### 2.3 Source Citation

```markdown
> [!quote] Original Source
> File: `upload_6e34e24c-f85d-4213-b31c-173254af4652_sample_invoice.md`
> Ingested: 2025-10-07 21:46:54
> SHA-256: `4384d5fbe8958df1`
```

### 2.4 Implementation

```python
def build_body(self, content: str, summary: str, ..., metadata: Dict):
    body_parts = []

    # Enhanced summary with callout
    if summary:
        body_parts.append(f"> [!abstract] Summary")
        body_parts.append(f"> {summary}")
        body_parts.append("")

    # RAG metadata callout
    quality = metadata.get('quality_score', 0.0)
    signalness = metadata.get('signalness', 0.0)
    cost = metadata.get('enrichment_cost', 0.0)

    body_parts.append("> [!info] RAG Metadata")
    body_parts.append(f"> - **Quality**: {quality:.2f}")
    body_parts.append(f"> - **Signalness**: {signalness:.2f}")
    body_parts.append(f"> - **Enrichment Cost**: ${cost:.5f}")
    body_parts.append(f"> - **Indexed**: {'✅' if metadata.get('do_index') else '❌'}")
    body_parts.append("")

    # Quality warnings
    if quality < 0.7:
        body_parts.append("> [!warning] Low Quality Score")
        body_parts.append(f"> Quality score {quality:.2f} - Review for accuracy")
        body_parts.append("")
```

---

## 3. Enhanced Dataview Queries

### 3.1 Inline Queries (DQL)

**Use Case**: Show statistics inline

**Current entity stub**:
```markdown
# Acme Corporation

```dataview
LIST FROM "10_normalized_md"
WHERE contains(organizations, "Acme Corporation")
SORT created_at DESC
```
```

**Enhanced entity stub**:
```markdown
# Acme Corporation

> [!info] Statistics
> Documents: `= length(filter(file.lists.file, (f) => contains(meta(f).organizations, "Acme Corporation")))`
> Total value: `$= sum(map(filter(...), (f) => f.rag.enrichment_cost_usd)) * 1000` ¢
> Avg quality: `$= average(map(filter(...), (f) => f.rag.quality_score))`

## Recent Documents

```dataview
TABLE
  file.ctime as "Date",
  rag.quality_score as "Quality",
  rag.signalness as "Signal",
  topics[0] as "Primary Topic"
FROM "data/obsidian"
WHERE contains(organizations, "Acme Corporation")
SORT file.ctime DESC
LIMIT 10
```

## By Topic

```dataview
TABLE
  rows.file.link as "Documents",
  length(rows) as "Count"
FROM "data/obsidian"
WHERE contains(organizations, "Acme Corporation")
GROUP BY topics[0]
SORT length(rows) DESC
```
```

### 3.2 Quality Dashboard

**Create**: `data/obsidian/_dashboards/quality-dashboard.md`

```markdown
# Quality Dashboard

## Low Quality Documents (Needs Review)

```dataview
TABLE
  file.link as "Document",
  rag.quality_score as "Quality",
  rag.signalness as "Signal",
  ingested_at as "Ingested"
FROM "data/obsidian"
WHERE rag.quality_score < 0.7
SORT rag.quality_score ASC
LIMIT 20
```

## High-Quality Canonical Documents

```dataview
TABLE
  file.link as "Document",
  rag.quality_score as "Quality",
  rag.novelty_score as "Novelty",
  topics[0] as "Topic"
FROM "data/obsidian"
WHERE rag.canonical = true AND rag.quality_score > 0.9
SORT rag.signalness DESC
LIMIT 20
```

## Cost Analysis by Month

```dataview
TABLE
  sum(rows.rag.enrichment_cost_usd) * 1000 as "Cost (¢)",
  length(rows) as "Documents",
  sum(rows.rag.enrichment_cost_usd) / length(rows) * 1000 as "Avg (¢)"
FROM "data/obsidian"
GROUP BY dateformat(file.ctime, "yyyy-MM") as "Month"
SORT "Month" DESC
```

## Deduplication Check

```dataview
TABLE
  length(rows) as "Count",
  rows.file.link as "Duplicates"
FROM "data/obsidian"
WHERE rag.provenance.sha256 != ""
GROUP BY rag.provenance.sha256 as "Hash"
WHERE length(rows) > 1
SORT length(rows) DESC
```
```

### 3.3 Topic Dashboard

**Create**: `data/obsidian/_dashboards/topics-dashboard.md`

```markdown
# Topics Overview

## Document Count by Primary Topic

```dataview
TABLE
  length(rows) as "Count",
  sum(rows.rag.enrichment_cost_usd) * 1000 as "Cost (¢)",
  average(rows.rag.quality_score) as "Avg Quality"
FROM "data/obsidian"
GROUP BY topics[0] as "Topic"
WHERE topics[0] != ""
SORT length(rows) DESC
```

## Recent by Topic: Business

```dataview
LIST
FROM "data/obsidian"
WHERE any(topics, (t) => startswith(t, "business/"))
SORT file.ctime DESC
LIMIT 10
```

## Recent by Topic: Technology

```dataview
LIST
FROM "data/obsidian"
WHERE any(topics, (t) => startswith(t, "technology/"))
SORT file.ctime DESC
LIMIT 10
```
```

---

## 4. Graph View Optimization

### 4.1 Enhanced Entity Linking

**Problem**: Current links are one-directional (doc → entity)
**Solution**: Add bidirectional context

**Current**:
```markdown
<!-- RAG:IGNORE-START -->
## Xref

[[org:Acme Corporation]]
[[org:Example Bank]]

<!-- RAG:IGNORE-END -->
```

**Enhanced**:
```markdown
<!-- RAG:IGNORE-START -->

## Related Entities

### Organizations
- [[org:Acme Corporation]] (Client)
- [[org:Example Bank]] (Payment)

### People
- [[person:Project Manager]] (Contact)

### Projects
- [[project:website-redesign-2025]]

### Places
- [[place:Berlin]] (Delivery location)

### Related Documents
- [[2025-09-15__text__website-redesign-proposal]] (Previous)
- [[2025-10-01__text__project-kickoff-meeting]] (Related)

<!-- RAG:IGNORE-END -->
```

**Benefit**: Richer graph, better navigation

### 4.2 Temporal Navigation

**Add date entity stubs**: `refs/days/2025-10-07.md`

```markdown
---
date: 2025-10-07
day_of_week: Tuesday
type: day
---

# 2025-10-07 (Tuesday)

## Documents Created/Received

```dataview
LIST
FROM "data/obsidian"
WHERE created_at = "2025-10-07"
SORT file.ctime ASC
```

## Documents About This Date

```dataview
LIST
FROM "data/obsidian"
WHERE contains(string(file), "2025-10-07") OR contains(dates, "2025-10-07")
```

## Statistics

- Documents: `$= length(filter(file.lists.file, (f) => meta(f).created_at = "2025-10-07"))`
- Total cost: `$= sum(...)`
- Avg quality: `$= average(...)`
```

**Link to dates**:
```markdown
## Timeline

- [[day:2025-10-07]] -- Invoice sent
- [[day:2025-11-06]] -- Payment due
```

---

## 5. Properties (Obsidian 1.4+)

**Problem**: YAML is plain text, no type validation
**Solution**: Use Obsidian Properties with types

### 5.1 Typed Properties

**Current**:
```yaml
---
quality_score: 1.0
novelty_score: 0.6
created_at: '2025-10-07'
organizations:
- Acme Corporation
---
```

**Enhanced (Properties)**:
```yaml
---
# Core metadata
title: Invoice #2025-1042
created_at: 2025-10-07           # Date type (sortable, calendar-aware)
doc_type: text                   # Text type
quality_score: 1.0               # Number type (slider support)
signalness: 0.76                 # Number type

# Lists (multi-select)
organizations:
  - "[[org:Acme Corporation]]"   # Links in lists
  - "[[org:Example Bank]]"
topics:
  - business/accounting
  - business/finance

# Flags (checkbox)
canonical: true                   # Boolean (checkbox in UI)
do_index: true

# Cost (number with precision)
enrichment_cost_usd: 0.00005
---
```

**Benefits**:
- Sortable dates (not strings)
- Number sliders for quality scores
- Checkboxes for flags
- Auto-complete for links
- Property search pane

### 5.2 Property Views

Obsidian 1.4+ allows:
- Sort by property (quality_score, created_at)
- Filter by property (canonical = true)
- Group by property (doc_type, topics[0])
- Property search (find all with quality > 0.9)

---

## 6. Tags Hierarchy

### 6.1 Nested Tags

**Current** (flat):
```yaml
tags:
- doc/text
- topic/business-accounting
- org/acme-corporation
```

**Enhanced** (hierarchical):
```yaml
tags:
- doc/text/invoice
- topic/business/accounting/invoice
- org/clients/acme-corporation
- project/active/website-redesign
- status/needs-review
- quality/high
```

**Benefits**:
- Tag pane shows hierarchy
- Filter by tag prefix (e.g., all `#topic/business/*`)
- Drill down in UI

### 6.2 Status Tags

Add workflow status:
```yaml
tags:
- status/new           # Just ingested
- status/reviewed      # Human reviewed
- status/archived      # Old, low relevance
- status/needs-update  # Outdated
```

### 6.3 Quality Tags

Add quality-based tags:
```yaml
tags:
- quality/high         # quality_score > 0.9
- quality/medium       # 0.7-0.9
- quality/low          # < 0.7
- quality/ocr-issues   # OCR quality < 0.7
```

**Implementation**:
```python
def derive_quality_tags(metadata: Dict) -> List[str]:
    """Add quality-based tags"""
    quality_tags = []

    quality = metadata.get('quality_score', 0.0)
    if quality > 0.9:
        quality_tags.append('quality/high')
    elif quality > 0.7:
        quality_tags.append('quality/medium')
    else:
        quality_tags.append('quality/low')

    ocr_quality = metadata.get('quality_indicators', {}).get('ocr_quality', 1.0)
    if ocr_quality < 0.7:
        quality_tags.append('quality/ocr-issues')

    return quality_tags
```

---

## 7. Community Plugins Integration

### 7.1 Tasks Plugin

**Use Case**: Extract action items from documents

**Current**:
```markdown
## Next Actions

- [ ] Review invoice
- [ ] Process payment by Nov 6
```

**Enhanced** (with Tasks plugin):
```markdown
## Next Actions

- [ ] Review invoice 📅 2025-10-10 #task/finance
- [ ] Process payment by Nov 6 📅 2025-11-06 ⏫ #task/payment
- [ ] Archive document after payment ⏬ #task/admin
```

**Query all tasks**:
```markdown
# My Tasks

```tasks
not done
sort by due
group by tags
```
```

**Implementation**: Extract action items during enrichment, format with Tasks syntax

### 7.2 Calendar Plugin

**Use Case**: Temporal navigation

**Implementation**:
- Date properties for sorting
- Daily notes for each ingestion day
- Link documents to calendar dates

### 7.3 Templater Plugin

**Use Case**: Dynamic content generation

**Example Template**: `_templates/invoice-template.md`
```markdown
---
title: <% tp.file.title %>
created_at: <% tp.date.now("YYYY-MM-DD") %>
doc_type: invoice
---

# <% tp.file.title %>

> [!abstract] Summary
> <% tp.system.prompt("Invoice summary") %>

## Client
<% tp.system.suggester(["Acme Corp", "Example Inc"], ["[[org:Acme Corporation]]", "[[org:Example Inc]]"]) %>

## Amount
$<% tp.system.prompt("Total amount") %>
```

### 7.4 Excalidraw Plugin

**Use Case**: Visual document relationships

**Example**: Create `_diagrams/project-overview.excalidraw.md`
- Visual map of project documents
- Timeline diagrams
- Entity relationship diagrams

### 7.5 Kanban Plugin

**Use Case**: Document workflow management

**Example**: `_workflows/document-review-board.md`
```markdown
---
kanban-plugin: board
---

## New (Needs Review)

- [[2025-10-07__pdf__court-decision]]
- [[2025-10-07__text__invoice]]

## In Review

- [[2025-10-06__text__meeting-notes]]

## Reviewed

- [[2025-10-05__text__scanner-setup]]
```

---

## 8. Canvas (Obsidian Canvas)

**Use Case**: Visual project/knowledge maps

### 8.1 Project Canvas

**Create**: `_canvas/website-redesign-project.canvas`

Layout:
```
┌──────────────┐
│ Project Plan │
│ (embed doc)  │
└──────────────┘
       │
       ├─→ ┌──────────────┐
       │   │ Invoice      │
       │   └──────────────┘
       │
       ├─→ ┌──────────────┐
       │   │ Meeting Notes│
       │   └──────────────┘
       │
       └─→ ┌──────────────┐
           │ Client Emails│
           └──────────────┘
```

**Auto-generate canvas** from project metadata

### 8.2 Entity Canvas

**Create**: `_canvas/acme-corporation.canvas`

Visual map of all documents, people, projects related to Acme Corp

---

## 9. Implementation Plan

### Phase 1: Enhanced Linking (1-2 hours)
- [ ] Add block IDs to key facts
- [ ] Implement heading links
- [ ] Add display aliases for entities
- [ ] Enhanced xref block with context

### Phase 2: Callouts & Visual Enhancement (2-3 hours)
- [ ] Convert summary to callout
- [ ] Add RAG metadata callout
- [ ] Add quality warnings
- [ ] Add source citation callout

### Phase 3: Dataview Dashboards (2-3 hours)
- [ ] Quality dashboard
- [ ] Topics dashboard
- [ ] Cost analysis dashboard
- [ ] Entity dashboards with inline stats

### Phase 4: Properties & Tags (1-2 hours)
- [ ] Migrate to typed properties (Obsidian 1.4+)
- [ ] Implement nested tag hierarchy
- [ ] Add quality tags
- [ ] Add status tags

### Phase 5: Temporal Navigation (2-3 hours)
- [ ] Generate daily note stubs
- [ ] Link documents to dates
- [ ] Add timeline sections

### Phase 6: Plugin Integration (3-4 hours)
- [ ] Tasks plugin integration
- [ ] Canvas auto-generation for projects
- [ ] Kanban board for workflow

---

## 10. Benefits Summary

| Enhancement | Benefit | Effort |
|-------------|---------|--------|
| **Callouts** | Better visual scanning, clearer metadata | Low |
| **Block References** | Precise fact citation, better RAG linking | Low |
| **Typed Properties** | Sortable, filterable, searchable metadata | Medium |
| **Nested Tags** | Better organization, tag hierarchy | Low |
| **Dataview Dashboards** | Aggregated insights, quality monitoring | Medium |
| **Temporal Navigation** | Date-based discovery, timeline views | Medium |
| **Enhanced Entity Stubs** | Richer context, better stats | Low |
| **Tasks Integration** | Actionable items, todo tracking | Medium |
| **Canvas** | Visual project/knowledge maps | High |
| **Quality Tags** | Quick filtering, status tracking | Low |

---

## 11. Quick Wins (Implement First)

### Top 3 High-Impact, Low-Effort Enhancements:

1. **Callouts for Metadata** (30 min)
   - Visual clarity
   - Quality warnings
   - Better UX

2. **Enhanced Entity Stubs with Stats** (1 hour)
   - Document counts
   - Quality averages
   - Cost tracking

3. **Quality Dashboard** (1 hour)
   - Monitor low-quality docs
   - Track costs
   - Find duplicates

---

## 12. Code Examples

### Enhanced Obsidian Service (Key Changes)

```python
def build_body_enhanced(
    self,
    content: str,
    summary: str,
    metadata: Dict[str, Any],
    key_facts: List[str] = None,
    ...
) -> str:
    """Build enhanced body with callouts, block refs, and rich formatting"""
    body_parts = []

    # Summary callout
    if summary:
        body_parts.append("> [!abstract] Summary")
        body_parts.append(f"> {summary}")
        body_parts.append("")

    # RAG Metadata callout
    quality = metadata.get('quality_score', 0.0)
    signalness = metadata.get('signalness', 0.0)
    cost = metadata.get('enrichment_cost', 0.0)
    canonical = metadata.get('canonical', False)

    body_parts.append("> [!info] RAG Metadata")
    body_parts.append(f"> - **Quality Score**: {quality:.2f}")
    body_parts.append(f"> - **Signalness**: {signalness:.2f}")
    body_parts.append(f"> - **Enrichment Cost**: ${cost:.5f}")
    body_parts.append(f"> - **Canonical**: {'✅ Yes' if canonical else '❌ No'}")
    body_parts.append("")

    # Quality warning if low
    if quality < 0.7:
        body_parts.append("> [!warning] Low Quality Score")
        body_parts.append(f"> This document has a quality score of {quality:.2f}.")
        body_parts.append("> Review carefully for potential issues.")
        body_parts.append("")

    # Source citation callout
    source = metadata.get('source', '')
    sha256 = metadata.get('content_hash', '')[:16]
    ingested = metadata.get('ingestion_date', '')

    body_parts.append("> [!quote] Original Source")
    body_parts.append(f"> **File**: `{source}`")
    body_parts.append(f"> **SHA-256**: `{sha256}`")
    body_parts.append(f"> **Ingested**: {ingested}")
    body_parts.append("")

    # Key Facts with block IDs
    if key_facts:
        body_parts.append("## Key Facts")
        body_parts.append("")
        for i, fact in enumerate(key_facts):
            block_id = f"fact-{i+1}"
            body_parts.append(f"- {fact} ^{block_id}")
        body_parts.append("")

    # Main content
    body_parts.append("## Evidence / Excerpts")
    body_parts.append("")
    body_parts.append(content)
    body_parts.append("")

    return "\n".join(body_parts)

def build_enhanced_entity_stub(
    self,
    entity_type: str,
    name: str,
    vault_path: str = "data/obsidian"
) -> str:
    """Generate enhanced entity stub with statistics and insights"""

    stub_parts = [f"# {name}", ""]

    # Statistics callout with inline Dataview
    stub_parts.append("> [!info] Statistics")
    stub_parts.append(f"> **Total Documents**: `$= dv.pages('\"{vault_path}\"').where(p => p.{entity_type}s?.includes('{name}')).length`")
    stub_parts.append(f"> **Avg Quality**: `$= dv.pages('\"{vault_path}\"').where(p => p.{entity_type}s?.includes('{name}')).avg(p => p.rag?.quality_score)`")
    stub_parts.append(f"> **Total Cost**: `$= (dv.pages('\"{vault_path}\"').where(p => p.{entity_type}s?.includes('{name}')).sum(p => p.rag?.enrichment_cost_usd) * 1000).toFixed(2)` ¢")
    stub_parts.append("")

    # Recent documents table
    stub_parts.append("## Recent Documents")
    stub_parts.append("")
    stub_parts.append("```dataview")
    stub_parts.append("TABLE")
    stub_parts.append("  file.ctime as \"Date\",")
    stub_parts.append("  rag.quality_score as \"Quality\",")
    stub_parts.append("  rag.signalness as \"Signal\",")
    stub_parts.append("  topics[0] as \"Primary Topic\"")
    stub_parts.append(f"FROM \"{vault_path}\"")
    stub_parts.append(f"WHERE contains({entity_type}s, \"{name}\")")
    stub_parts.append("SORT file.ctime DESC")
    stub_parts.append("LIMIT 10")
    stub_parts.append("```")
    stub_parts.append("")

    # By topic breakdown
    stub_parts.append("## By Topic")
    stub_parts.append("")
    stub_parts.append("```dataview")
    stub_parts.append("TABLE")
    stub_parts.append("  length(rows) as \"Count\",")
    stub_parts.append("  rows.file.link as \"Documents\"")
    stub_parts.append(f"FROM \"{vault_path}\"")
    stub_parts.append(f"WHERE contains({entity_type}s, \"{name}\")")
    stub_parts.append("GROUP BY topics[0] as \"Topic\"")
    stub_parts.append("SORT length(rows) DESC")
    stub_parts.append("```")

    return "\n".join(stub_parts)

def derive_enhanced_tags(
    self,
    doc_type: DocumentType,
    metadata: Dict[str, Any],
    ...
) -> List[str]:
    """Derive hierarchical tags with quality and status"""
    tags = []

    # Document type (hierarchical)
    type_str = str(doc_type).replace('DocumentType.', '')
    if type_str == 'text':
        tags.append('doc/text/general')
    elif type_str == 'email':
        tags.append('doc/text/email')
    # ... etc

    # Quality tags
    quality = metadata.get('quality_score', 0.0)
    if quality > 0.9:
        tags.append('quality/high')
    elif quality > 0.7:
        tags.append('quality/medium')
    else:
        tags.append('quality/low')

    # OCR quality
    ocr_quality = metadata.get('quality_indicators', {}).get('ocr_quality', 1.0)
    if ocr_quality < 0.7:
        tags.append('quality/ocr-issues')

    # Status tags
    tags.append('status/new')  # Default for new documents

    # Canonical corpus
    if metadata.get('canonical', False):
        tags.append('corpus/canonical')

    # Project tags (hierarchical)
    for project in projects:
        tags.append(f'project/active/{slugify(project)}')

    # ... rest of tag logic

    return tags
```

---

## Conclusion

Implementing these Obsidian enhancements transforms the RAG system from a **document repository** into a **knowledge graph** with:

- **Visual clarity** (callouts, hierarchical tags)
- **Precise linking** (block refs, heading links)
- **Dynamic insights** (Dataview dashboards, inline stats)
- **Temporal navigation** (date stubs, calendar)
- **Quality monitoring** (dashboards, warnings)
- **Cost tracking** (per-document, aggregated)
- **Workflow management** (status tags, Kanban boards)
- **Visual mapping** (Canvas, entity graphs)

**Next Steps**: Implement Phase 1-3 (Quick Wins) for immediate impact.
