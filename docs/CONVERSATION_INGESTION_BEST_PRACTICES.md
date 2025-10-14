# Conversation Ingestion Best Practices

**Email, WhatsApp, LLM Chat & Other Conversational Documents**

This guide covers best practices for ingesting conversational documents that benefit from special handling.

---

## Quick Summary

| Document Type | Recommended Approach | Date Source | Why |
|---------------|---------------------|-------------|-----|
| **Emails** | Individual `.eml` files | Email Date header | Chronological accuracy, proper daily notes |
| **Email Archives** | `.mbox` with threading | Email Date header | Groups into conversation threads |
| **WhatsApp** | Export as text file | Message timestamps | Preserves conversation flow |
| **LLM Chats** | Export as markdown | Export timestamp | Context-aware chunking |

---

## Email Ingestion

### Single Email Files (.eml)

**Best Practice**: Ingest individual `.eml` files for maximum accuracy.

```bash
# Upload single email
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@important_email.eml" \
  -F "generate_obsidian=true"
```

**What Happens**:
- ✅ Date extracted from `Date:` header (not ingestion time)
- ✅ Sender/recipient properly parsed
- ✅ Subject decoded (handles `=?UTF-8?Q?...?=` encoding)
- ✅ Attachments saved separately
- ✅ Appears in daily note for email's sent date

**Why This is Better**:
- Chronological accuracy: old emails show in correct daily notes
- Full metadata preserved (From, To, CC, BCC)
- Attachments referenced for future processing

### Email Archives (.mbox)

**Best Practice**: Use `.mbox` format for bulk email ingestion with threading.

```bash
# Upload mbox archive
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@gmail_export.mbox" \
  -F "generate_obsidian=true"
```

**What Happens**:
- ✅ Groups emails into conversation threads
- ✅ Chronological ordering within threads
- ✅ Preserves In-Reply-To and References headers
- ✅ One document per thread (better for RAG retrieval)

**Why Threading Matters**:
- **Better Context**: "Re: Project Update" messages are grouped together
- **Cleaner Search**: Find entire conversation, not fragmented messages
- **Reduced Noise**: 50 email replies → 1 threaded conversation document

**Thread Grouping Algorithm**:
1. Normalize subject (remove `Re:`, `Fwd:`, `RE:`, etc.)
2. Group by normalized subject
3. Order by date within thread
4. Track participants across thread

### Email Best Practices Summary

✅ **Do**:
- Use `.eml` for important individual emails (contracts, receipts)
- Use `.mbox` for bulk archives (Gmail exports, Outlook archives)
- Let the system extract dates automatically
- Enable Obsidian generation for daily note linking

❌ **Don't**:
- Don't convert emails to PDF before ingesting (loses metadata)
- Don't manually copy/paste email text (loses Date header)
- Don't worry about attachments - they're auto-saved

---

## WhatsApp Chat Exports

### Export Format

**Best Practice**: Export WhatsApp chats as `.txt` files (not `.zip`).

**How to Export**:
1. Open WhatsApp chat
2. Menu → More → Export Chat
3. Choose "Without Media" or "With Media"
4. Save as `.txt` file

### Ingestion

```bash
# Upload WhatsApp export
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@WhatsApp_Chat.txt" \
  -F "generate_obsidian=true"
```

**What Happens**:
- ✅ Detects WhatsApp format automatically
- ✅ Parses message timestamps (`[12/25/23, 10:15:30 AM]`)
- ✅ Extracts participants
- ✅ Preserves chronological order
- ✅ Handles system messages ("X was added", "X left")

**Timestamp Handling**:
- System uses **oldest message timestamp** as document date
- Daily note shows chat on the day it started
- Individual messages timestamped for future search

### Media Files

If exported "With Media":
- Images, videos saved to `/data/whatsapp_media/`
- Referenced in text with `[image omitted]`, `[video omitted]`
- Can be processed separately if needed

### WhatsApp Best Practices

✅ **Do**:
- Export regularly (weekly/monthly) for recent chats
- Use descriptive filenames (`mom_birthday_planning.txt`)
- Keep "With Media" for important visual context

❌ **Don't**:
- Don't export years-old chats (performance issues with 10,000+ messages)
- Don't mix multiple chat exports in one file

---

## LLM Chat Exports

### From ChatGPT, Claude, etc.

**Best Practice**: Export as markdown with proper frontmatter.

**Example Format**:
```markdown
---
title: "Debugging Python Import Error"
date: 2025-10-14
model: gpt-4
---

**User**: I'm getting ModuleNotFoundError...

**Assistant**: This error occurs when...
```

### Ingestion

```bash
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@chatgpt_export.md" \
  -F "generate_obsidian=true"
```

**What Happens**:
- ✅ Detected as `llm_chat` document type
- ✅ Title/date extracted from frontmatter
- ✅ Conversation structure preserved
- ✅ Code blocks preserved for RAG retrieval
- ✅ Appears in daily note 🤖 LLM Conversations section

### Why LLM Chats are Special

LLM chats benefit from **structure-aware chunking**:
- Code blocks kept intact (no mid-function splits)
- Q&A pairs grouped together
- Markdown formatting preserved
- Links and references maintained

### LLM Chat Best Practices

✅ **Do**:
- Export conversations immediately after completion
- Include descriptive titles
- Use proper markdown formatting
- Export long conversations as separate files

❌ **Don't**:
- Don't export entire chat history as one file (creates mega-document)
- Don't strip markdown formatting

---

## Daily Note Integration

### How Dates are Used

```
Emails          → Email Date header → daily note for sent date
WhatsApp        → First message      → daily note for chat start
LLM Chat        → Export timestamp   → daily note for chat date
Other docs      → Ingestion time     → daily note for today
```

