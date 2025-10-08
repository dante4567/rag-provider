# Enhanced Entity Stubs - Obsidian-First Approach

## Philosophy

**Obsidian is the source of truth**. vCards and iCal files are just optional export formats.

### Current Flow (Just Implemented)
```
Document → Extract People/Dates → Create vCards/iCal → Sync to Apps
```

### Better Flow (Obsidian-First)
```
Document → Extract People/Dates → Create Rich Entity Stubs in Obsidian
                                 ↓
                                 Optional: Export to vCard/iCal (if actionable)
```

---

## Enhanced Entity Stub Format

### Person Stub (refs/persons/person-name.md)

```markdown
---
aliases: []
name: Rechtsanwalt Dr. Schmidt
type: person
role: Lawyer
organization: Law Firm XYZ
first_seen: 2025-10-08
last_seen: 2025-10-08
mentions: 3
actionable: true          # LLM-determined
vcard_exported: false     # Has vCard been created?
vcard_path: null          # Path to vCard file if exported

# Optional contact details (if mentioned in docs)
email: null
phone: null
address: null

# Metadata
tags:
  - person
  - legal
  - lawyer
---

# Rechtsanwalt Dr. Schmidt

> **Role**: Lawyer
> **Organization**: Law Firm XYZ
> **Actionable**: Yes (real contact, not historical figure)

## Mentioned In

\```dataview
TABLE
  file.name as "Document",
  topics as "Topics",
  created_at as "Date"
FROM ""
WHERE contains(people, "Rechtsanwalt Dr. Schmidt")
SORT created_at DESC
\```

## Context

\```dataview
LIST
  regexreplace(file.link, ".*", "$0: " + join(filter(split(file.content, "\n"), (x) => contains(x, "Schmidt")), " | "))
FROM ""
WHERE contains(people, "Rechtsanwalt Dr. Schmidt")
LIMIT 5
\```

## Actions

- [ ] Create vCard export → `[[vcard:rechtsanwalt-dr-schmidt.vcf]]`
- [ ] Add to contacts app
- [ ] Follow up on case

## Notes

<!-- Add manual notes about this person here -->

```

### Date/Event Stub (refs/days/2025-11-15.md)

```markdown
---
aliases: []
date: 2025-11-15
type: day
events:
  - title: "School Enrollment Deadline"
    source: "einschulung-2026.md"
    topics: ["education/school/enrollment"]
    actionable: true
    event_type: deadline
    ical_exported: false
    ical_path: null

tags:
  - day
  - deadline
  - education
---

# 2025-11-15

## Events on This Day

### School Enrollment Deadline
- **Type**: Deadline
- **Source**: [[einschulung-2026]]
- **Topics**: education/school/enrollment
- **Actionable**: Yes
- **Reminder**: 7 days before

**Context from document**:
> Registration deadline November 15, 2025. Must submit birth certificate and proof of residence.

## All Documents Mentioning This Date

\```dataview
TABLE
  file.name as "Document",
  topics as "Topics",
  entities.dates as "Other Dates"
FROM ""
WHERE contains(entities.dates, "2025-11-15")
SORT created_at DESC
\```

## Actions

- [ ] Create calendar event → `[[event:2025-11-15-school-enrollment.ics]]`
- [ ] Set reminder (7 days before)
- [ ] Gather required documents

## Notes

<!-- Add manual notes about this date here -->

```

---

## Implementation: Make vCard/iCal Optional

### Configuration (.env)

```bash
# Entity export settings
CREATE_ENTITY_STUBS=true           # Always create Obsidian stubs (default: true)
EXPORT_VCARDS=false                # Only export vCards if actionable (default: false)
EXPORT_ICALENDARS=false            # Only export iCal if actionable (default: false)
USE_ACTIONABILITY_FILTER=true     # Use LLM to filter (default: true)

# Export triggers
EXPORT_VCARDS_AUTO=false           # Auto-export during ingestion
EXPORT_VCARDS_MANUAL=true          # Only export when requested via API
```

### Modified Integration Flow

