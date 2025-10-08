# Obsidian Export Enhancements - October 7, 2025

## Summary

Enhanced Obsidian exports with comprehensive RAG technical metadata and source linking.

---

## What's New

### 1. Enhanced RAG Metadata Section ✨

The `rag:` section in frontmatter now includes **detailed comments and additional fields**:

```yaml
rag:
  # Quality metrics (0-1 scores)
  quality_score: 1.0
  novelty_score: 0.7
  actionability_score: 0.6
  recency_score: 1.0
  signalness: 0.79

  # Indexing flags
  do_index: true
  canonical: true

  # Document metadata
  page_span: null
  enrichment_version: '2.0'
  enrichment_cost_usd: 0.00005

  # Provenance (where this came from)
  provenance:
    sha256: 4384ab05d320f8ae
    sha256_full: 4384ab05d320f8ae1b2c3d4e5f6a7b8c...
    original_filename: upload_6e34e24c-f85d-4213-b31c-173254af4652_sample_invoice.md
    file_size_mb: 0.0
    ingestion_date: '2025-10-07T21:46:53.715256'
```

### 2. Source Link Section

Added a **Source** section in the document body:

```markdown
## Source

See `source` in frontmatter for original filename.
```

This makes it easy to find the original file that was ingested.

### 3. Complete Example

Here's a full example of the enhanced export:

```markdown
---
id: 20251007_upload-6e34e24c-f85d-4213-b31c-173254af4_4384
title: upload 6e34e24c f85d 4213 b31c 173254af4652 sample invoice
source: upload_6e34e24c-f85d-4213-b31c-173254af4652_sample_invoice.md
doc_type: text
organizations:
- Acme Corporation
- Example Bank
topics:
- business/accounting
- business/finance
- business/operations
created_at: '2025-10-07'
ingested_at: '2025-10-07'
tags:
- doc/text
- org/acme-corporation
- org/example-bank
- topic/business-accounting
- topic/business-finance
- topic/business-operations
rag:
  quality_score: 1.0
  novelty_score: 0.7
  actionability_score: 0.6
  recency_score: 1.0
  signalness: 0.74
  do_index: true
  canonical: true
  enrichment_version: '2.0'
  enrichment_cost_usd: 0.00005
  provenance:
    sha256: 4384ab05d320f8ae
    sha256_full: 4384ab05d320f8ae1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a
    original_filename: upload_6e34e24c-f85d-4213-b31c-173254af4652_sample_invoice.md
    file_size_mb: 0.0
    ingestion_date: '2025-10-07T21:46:53.715256'
---

# upload 6e34e24c f85d 4213 b31c 173254af4652 sample invoice

> **Summary:** Invoice #2025-1042 for Website Redesign project with Acme Corporation, totaling $10,472.

## Source

See `source` in frontmatter for original filename.

## Evidence / Excerpts

# Invoice #2025-1042

**Date:** October 7, 2025
**Client:** Acme Corporation
**Project:** Website Redesign

[... rest of invoice content ...]

<!-- RAG:IGNORE-START -->

## Xref

[[org:Acme Corporation]]
[[org:Example Bank]]

<!-- RAG:IGNORE-END -->
```

---

## What the RAG Metadata Means

### Quality Metrics (0-1 scores)

- **quality_score**: Overall document quality (1.0 = perfect text, no OCR issues)
- **novelty_score**: How unique/novel is this content (0.7 = somewhat novel)
- **actionability_score**: Does it contain action items/decisions (0.6 = some actions)
- **recency_score**: How recent is the document (1.0 = today, decays with age)
- **signalness**: Combined signal-to-noise ratio (0.79 = good quality overall)

### Indexing Flags

- **do_index**: Whether to include in search (true = yes, index this)
- **canonical**: Is this in the canonical corpus (true = high quality, include in main corpus)

### Document Metadata

- **page_span**: Page range for PDFs (null for non-PDFs)
- **enrichment_version**: Version of enrichment service used (2.0 = current)
- **enrichment_cost_usd**: Cost to enrich this document ($0.00005 = half a cent per 10 docs)

### Provenance

- **sha256**: Short hash for deduplication (first 16 chars)
- **sha256_full**: Full SHA-256 hash of content
- **original_filename**: Name of file that was ingested
- **file_size_mb**: Size of original file
- **ingestion_date**: When this was ingested into RAG system

---

## Use Cases

### 1. Filtering by Quality

In Dataview, filter documents by quality:

```dataview
TABLE quality_score, signalness, topics
FROM "data/obsidian"
WHERE rag.quality_score > 0.8
SORT rag.signalness DESC
```

### 2. Finding Recent High-Quality Documents

```dataview
LIST
FROM "data/obsidian"
WHERE rag.recency_score > 0.9 AND rag.canonical = true
SORT file.ctime DESC
LIMIT 10
```

### 3. Cost Analysis

Track enrichment costs:

```dataview
TABLE sum(rows.rag.enrichment_cost_usd) AS total_cost
FROM "data/obsidian"
GROUP BY dateformat(file.ctime, "yyyy-MM") AS month
```

### 4. Deduplication Check

Find duplicates by SHA-256:

```dataview
TABLE rag.provenance.sha256, file.name
FROM "data/obsidian"
WHERE rag.provenance.sha256 != ""
SORT rag.provenance.sha256
```

---

## Benefits

1. **Full Transparency**: See exactly how each document was processed
2. **Quality Filtering**: Filter by quality/signal metrics in Obsidian
3. **Cost Tracking**: Track LLM enrichment costs per document
4. **Deduplication**: SHA-256 hashes for finding duplicates
5. **Provenance**: Know exactly where each document came from
6. **Source Linking**: Easy reference back to original files

---

## Technical Details

**Files Modified:**
- `src/services/obsidian_service.py`
  - Enhanced `build_frontmatter()` with detailed RAG metadata
  - Added `enrichment_cost_usd` field
  - Enhanced provenance with full SHA-256, file size, ingestion date
  - Added comments to explain each field
  - Added Source section to document body

**Backward Compatible:** ✅
- Old Obsidian files still work
- New fields are additive
- No breaking changes

**Storage Impact:**
- ~200 bytes additional metadata per document
- Negligible storage cost

---

## Example Queries You Can Now Run

### Find Expensive Documents
```dataview
TABLE rag.enrichment_cost_usd * 1000 AS "Cost (¢)"
FROM "data/obsidian"
SORT rag.enrichment_cost_usd DESC
LIMIT 10
```

### Quality Dashboard
```dataview
TABLE
  rag.quality_score as "Quality",
  rag.novelty_score as "Novelty",
  rag.signalness as "Signal",
  topics[0] as "Primary Topic"
FROM "data/obsidian"
WHERE rag.quality_score > 0
SORT rag.signalness DESC
```

### Recent Canonical Documents
```dataview
LIST
FROM "data/obsidian"
WHERE rag.canonical = true
  AND rag.recency_score > 0.8
SORT file.ctime DESC
```

---

*Enhancements deployed: October 7, 2025*
*Compatible with: Obsidian + Dataview plugin*
*Breaking changes: None*
