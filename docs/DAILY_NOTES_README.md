# Daily Notes Feature - Complete Documentation

**Automatic journal generation linking documents by date**

## Overview

The Daily Notes feature automatically creates time-based journal entries that link to your ingested documents by date. It provides three levels of temporal organization:

- **Daily Notes** (`refs/days/YYYY-MM-DD.md`) - All documents from a specific day
- **Weekly Notes** (`refs/weeks/YYYY-W##.md`) - Links to daily notes + LLM summary
- **Monthly Notes** (`refs/months/YYYY-MM.md`) - Links to weekly notes + overview

## Quick Start

```bash
# Documents automatically create daily notes
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@document.pdf" \
  -F "generate_obsidian=true"

# Generate weekly note with LLM summary
curl -X POST "http://localhost:8001/generate-weekly-note?date=2025-10-14"

# Generate monthly note
curl -X POST "http://localhost:8001/generate-monthly-note?date=2025-10-14"

# Get daily note content
curl "http://localhost:8001/daily-note/2025-10-14"
```

## Features

### 1. Automatic Daily Note Creation

When a document is ingested with `generate_obsidian=true`, a daily note is automatically created or updated.

**Example Daily Note** (`refs/days/2025-10-14.md`):

```markdown
---
date: '2025-10-14'
type: daily-note
week: '[[weeks/2025-W42]]'
month: '[[months/2025-10']]'
documents:
  - id: 20251014_debugging-python__a1b2
    title: Debugging Python Import Error
    type: llm_chat
    filename: 2025-10-14__llm-chat__debugging-python__a1b2
  - id: 20251014_meeting-notes__c3d4
    title: Meeting Notes
    type: email
    filename: 2025-10-14__email__meeting-notes__c3d4
---

# Tuesday, October 14, 2025

← [[weeks/2025-W42|Week 42]] | [[months/2025-10|October 2025]] →

## 🤖 LLM Conversations

- [[2025-10-14__llm-chat__debugging-python__a1b2|Debugging Python Import Error]]

## 📧 Emails

- [[2025-10-14__email__meeting-notes__c3d4|Meeting Notes]]

## 📄 Other Documents

- [[2025-10-14__text__report__e5f6|Quarterly Report]] (text)
```

**Key Features**:
- Documents grouped by type (🤖 LLM, 📧 Email, 📄 Other)
- Links to weekly/monthly notes for navigation
- Duplicate prevention (same document only listed once)
- Frontmatter for Dataview queries

### 2. Date Handling

Documents use their **created date**, not ingestion time:

| Document Type | Date Source | Example |
|---------------|-------------|---------|
| Email (.eml) | `Date:` header | Mon, 1 Jan 2024 10:30:00 +0000 → 2024-01-01 |
| Word/PDF | File metadata | Document properties → created date |
| Other files | Ingestion time | Today's date |

**Email Date Extraction**:
```python
# Automatically parsed from email headers
Date: Wed, 15 Mar 2023 14:30:00 +0000
# Results in created_at: 2023-03-15
```

### 3. Weekly Notes with LLM Summaries

Weekly notes aggregate daily activity and generate an LLM-powered summary of themes.

**Example Weekly Note** (`refs/weeks/2025-W42.md`):

```markdown
---
week: 2025-W42
year: 2025
week_number: 42
type: weekly-note
month: '[[months/2025-10]]'
daily_notes:
  - date: '2025-10-14'
    day_name: Tuesday
    filename: days/2025-10-14
  - date: '2025-10-15'
    day_name: Wednesday
    filename: days/2025-10-15
llm_chat_count: 12
---

# Week 42, 2025

← [[months/2025-10|October 2025]] →

## Daily Notes

- [[days/2025-10-14|Tuesday, 2025-10-14]]
- [[days/2025-10-15|Wednesday, 2025-10-15]]

## What Was On My Mind

I was thinking about software architecture patterns and system design,
particularly around microservices and event-driven systems. Several conversations
explored database optimization strategies and caching patterns. I also spent time
debugging Python import issues and exploring new testing frameworks.

## Week Summary

- **LLM Conversations**: 12
- **Days with activity**: 2
```

