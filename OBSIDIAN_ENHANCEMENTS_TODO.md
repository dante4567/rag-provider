# 📝 Obsidian Export Enhancements - TODO List

**Based on**: Scale test with 100 PDFs
**User Feedback**: "output is without formatting" + "backlinks can be added also, its great overall"

---

## 🎯 Priority 1: Formatting Improvements (2 hours)

### 1.1 Content Formatting ✅ CRITICAL
**Issue**: Content appears as raw text without markdown formatting
**Example**:
```
Current: Montag 06.10. Dienstag 07.10 Mittwoch 08.10
Better:  - Montag 06.10
         - Dienstag 07.10
         - Mittwoch 08.10
```

**Fix**:
- Detect lists (dates, bullet points, numbered items)
- Convert to markdown lists
- Preserve paragraph structure
- Add proper headings

**Location**: `src/services/obsidian_service.py:190-197`

### 1.2 Clean Up Type Field
**Issue**: Shows `DocumentType.pdf` instead of clean value
**Example**:
```
Current: type: DocumentType.pdf
Better:  type: literature
```

**Fix**: Strip enum prefix, map to clean values

### 1.3 Remove Duplicate Tags
**Issue**: Tags can appear multiple times (e.g., `#literature` twice)
**Fix**: Deduplicate tag list before export

### 1.4 Clean Source Filename
**Issue**: Shows temp upload path
**Example**:
```
Current: upload_e6a7816e-dfa5-4a03-b1d5-70c26e247171_Schulanmeldung_QR_Codes_.pdf
Better:  Schulanmeldung_QR_Codes_.pdf
```

**Fix**: Extract original filename from temp path

---

## 🎯 Priority 2: Backlinks & Related Notes (3 hours)

### 2.1 Add Related Notes Section
**Feature**: Suggest related documents based on:
- Similar tags (tag overlap > 50%)
- Same domain
- Entity mentions (shared people/organizations)

**Example**:
```markdown
## Related Notes

- [[School Calendar 2024]]
- [[Parent-Teacher Meeting Dates]]
- [[QR Code System Overview]]
```

**Implementation**:
- Query ChromaDB for similar documents
- Use tag overlap as primary signal
- Limit to top 5 most related

### 2.2 Entity Cross-References
**Feature**: Link to other notes mentioning same entities

**Example**:
```markdown
## Entity Cross-References

**People**:
- [[Dr. Russell Barkley]] - also mentioned in:
  - [[ADHD Research Overview]]
  - [[Executive Function Studies]]

**Organizations**:
- [[Medical Facility]] - also mentioned in:
  - [[Healthcare Providers List]]
```

**Implementation**:
- Search for entity names in other documents
- Create backlinks section
- Group by entity type

### 2.3 Bidirectional Links
**Feature**: Update linked notes with backlinks

**Example**: If Note A links to Note B, add to Note B:
```markdown
## Backlinks

- [[Note A]]
```

**Implementation**:
- Track outgoing links during export
- Update target notes with backlinks
- Maintain link graph

---

## 🎯 Priority 3: SmartNotes Compatibility (4 hours)

### 3.1 Dataview Inline Fields
**Feature**: Add inline fields after frontmatter

**Example**:
```markdown
---
title: "Note Title"
---

project:: [[Getting Started]]
hub:: [[Knowledge Management +]]
area:: 100
up:: [[Parent Note]]

- [ ] #cont/in/read
- [ ] #cont/zk/connect
```

**Implementation**:
- Detect note type from tags
- Map domains to area numbers
- Suggest hub/project based on tags
- Add workflow checkboxes

### 3.2 Folder Structure
**Feature**: Organize by note type

**Structure**:
```
/Zettel (permanent notes - #permanent tag)
/Projects (project notes - #project tag)
/Literature Notes (external sources - #literature tag)
```

**Implementation**:
- Detect primary tag
- Create folder structure
- Move files to appropriate folders

### 3.3 Title Markers
**Feature**: Add symbols to titles

**Examples**:
- `"Note Title +"` for entry notes/hubs (#hub tag)
- `"Note Title ++"` for MOCs (#hub/moc tag)
- `"WP Note Title"` for projects (#project tag)

**Implementation**:
- Detect tag patterns
- Modify title in frontmatter
- Update filename accordingly

---

## 🎯 Priority 4: Content Enhancement (4 hours)

### 4.1 Smart Content Parsing
**Feature**: Better content structure detection

**Improvements**:
- Detect headings (lines ending with :)
- Detect lists (-, *, numbers)
- Detect tables
- Detect code blocks
- Preserve formatting

### 4.2 Automatic Headings
**Feature**: Add section headings based on content

**Example**:
```markdown
## Dates and Events
- Monday 06.10
- Tuesday 07.10

## Important Information
[content...]
```

**Implementation**:
- Use LLM to suggest headings
- Or use heuristics (first sentence, keywords)

### 4.3 Extract Key Information
**Feature**: Highlight important data

**Example**:
```markdown
## Key Information
> **Due Date**: October 10, 2024
> **Contact**: school@example.com
> **Location**: Room 305
```

**Implementation**:
- Extract dates, emails, phone numbers
- Format as callouts/blockquotes
- Add to top of note

---

## 📊 Implementation Plan

### Week 1: Core Formatting (8 hours)
- [ ] Fix content formatting (2h)
- [ ] Clean up frontmatter (1h)
- [ ] Add basic related notes (3h)
- [ ] Test with 20 documents (2h)

**Result**: B+ export → A- export (85/100)

### Week 2: SmartNotes Integration (8 hours)
- [ ] Add Dataview fields (3h)
- [ ] Implement folder structure (2h)
- [ ] Add title markers (1h)
- [ ] Test with full workflow (2h)

**Result**: A- export → A export (90/100)

### Week 3: Advanced Features (8 hours)
- [ ] Entity cross-references (4h)
- [ ] Bidirectional links (2h)
- [ ] Smart content parsing (2h)

**Result**: A export → A+ export (95/100)

---

## 🎯 Quick Wins (Do First!)

### This Session (30 minutes):
1. ✅ Fix `DocumentType.pdf` → `pdf` (5 min)
2. ✅ Remove duplicate tags (5 min)
3. ✅ Clean source filename (5 min)
4. ✅ Basic list formatting (15 min)

### Tomorrow (2 hours):
1. ✅ Add Related Notes section (1.5h)
2. ✅ Better content parsing (30min)

---

## 💡 User Feedback Incorporated

**From user**:
> "output is without formatting"

**Fix**: Priority 1.1 - Content formatting

**From user**:
> "backlinks can be added also"

**Fix**: Priority 2.1-2.3 - Backlinks & related notes

**From user**:
> "its great overall"

**Interpretation**: Core functionality works, needs polish ✅

---

## 🎓 Recommendations

### Do NOW:
1. **Fix formatting** (Priority 1) - Most visible improvement
2. **Add related notes** (Priority 2.1) - High value, moderate effort

### Do SOON (this week):
3. **SmartNotes fields** (Priority 3.1) - If you need full workflow integration

### Do LATER (next month):
4. **Advanced features** (Priority 4) - Nice-to-have enhancements

---

**Current Obsidian Export Grade**: 78/100
**Target After Quick Wins**: 85/100
**Target After Full Implementation**: 95/100

---

Let me know which priorities you want to tackle first!