```python
# In app.py, after enrichment:

# 1. ALWAYS create Obsidian entity stubs (cheap, useful for graph)
if generate_obsidian:
    self.obsidian_service.create_person_stubs(people, metadata)
    self.obsidian_service.create_date_stubs(dates, metadata)

# 2. OPTIONALLY export to vCards/iCal (expensive, only if actionable)
if settings.EXPORT_VCARDS_AUTO:
    # Filter for actionable people
    if settings.USE_ACTIONABILITY_FILTER:
        actionable_people = await actionability_filter.filter_people(
            people, title, topics, content
        )
    else:
        actionable_people = people

    # Export only actionable people
    if actionable_people:
        vcards = contact_service.create_vcards(actionable_people, metadata)
        # Update stubs with vcard_exported: true

# 3. Same for calendar events
if settings.EXPORT_ICALENDARS_AUTO:
    actionable_dates = await actionability_filter.filter_dates(
        dates, title, topics, content
    )
    if actionable_dates:
        events = calendar_service.create_events(actionable_dates, metadata)
```

---

## API Endpoints

### Export Individual Entity

```bash
# Export specific person to vCard
POST /entities/person/{person-slug}/export/vcard

# Export specific date to iCal
POST /entities/date/{date}/export/ical
```

### Batch Export

```bash
# Export all actionable people to vCards
POST /entities/people/export/vcards
{
  "filter": "actionable",  # or "all"
  "dry_run": false
}

# Export all actionable dates to iCal
POST /entities/dates/export/icalendars
{
  "filter": "actionable",
  "date_range": {
    "start": "2025-10-01",
    "end": "2026-12-31"
  }
}
```

---

## User Workflow

### Obsidian-Only (No External Apps)

1. Ingest document
2. View extracted people/dates in Obsidian entity stubs
3. Use Dataview to query/link entities
4. Add manual notes to entity stubs
5. No external exports needed

### Obsidian + Calendar/Contacts Sync

1. Ingest document
2. Review entity stubs in Obsidian
3. Manually export actionable entities:
   ```bash
   curl -X POST http://localhost:8001/entities/person/lawyer-schmidt/export/vcard
   curl -X POST http://localhost:8001/entities/date/2025-11-15/export/ical
   ```
4. Sync exported files to calendar/contacts apps

### Automated Export (Power User)

1. Enable auto-export in `.env`:
   ```bash
   EXPORT_VCARDS_AUTO=true
   EXPORT_ICALENDARS_AUTO=true
   USE_ACTIONABILITY_FILTER=true
   ```
2. Ingest document → auto-creates stubs + exports actionable entities
3. Sync exports to apps via CardDAV/CalDAV

---

## Benefits of This Approach

**1. Obsidian-First**
- Entity stubs are always created (cheap, useful)
- Graph visualization works immediately
- Dataview queries work across all entities

**2. Flexible Export**
- vCards/iCal only created when needed
- Manual control over what gets exported
- No clutter in calendar/contacts apps

**3. Actionability Filtering**
- LLM determines what's worth exporting
- Avoids creating calendar events for historical dates
- Avoids creating contacts for book authors, etc.

**4. Source of Truth**
- Obsidian stubs contain full metadata
- Manual notes can be added
- Export can be re-done anytime

**5. Performance**
- Don't create vCards/iCal for every mention
- Reduce sync overhead
- Faster ingestion

---

## Migration Path

### Phase 1: Current Implementation ✅
- Always create vCards/iCal during ingestion
- No filtering

### Phase 2: Add Actionability Filter (Next)
- Add LLM-based filtering
- Still auto-export, but only actionable entities

### Phase 3: Make Export Optional (Recommended)
- Create stubs always
- Export only when requested
- Add API endpoints for manual export

### Phase 4: Enhanced Stubs (Future)
- Richer metadata in stubs
- Better Dataview queries
- Action items and notes

---

## Example: School Enrollment Document

**Input**: Document about school enrollment deadline November 15, 2025

**Current Approach**:
- Creates: `data/calendar/2025-11-15_school-enrollment.ics`
- Syncs to calendar immediately

**Better Approach**:
1. **Always**: Creates `refs/days/2025-11-15.md` with:
   - Event metadata
   - Dataview query showing all docs mentioning this date
   - Action checklist
   - Notes section
2. **Optional**: User reviews stub, decides "yes, this is actionable"
3. **Manual Export**: `POST /entities/date/2025-11-15/export/ical`
4. **Sync**: iCal file created, synced to calendar

**User Control**: Full visibility and control over what becomes a calendar event