**LLM Summary Generation**:
- Uses Groq Llama 3.1 8B (fast & cheap: ~$0.00001 per summary)
- Analyzes document summaries, not just titles
- Identifies patterns and themes across conversations
- Written in first person ("I was thinking about...")

### 4. Monthly Notes

Monthly notes provide high-level overview by linking to weekly notes.

**Example Monthly Note** (`refs/months/2025-10.md`):

```markdown
---
month: 2025-10
year: 2025
month_number: 10
type: monthly-note
weekly_notes:
  - week: 2025-W42
    filename: weeks/2025-W42
  - week: 2025-W43
    filename: weeks/2025-W43
---

# October 2025

## Weekly Notes

- [[weeks/2025-W42|2025-W42]]
- [[weeks/2025-W43|2025-W43]]

## Month Summary

- **Weeks tracked**: 2
```

## API Reference

### POST /generate-weekly-note

Generate or regenerate weekly note with LLM summary.

**Parameters**:
- `date` (optional): Date in `YYYY-MM-DD` format (defaults to today)
- `force` (optional): Regenerate even if exists (default: false)

**Example**:
```bash
curl -X POST "http://localhost:8001/generate-weekly-note?date=2025-10-14&force=true"
```

**Response**:
```json
{
  "success": true,
  "note_path": "/data/obsidian/refs/weeks/2025-W42.md",
  "week": "2025-W42",
  "date": "2025-10-14"
}
```

### POST /generate-monthly-note

Generate or regenerate monthly note.

**Parameters**:
- `date` (optional): Date in `YYYY-MM-DD` format (defaults to today)
- `force` (optional): Regenerate even if exists (default: false)

**Example**:
```bash
curl -X POST "http://localhost:8001/generate-monthly-note?date=2025-10-01"
```

**Response**:
```json
{
  "success": true,
  "note_path": "/data/obsidian/refs/months/2025-10.md",
  "month": "2025-10",
  "date": "2025-10-01"
}
```

### GET /daily-note/{date}

Retrieve daily note content for a specific date.

**Parameters**:
- `date`: Date in `YYYY-MM-DD` format (path parameter)

**Example**:
```bash
curl "http://localhost:8001/daily-note/2025-10-14"
```

**Response**:
```json
{
  "success": true,
  "date": "2025-10-14",
  "note_path": "/data/obsidian/refs/days/2025-10-14.md",
  "content": "---\ndate: '2025-10-14'\n..."
}
```

## Backfilling Existing Documents

After bulk ingestion or enabling the feature, backfill daily notes for existing documents:

```bash
# Dry run (preview only)
docker exec rag_service python3 scripts/backfill_daily_notes.py \
    --obsidian-path /data/obsidian \
    --dry-run

# Actually create notes
docker exec rag_service python3 scripts/backfill_daily_notes.py \
    --obsidian-path /data/obsidian \
    --verbose
```

**Script Options**:
- `--obsidian-path`: Path to Obsidian vault (default: `./obsidian_vault`)
- `--dry-run`: Preview without creating files
- `--verbose` or `-v`: Show detailed progress

**What It Does**:
1. Reads all `.md` files in Obsidian vault
2. Extracts `created_at` date from frontmatter
3. Creates/updates daily notes for each unique date
4. Groups documents by date
5. Generates proper frontmatter and body

**Performance**:
- 2234 documents processed in ~10 seconds
- Memory efficient (streams files)
- Safe (skips invalid dates)

## Architecture

### Service Layer