### Daily Note Structure

```markdown
# Tuesday, October 14, 2025

← [[weeks/2025-W42|Week 42]] | [[months/2025-10|October 2025]] →

## 🤖 LLM Conversations

- [[2025-10-14__llm-chat__debugging-python__a1b2|Debugging Python Import Error]]
- [[2025-10-14__llm-chat__travel-planning__c3d4|Travel Planning Rome]]

## 📧 Emails

- [[2025-10-14__email__meeting-confirmation__e5f6|Meeting Confirmation]]

## 📄 Other Documents

- [[2025-10-14__whatsapp__family-group__g7h8|Family Group Chat]]
```

### Weekly Summaries

**Automatic LLM-Generated Insights**:

Weekly notes include a "What Was On My Mind" section generated from document summaries:

```bash
# Generate weekly note with summary
curl -X POST "http://localhost:8001/generate-weekly-note?date=2025-10-14&force=true"
```

**What Gets Summarized**:
- LLM chat topics and themes
- Email subjects and key points
- Document titles and summaries
- Patterns across the week

**Example Output**:
> I was thinking about optimizing my development workflow, with particular focus on Python tooling and debugging strategies. I also spent time planning travel logistics and coordinating meetings with team members.

---

## Batch Ingestion

### For Large Archives

**Best Practice**: Use batch scripts with rate limiting.

```bash
# Email archive (mbox handles bulk automatically)
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@2023_emails.mbox"

# Multiple files with rate limiting
for file in emails/*.eml; do
    curl -X POST http://localhost:8001/ingest/file \
        -F "file=@$file" \
        -F "generate_obsidian=true"
    sleep 0.5  # Rate limit to avoid overwhelming
done
```

### Backfilling Daily Notes

After bulk ingestion, backfill daily notes:

```bash
# Dry run first
docker exec rag_service python3 scripts/backfill_daily_notes.py \
    --obsidian-path /data/obsidian \
    --dry-run

# Actually create notes
docker exec rag_service python3 scripts/backfill_daily_notes.py \
    --obsidian-path /data/obsidian \
    --verbose
```

---

## Troubleshooting

### Email Dates Not Extracted

**Problem**: Emails show today's date instead of sent date

**Cause**: Emails converted to PDF/text before ingestion

**Fix**: Upload original `.eml` files

```bash
# Wrong
curl -F "file=@email_converted.pdf"  # ❌

# Right
curl -F "file=@original.eml"  # ✅
```

### WhatsApp Format Not Detected

**Problem**: WhatsApp chat treated as plain text

**Cause**: Non-standard export format

**Expected Format**:
```
[12/25/23, 10:15:30 AM] John: Hello there
[12/25/23, 10:16:45 AM] Jane: Hi John!
```

**Fix**: Re-export from WhatsApp directly (don't edit file)

### Daily Notes Show Wrong Dates

**Problem**: All documents appear in today's daily note

**Cause**: Bulk ingestion without proper metadata

**Fix**:
1. Check that source files have proper dates:
   - `.eml`: Date header present
   - `.mbox`: Message dates included
   - Markdown: Frontmatter with `date:` field

2. Regenerate daily notes:
```bash
# Remove existing daily notes
docker exec rag_service rm -rf /data/obsidian/refs/days/*

# Backfill with correct dates
docker exec rag_service python3 scripts/backfill_daily_notes.py \
    --obsidian-path /data/obsidian
```

### YAML Parsing Errors

**Problem**: Some documents fail with YAML frontmatter errors

**Cause**: Summaries with unescaped special characters

**Status**: Fixed in v2.2.1 with automatic sanitization

**What's Sanitized**:
- Newlines converted to spaces
- Excessive whitespace collapsed
- Summaries truncated to 500 chars

No action needed - auto-handled on ingestion.

---

## Performance Considerations

### Chunk Size Tuning

Conversational documents use structure-aware chunking:

```python
# Default settings (optimized for conversations)
target_size = 512 tokens   # ~2-3 message exchanges
overlap = 50 tokens        # Preserve context
max_size = 800 tokens     # Prevent mega-chunks
```

### When to Adjust:

**Shorter chunks** (256 tokens):
- Very dense technical conversations
- Lots of code snippets
- Need precise retrieval

**Longer chunks** (1024 tokens):
- Long-form discussions
- Narrative conversations
- Prioritize context over precision

### Search Performance

**Threading improves search**:
- Without threading: 1 email thread = 20 documents = 20 search results
- With threading: 1 email thread = 1 document = clean results

**RAG retrieval benefits**:
- More context per chunk (full message exchanges)
- Better semantic similarity (grouped topics)
- Reduced noise (no fragmented replies)

---

## Summary: Quick Reference

```bash
# Email (single)
curl -F "file=@email.eml" http://localhost:8001/ingest/file

# Email (archive with threading)
curl -F "file=@archive.mbox" http://localhost:8001/ingest/file

# WhatsApp
curl -F "file=@WhatsApp_Chat.txt" http://localhost:8001/ingest/file

# LLM Chat
curl -F "file=@chatgpt_export.md" http://localhost:8001/ingest/file

# Generate weekly note
curl -X POST "http://localhost:8001/generate-weekly-note?date=2025-10-14"

# Backfill daily notes
docker exec rag_service python3 scripts/backfill_daily_notes.py \
    --obsidian-path /data/obsidian
```

---

## See Also

- [Daily Notes Feature](../README.md#daily-notes) - Complete daily notes documentation
- [Testing Guide](TESTING_GUIDE.md) - How to test conversation ingestion
- [Architecture](../architecture/ARCHITECTURE.md) - System design overview
