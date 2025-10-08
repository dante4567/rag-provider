# Quick Start: Entity Exports (People & Dates)

## Overview

The RAG Provider extracts people and dates from documents and can handle them two ways:

### Approach 1: Obsidian-Only (Recommended)
**What**: Create rich entity stubs in Obsidian, use graph/dataview, optionally export
**When**: You want full control, use Obsidian as your main tool
**Files**: Only Obsidian MD files in `refs/people/`, `refs/days/`

### Approach 2: Auto-Export (Just Implemented)
**What**: Automatically create vCards (.vcf) and iCal (.ics) files, sync to calendar/contacts apps
**When**: You want automatic calendar/contacts sync
**Files**: Obsidian MD + vCards in `data/contacts/` + iCal in `data/calendar/`

---

## Current Configuration (Auto-Export)

**What's happening now**:
```python
# When you ingest a document with generate_obsidian=true:
Document → Extract People/Dates → Create Obsidian Stubs + vCards + iCal
```

**Files created**:
- `data/obsidian/refs/persons/person-name.md` (Obsidian stub)
- `data/contacts/person-name.vcf` (vCard for contacts app)
- `data/calendar/2025-11-15_event.ics` (iCal for calendar app)

---

## Quick Test

### 1. Drop a file in the input directory

```bash
# Copy a document to the input folder
cp ~/Documents/your-document.pdf data/input/

# Wait a few seconds, check logs
docker-compose logs -f rag-service
```

### 2. Check what was created

```bash
# Obsidian stubs (always created)
ls data/obsidian/refs/persons/
ls data/obsidian/refs/days/

# vCards (created if people extracted)
ls data/contacts/*.vcf

# Calendar events (created if dates extracted)
ls data/calendar/*.ics
```

### 3. View in Obsidian

1. Open Obsidian vault: `data/obsidian/`
2. Check Graph View → see people/places linked
3. Open a person stub → see Dataview query with all mentions

---

## Switching to Obsidian-Only Approach

### Why?

**Problem with auto-export**:
- Not every person should be a contact (book authors, historical figures)
- Not every date should be a calendar event (historical dates, blog post dates)
- Creates clutter in contacts/calendar apps

**Solution: LLM-filtered optional export**:
1. **Always** create Obsidian entity stubs (useful for graph/linking)
2. **Filter** people/dates with LLM (is this actionable?)
3. **Optionally** export only actionable entities to vCards/iCal

### Configuration (Future - Not Implemented Yet)

Add to `.env`:
```bash
# Entity export settings
CREATE_ENTITY_STUBS=true           # Always create Obsidian stubs
EXPORT_VCARDS_AUTO=false           # Don't auto-export vCards
EXPORT_ICALENDARS_AUTO=false       # Don't auto-export iCal
USE_ACTIONABILITY_FILTER=true     # Use LLM to filter if exporting
```

### Manual Export (Future API)

```bash
# Review entity stubs in Obsidian first
# Then manually export specific entities:

# Export specific person to vCard
curl -X POST http://localhost:8001/entities/person/lawyer-schmidt/export/vcard

# Export specific date to iCal
curl -X POST http://localhost:8001/entities/date/2025-11-15/export/ical

# Batch export all actionable people
curl -X POST http://localhost:8001/entities/people/export/vcards \
  -d '{"filter": "actionable"}'
```

---

## Current Workflow (Auto-Export)

**Step 1: Ingest**
```bash
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@document.pdf" \
  -F "generate_obsidian=true"
```

**Step 2: Check Created Files**
```bash
# Obsidian stubs (always)
ls data/obsidian/refs/persons/
ls data/obsidian/refs/days/

# vCards (if people extracted)
ls data/contacts/

# iCal (if dates extracted)
ls data/calendar/
```

**Step 3: Sync to Apps** (see `CARDDAV_CALDAV_SYNC_GUIDE.md`)
```bash
# Export all contacts to single file
# (Future API endpoint - not implemented yet)
# For now, manually copy .vcf files to contacts app
```

---

## Recommended Workflow (Obsidian-First)

**Step 1: Ingest**
```bash
# Drop file in input directory
cp document.pdf data/input/
```

**Step 2: Review in Obsidian**
1. Open Obsidian vault: `data/obsidian/`
2. Check `refs/persons/` and `refs/days/` for extracted entities
3. Review Dataview queries to see all mentions
4. Add manual notes to entity stubs

**Step 3: Optionally Export**
- Only export entities you actually need in contacts/calendar apps
- Use future API endpoints for selective export
- Or: Enable auto-export with LLM filtering

---

## What Works Right Now ✅

**Auto-Created**:
- ✅ Obsidian entity stubs (`refs/persons/`, `refs/days/`)
- ✅ vCard files (`data/contacts/*.vcf`)
- ✅ iCal files (`data/calendar/*.ics`)

**Not Yet Implemented** (coming soon):
- ⏳ LLM actionability filter
- ⏳ Optional export (stubs only, no vCards/iCal)
- ⏳ API endpoints for manual export
- ⏳ Batch export with filtering

---

## FAQ

**Q: Do I need vCards/iCal if I use Obsidian?**
No! Obsidian entity stubs are sufficient for most use cases. vCards/iCal are only useful if you want to sync with external calendar/contacts apps.

**Q: Can I disable vCard/iCal creation?**
Not yet (configuration coming soon). For now, they're auto-created but you can ignore them.

**Q: Where do I find extracted entities?**
- Obsidian stubs: `data/obsidian/refs/persons/`, `refs/days/`
- vCards: `data/contacts/`
- iCal: `data/calendar/`

**Q: How do I import vCards/iCal to my apps?**
See `CARDDAV_CALDAV_SYNC_GUIDE.md` for detailed instructions.

**Q: Can I manually edit entity stubs?**
Yes! Edit files in `data/obsidian/refs/` to add notes, fix names, etc.

---

## Next Steps

1. **Try it**: Drop a document in `data/input/` and see what gets created
2. **Review stubs**: Open Obsidian vault and explore entity stubs
3. **Decide approach**:
   - Obsidian-only → ignore vCards/iCal for now
   - Full sync → set up CardDAV/CalDAV (see sync guide)
4. **Give feedback**: What entities are actionable? Which approach do you prefer?

See also:
- `data/input/README.md` - How to use input directory
- `CARDDAV_CALDAV_SYNC_GUIDE.md` - How to sync vCards/iCal
- `docs/ENHANCED_ENTITY_STUBS.md` - Future enhanced approach