**DailyNoteService** (`src/services/daily_note_service.py`):
- `add_document_to_daily_note()` - Add document to daily note
- `generate_weekly_note()` - Generate weekly note with LLM summary
- `generate_monthly_note()` - Generate monthly overview
- `_load_document_summary()` - Load full document for summary
- `_generate_weekly_summary()` - LLM-powered theme analysis

**Integration Points**:
- `ObsidianService.export_document()` - Calls `add_document_to_daily_note()`
- `LLMService` - Used for weekly summaries
- `RAGService` - Initializes `DailyNoteService` singleton

### Date Flow

```
Document Ingestion
    ↓
DocumentService.process_file()
    ↓ (for emails)
_process_email() → returns (text, {created_date: "YYYY-MM-DD"})
    ↓
RAGService.ingest_document()
    ↓ (uses created_date if available)
ObsidianService.export_document(created_at=doc_date)
    ↓
DailyNoteService.add_document_to_daily_note()
    ↓
Daily note created/updated for doc_date
```

### Deduplication

**Frontmatter Level**:
```python
# Check if document ID already exists
if not any(d.get('id') == doc_id for d in frontmatter['documents']):
    frontmatter['documents'].append(doc_entry)
```

**Body Level**:
```python
# Check if wiki-link already exists
if link in body:
    return body  # Skip adding duplicate
```

### YAML Sanitization

**Purpose**: Prevent parsing errors from newlines/quotes in summaries.

**Implementation** (`ObsidianService._sanitize_yaml_string()`):
```python
def _sanitize_yaml_string(self, value: str) -> str:
    # Replace newlines with spaces
    cleaned = value.replace('\n', ' ').replace('\r', ' ')

    # Collapse multiple spaces
    cleaned = ' '.join(cleaned.split())

    # Limit length
    if len(cleaned) > 500:
        cleaned = cleaned[:497] + '...'

    return cleaned
```

**Applied To**:
- `summary` field in frontmatter
- Fixes 29 YAML parsing errors in backfill test

## Testing

### Automated Test Suite

Run comprehensive tests:

```bash
bash scripts/test_daily_notes.sh
```

**Tests**:
1. ✅ Email date extraction
2. ✅ Daily note creation
3. ✅ Duplicate prevention
4. ✅ YAML sanitization
5. ✅ Weekly note generation
6. ✅ Monthly note generation
7. ✅ API endpoints

### Manual Testing

**Test Email Date Extraction**:
```bash
# Create test email
cat > /tmp/test.eml << 'EOF'
From: test@example.com
To: you@example.com
Subject: Test Email
Date: Mon, 1 Jan 2024 10:30:00 +0000

Test content
EOF

# Ingest
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@/tmp/test.eml" \
  -F "generate_obsidian=true"

# Check daily note
docker exec rag_service cat /data/obsidian/refs/days/2024-01-01.md
```

**Test Weekly Summary**:
```bash
# Generate weekly note
curl -X POST "http://localhost:8001/generate-weekly-note?date=2024-01-01&force=true"

# View summary
docker exec rag_service cat /data/obsidian/refs/weeks/2024-W01.md | grep -A 10 "What Was On My Mind"
```

## Troubleshooting

### Daily Notes Show Wrong Dates

**Problem**: All documents appear in today's daily note instead of correct dates.

**Cause**: Documents lack proper date metadata.

**Fix**:
1. For emails: Upload `.eml` files (not PDF/text conversions)
2. For other docs: Ensure file metadata includes creation date
3. Backfill after fixing: `scripts/backfill_daily_notes.py`

### Duplicate Entries in Daily Notes

**Problem**: Same document appears multiple times in daily note.

**Status**: Fixed in v2.2.2

**Fix Applied**:
- Added duplicate check in `_update_daily_note_body()`
- Checks both frontmatter (by ID) and body (by wiki-link)

### Weekly Summary Not Generating

**Problem**: "What Was On My Mind" section missing.

**Causes**:
1. No LLM chats that week (only emails/docs)
2. LLM service unavailable
3. Groq API rate limit

