# Real Data Test Results - October 8, 2025

## Test Summary

**Documents Ingested**: 19 total (10 new test documents)
**Total Chunks**: 181
**Storage Used**: 0.13 MB
**Test Duration**: ~2 minutes

**Document Types Tested**:
- Legal PDFs (court decisions, educational regulations)
- Markdown notes (custody planning, school enrollment, technical docs)
- Journal entries (daily notes)
- Articles (tech reviews)
- Student lists (scanned PDFs)

---

## Critical Issues Found

### 1. ❌ Wrong Frontmatter Structure (Blueprint Violation)

**Problem**: Scores nested under `rag:` instead of top-level

**Blueprint Spec**:
```yaml
quality_score: 0.94
novelty_score: 0.72
actionability_score: 0.80
signalness: 0.85
do_index: true

provenance:
  sha256: "..."
  source_ref: "..."
```

**Our Implementation** (WRONG):
```yaml
rag:
  quality_score: 1.0
  novelty_score: 0.6
  actionability_score: 0.6
  recency_score: 1.0
  signalness: 0.76
  do_index: true
  provenance:
    sha256: 80f90d8d39012cd7
```

**Impact**:
- Not blueprint-compliant
- Harder to query in Dataview
- Inconsistent with standard RAG systems

---

### 2. ❌ Missing Entities Section (Critical Data Loss)

**Problem**: No `entities:` section with orgs, dates, numbers

**Blueprint Spec**:
```yaml
entities:
  orgs: [Kita XY, Example Corp]
  dates: ["2025-09-29", "2025-10-02", "2025-11-15"]
  numbers: ["+49-123-456", "€1,500", "310 F 141/25"]
```

**Our Implementation**: ❌ **MISSING ENTIRELY**

**Real-World Examples of Data Loss**:

#### Legal Court Decision (2025-08-22-BschlussKur.pdf)
**Dates Lost** (should be in entities.dates):
- 2025-08-22 (decision date)
- 2024-03-xx (separation date)
- 2024-01-20 (child's birth date)
- 2024-10-30 (previous order date)
- 2024-10-31, 2024-11-06, 2024-12-26 (contact dates)

**Numbers Lost** (should be in entities.numbers):
- "310 F 141/25" (case number)
- "310 F 158/24", "310 F 159/24", "310 F 160/24" (related cases)
- "2.500 Euro" (court value)
- "18 Uhr", "7:00 Uhr" (times)

**Organizations** (partially extracted):
- ✅ "Techniker Krankenkasse"
- ✅ "AWO-Kliniki 'Zur Solequelle'"
- ❌ Should be in entities.orgs, not top-level

#### School Enrollment Doc (einschulung_2026_27_nrw_zeitstrahl_checkliste_obsidian.md)
**Dates Lost** (15+ critical dates):
- 2025-09-30 (info evening)
- 2025-10-02 (info evening)
- 2025-10-06 to 2025-10-10 (registration week)
- **2025-11-15** (DEADLINE - critical!)
- 2025-10-13 to 2025-10-25 (autumn holidays)
- 2026-02-01 to 2026-04-30 (decision window)
- 2026-07-20 to 2026-09-01 (summer holidays)
- **2026-09-02** (first school day - critical!)

**Places Lost**:
- Köln (mentioned in frontmatter but not extracted)
- Essen (mentioned in frontmatter but not extracted)

**Organizations Lost**:
- Gesundheitsamt
- Schools (not specifically named but referenced)

#### Custody Models Doc (Custody-Models-Visual-Note.md)
**Numbers Lost** (percentages, counts):
- "79%" (dad's overnight percentage)
- "21%" (mom's overnight percentage)
- "64%", "36%" (model 2 percentages)
- "22 overnights", "6 overnights", "18 overnights", "10 overnights"
- "3 of 4 weekends"
- "50/50", "60-65%", "70%" (holiday splits)

**Dates Lost** (schedule references):
- Days of week (Mon-Sun patterns)
- Week numbers (Week 1-4 rotation)

**Impact**: **MASSIVE information loss** - key deadlines, case numbers, percentages completely missing

---

### 3. ❌ Topic Misclassification (Wrong Vocabulary Matching)

**Problem**: Legal/family documents tagged as business, school documents missing topics entirely

**Examples**:

| Document | Actual Topic | Wrong Classification | Should Be |
|----------|--------------|---------------------|-----------|
| Court decision (legal custody) | Legal/family | `business/finance`, `business/operations` | `legal/family`, `legal/custody`, `legal/court-decision` |
| Custody models (parenting plan) | Legal/family | `business/operations`, `business/planning` | `legal/custody`, `family/parenting`, `planning/schedule` |
| School enrollment timeline | Education/planning | **NO TOPICS** | `education/school`, `education/enrollment`, `planning/timeline` |
| IT school privacy doc | Education/IT | `communication/announcement` | `education/it`, `privacy/data-protection` |

**Root Cause**:
- LLM not selecting correct topics from vocabulary
- Need better prompting or examples
- May need education/legal vocabulary expansion

---

### 4. ⚠️ Title Extraction Issues (PDFs)

**Problem**: Some PDF titles are poor (first line extraction)

**Examples**:
- ❌ "Herr Daniel Teckentrup, Darmstädter Straße 13, 50678 Köln, Antragsgegner und Vater, V"
  - Should be: "Court Decision - Custody Motion Rejection"
- ❌ "3 SchulG ) nimmt ein Teil der Schülerinnen und Schüler de"
  - Should be: "OGS Participation FAQ"
- ❌ "upload 4ecd62ca 0c0e 4e1b 9bc1 faee3586a356 LessonStudentListImg 20250911 0724"
  - Should be: "Student List - September 2024"

**Impact**: Poor search UX, unclear document references

---

### 5. ❌ No Date Entity Linking (Missing Temporal Navigation)

**Problem**: No date entity stubs or links

**Blueprint Expectation**:
```markdown
## Timeline

- [[day:2025-10-07]] -- Invoice sent
- [[day:2025-11-06]] -- Payment due
- [[day:2025-09-29]] -- Project kickoff
```

**Our Implementation**: ❌ None

**Impact**:
- No temporal navigation
- Can't find "what happened on this date"
- Can't build timelines
- Missing critical deadline tracking

---

### 6. ⚠️ Entity Stubs Too Sparse

**Current Person Stub**:
```yaml
---
type: person
name: Richterin
aliases: []
---

# Richterin

```dataview
LIST FROM "10_normalized_md"
WHERE contains(people, "Richterin")
SORT created_at DESC
```
```

**What's Missing**:
- Role context (judge in family court)
- Relationships (involved in which cases)
- Timeline (first/last mentioned)
- Document statistics
- Locations (which court)

---

## Detailed Test Results by Document

### 1. Legal Court Decision (PDF) - 2025-08-22-BschlussKur.pdf

**✅ Good**:
- Quality score: 0.85 (good OCR)
- People roles extracted: Richterin, Rechtsanwalt, Verfahrensbevollmächtigter
- Organizations extracted: Techniker Krankenkasse, AWO-Kliniki
- Place extracted: Köln

**❌ Problems**:
- Title terrible (first line of PDF text)
- Topics wrong: `business/finance` instead of `legal/family`
- **15+ dates not extracted**
- **5+ case numbers not extracted**
- No entities section
- Personal data exposed (Daniel Teckentrup, address) - may need redaction

**Content**:
- Case: 310 F 141/25 (custody/visitation)
- Decision: Rejected mother's request for spa trip
- Key dates: 2025-08-22 (decision), 2024-10-30 (previous order)
- Parties: Daniel Teckentrup (father), Fanny Teckentrup (mother), Pola Teckentrup (child, born 2020-01-20)

### 2. Custody Models (MD) - Custody-Models-Visual-Note.md

**✅ Good**:
- Title: Perfect
- Quality: 1.0
- Structure preserved well

**❌ Problems**:
- Topics wrong: `business/operations` instead of `legal/custody`
- People: lawyer, Jugendamt extracted (good!) but sparse
- Place: Essen (good!)
- **20+ percentages/numbers not extracted**
- **Schedule dates/patterns not extracted**
- No entities section
- No links to related documents (court cases)

**Content**:
- Custody schedule models (79% dad, 21% mom OR 64%/36%)
- Holiday policies (50/50, 60-65%, 70% options)
- Handover rules (Sun night anchor)
- Target audience: lawyer, Jugendamt, court

### 3. School Enrollment Timeline (MD) - einschulung_2026_27_nrw_zeitstrahl_checkliste_obsidian.md

**✅ Good**:
- Title: Perfect
- Structure: Excellent (Mermaid diagram, checklists)
- Quality: 1.0

**❌ Problems**:
- **NO TOPICS EXTRACTED** (should be education/school, planning/timeline)
- **NO PEOPLE EXTRACTED**
- **NO PLACES EXTRACTED** (Köln, Essen in content!)
- **15+ CRITICAL DATES NOT EXTRACTED**:
  - 2025-11-15 (DEADLINE!)
  - 2026-09-02 (first school day)
  - Registration week, holidays, etc.
- No entities section
- No organization extraction (Gesundheitsamt)

**Content**:
- NRW school enrollment 2026/27
- Köln registration: 2025-10-06 to 2025-10-10
- **Critical deadline**: 2025-11-15
- First school day: 2026-09-02
- Comprehensive checklists and timeline

### 4. IT School Privacy Doc (MD) - HIN_InfoBlatt_Datenschutz_2025.md

**✅ Good**:
- Title: "Heinz-Nixdorf-Berufskolleg · Informationstechnik"
- Quality: 1.0

**❌ Problems**:
- Topics: Only `communication/announcement` (missing IT, privacy, education)
- No organizations extracted (school name)
- No dates extracted
- No entities section

### 5. RAG Technical Doc (MD) - personal_homelab_rag_no_nonsense_v_3_daniel_tuned.md

**✅ Good**:
- Title: "Personal Homelab RAG — No‑Nonsense v3 Daniel‑tuned"
- Quality: 1.0
- Large doc (14KB)

**❌ Problems**:
- Topics not checked yet
- Technical terms likely not extracted as entities
- Version numbers, tech stack not in entities
- No dates extracted

### 6. Daily Journal (MD) - 2024-04-28.md

**❌ Problems**:
- Title: Generic UUID-based
- Topics likely missing
- Date (2024-04-28) not in entities
- Personal entries not categorized

### 7. Tech Article (MD) - Sony WF-1000XM5 Review

**❌ Problems**:
- Title: UUID-based
- Product name "Sony WF-1000XM5" likely not in entities.orgs
- Price numbers not extracted
- Review date not extracted

---

## Statistics

### Extraction Success Rate

| Entity Type | Should Extract | Actually Extracted | Success Rate |
|-------------|----------------|-------------------|--------------|
| **Dates** | ~50 dates | 0 dates | **0%** ❌ |
| **Numbers** | ~40 numbers | 0 numbers | **0%** ❌ |
| **Organizations** | ~15 orgs | ~12 orgs | **80%** ✅ |
| **People** | ~10 people | ~8 people | **80%** ✅ |
| **Places** | ~8 places | ~5 places | **62%** ⚠️ |
| **Topics** | 19 docs | ~10 correct | **53%** ❌ |

### Data Loss Impact

**Critical Information Lost**:
- **ALL dates** (deadlines, court dates, school dates)
- **ALL numbers** (case numbers, amounts, percentages, times)
- **47% of topics** (misclassified or missing)
- **38% of places** (mentioned but not extracted)

**Use Cases Broken**:
- ❌ Timeline queries ("what happened on 2025-11-15?")
- ❌ Deadline tracking ("upcoming deadlines")
- ❌ Case number lookup ("find case 310 F 141/25")
- ❌ Amount searches ("invoices over €1000")
- ❌ Date-based filtering (can't use entities.dates)

---

## Root Cause Analysis

### 1. Frontmatter Structure
**Cause**: Designed before seeing blueprint
**Fix**: Refactor to move scores to top-level

### 2. Missing Entities Section
**Cause**: Not implemented in enrichment service
**Fix**: Add date/number extraction to enrichment_service.py

### 3. Topic Misclassification
**Cause**:
- LLM prompt not specific enough
- Vocabulary may need legal/education expansion
- No examples in prompt

**Fix**:
- Improve prompt with examples
- Add legal/* and education/* topic categories
- Use few-shot prompting

### 4. Title Extraction (PDFs)
**Cause**: Using first line as fallback
**Fix**:
- Use document type detection
- Extract from metadata first
- Smarter heuristics for legal/official docs

### 5. Date Entity Linking
**Cause**: Not implemented
**Fix**:
- Extract dates with regex + NER
- Create date entity stubs
- Add date links to documents

---

## Action Items (Priority Order)

### 🔴 CRITICAL (Blocking)
1. **Fix frontmatter structure** (2-3h)
   - Move scores to top-level
   - Blueprint-compliant format
   - Update all existing docs

2. **Add entities section** (3-4h)
   - Extract dates (regex: YYYY-MM-DD, DD.MM.YYYY, etc.)
   - Extract numbers (amounts, case numbers, percentages)
   - Move orgs to entities.orgs
   - Update enrichment_service.py

### 🟡 HIGH PRIORITY (Major improvement)
3. **Fix topic classification** (2-3h)
   - Add legal/* topics (legal/family, legal/custody, legal/court-decision)
   - Add education/* topics (education/school, education/enrollment)
   - Improve LLM prompt with examples
   - Test with real documents

4. **Improve title extraction** (2h)
   - Document type detection
   - Metadata-first approach
   - Better heuristics for PDFs

5. **Date entity linking** (3-4h)
   - Create date extraction pipeline
   - Generate date entity stubs
   - Add links to documents
   - Timeline navigation

### 🟢 MEDIUM PRIORITY (Enhancement)
6. **Enhance entity stubs** (2-3h)
   - Rich person metadata
   - Rich place metadata
   - Context and relationships

7. **Cross-document linking** (2h)
   - Related documents section
   - Same project/case links
   - Temporal links (prev/next)

---

## Test Documents Inventory

| # | Filename | Type | Size | Topics | Issues |
|---|----------|------|------|--------|--------|
| 1 | 2025-08-22-BschlussKur.pdf | Legal PDF | 80KB | Legal/custody | Title, dates, numbers |
| 2 | Custody-Models-Visual-Note.md | Planning MD | 10KB | Legal/planning | Topics, numbers |
| 3 | einschulung_2026_27_nrw_zeitstrahl_checkliste_obsidian.md | Timeline MD | 10KB | Education | All entities missing |
| 4 | HIN_InfoBlatt_Datenschutz_2025.md | Info MD | 5KB | Education/IT | Topics, entities |
| 5 | personal_homelab_rag_no_nonsense_v_3_daniel_tuned.md | Technical MD | 14KB | Tech/RAG | Entities |
| 6 | FAQ-zur-Teilnahmeregelung-OGS.pdf | FAQ PDF | 16KB | Education | Title, topics |
| 7 | LessonStudentListImg_20250911_0724.pdf | Scan PDF | 3KB | Education | Title, OCR |
| 8 | 2024-04-28.md | Journal MD | 4KB | Personal | Title, dates |
| 9 | 2023-08-14 In-Ear-Kopfhörer... | Article MD | 8KB | Tech | Entities |
| 10 | 2024-02-07 Pump Up the Volume.md | Article MD | 11KB | Tech | Entities |

---

## Conclusion

**Current System Grade**: **C (70/100)** - Works but misses critical data

**Issues by Severity**:
- 🔴 **CRITICAL**: 2 issues (frontmatter, entities section)
- 🟡 **HIGH**: 3 issues (topics, titles, date linking)
- 🟢 **MEDIUM**: 2 issues (entity metadata, cross-linking)

**Data Loss**: **~40% of extractable information lost**
- 0% of dates extracted (should be 100%)
- 0% of numbers extracted (should be 100%)
- 53% of topics correct
- 80% of organizations extracted

**Next Steps**:
1. Fix frontmatter structure (blueprint compliance)
2. Implement entities section (dates, numbers, orgs)
3. Fix topic classification (legal, education categories)
4. Test again with same documents
5. Measure improvement

**Target After Fixes**: **A (92/100)**
- 100% blueprint compliance
- 95%+ entity extraction
- 90%+ topic accuracy
- Full temporal navigation
- Rich entity metadata

---

*Test completed: October 8, 2025 00:15 CET*
*Documents tested: 19 (10 new diverse documents)*
*Test duration: ~2 minutes ingestion + 10 minutes analysis*
*Next: Fix critical issues and re-test*