**Fix**:
- Summary only generated if `llm_chat` documents exist
- Uses Groq (check `GROQ_API_KEY` is set)
- Retry after rate limit expires

### YAML Parsing Errors

**Problem**: Backfill script shows YAML parsing errors.

**Example**:
```
while scanning a quoted scalar: found unexpected end of stream
```

**Status**: Fixed with `_sanitize_yaml_string()`

**What's Sanitized**:
- Newlines → spaces
- Multiple spaces → single space
- Truncated to 500 chars

## Performance

### Costs

| Operation | Model | Cost per Call |
|-----------|-------|---------------|
| Weekly Summary | Groq Llama 3.1 8B | ~$0.00001 |
| Document Ingestion | Claude Haiku | ~$0.00025 |
| Daily Note Creation | N/A | Free (local) |

**Monthly Costs** (1000 docs):
- Daily notes: $0 (automatic)
- Weekly summaries: $0.0004 (4 weeks × $0.0001)
- Document ingestion: $0.25 (1000 × $0.00025)
- **Total**: ~$0.25/month for 1000 docs

### Speed

| Operation | Time |
|-----------|------|
| Daily note creation | <100ms |
| Weekly note generation | ~2s (with LLM summary) |
| Monthly note generation | <500ms |
| Backfill 2234 docs | ~10s |

### Storage

| Item | Size per Note |
|------|---------------|
| Daily note | ~1-5 KB |
| Weekly note | ~2-10 KB |
| Monthly note | ~1-3 KB |

**Example**: 365 days + 52 weeks + 12 months = ~2-5 MB/year

## Best Practices

### Document Organization

✅ **Do**:
- Upload original `.eml` files for emails (preserves dates)
- Enable `generate_obsidian=true` for all documents
- Run backfill after bulk ingestion
- Generate weekly notes at end of week

❌ **Don't**:
- Convert emails to PDF before ingestion (loses Date header)
- Manually edit daily notes (will be overwritten)
- Delete refs/ directory (breaks wiki-links)

### Weekly Summaries

**For Better Summaries**:
1. Upload LLM chat exports regularly (they drive the summary)
2. Use descriptive document titles
3. Keep summaries in frontmatter (used by LLM)
4. Regenerate with `force=true` after adding more docs

### Dataview Queries

Daily notes support powerful Dataview queries:

**All documents from a specific week**:
```dataview
TABLE file.link as Document, summary as Summary
FROM "refs/days"
WHERE week = "[[weeks/2025-W42]]"
```

**LLM chats across all time**:
```dataview
TABLE file.link as "Daily Note", llm_chat_count as "Chats"
FROM "refs/days"
WHERE llm_chat_count > 0
SORT file.name DESC
```

**Weekly activity heatmap**:
```dataview
TABLE week, length(daily_notes) as "Active Days", llm_chat_count as "LLM Chats"
FROM "refs/weeks"
SORT week DESC
LIMIT 10
```

## See Also

- [Conversation Ingestion Best Practices](CONVERSATION_INGESTION_BEST_PRACTICES.md)
- [Testing Guide](guides/TESTING_GUIDE.md)
- [Architecture Overview](architecture/ARCHITECTURE.md)
- [API Documentation](../README.md#api-reference)

## Changelog

### v2.2.2 (Oct 14, 2025)
- 🐛 Fixed duplicate entries in daily notes
- ✅ Added comprehensive test suite
- 📚 Complete documentation

### v2.2.1 (Oct 14, 2025)
- ✅ Email date extraction from headers
- ✅ YAML sanitization for summaries
- ✅ Rich weekly summaries using document content
- ✅ Best practices documentation

### v2.2.0 (Oct 14, 2025)
- ✨ Initial daily notes feature
- 🤖 LLM-powered weekly summaries
- 📅 Backfill script for existing documents
- 🔌 REST API endpoints
