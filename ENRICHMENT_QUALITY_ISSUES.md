# Enrichment Quality Issues

**Discovered:** 2025-10-14
**Severity:** HIGH - Data contamination/hallucination

## Problem

LLM enrichment is generating **hallucinated or contaminated metadata**:

### Example: `2025-10-14__text__preserving-windows-10-laptop__a529.md`

**Source:** ChatGPT conversation about Windows 10 laptop → Clonezilla → Proxmox VM

**Expected Metadata:**
- Topics: technology/virtualization, technology/backup
- People: User, Assistant (from chat)
- Organizations: Synology, Proxmox

**Actual (WRONG) Metadata:**
```yaml
People:
  - Dr. Schmidt (lawyer) ❌ NOT IN SOURCE
  - Anna Lins ❌ NOT IN SOURCE
Places:
  - Köln, Berlin ❌ IRRELEVANT
Dates:
  - 2025-11-25, 2025-12-15 ❌ NOT IN SOURCE
  - Case number: 310 F 141/25 ❌ LEGAL CASE DATA!
Topics:
  - business/finance ❌ WRONG
  - business/accounting ❌ WRONG
```

## Root Causes (Hypothesis)

1. **Cross-document contamination** - LLM context bleed between requests
2. **Hallucination** - LLM inventing entities
3. **Poor prompt constraints** - Not limiting to actual document content
4. **Token limit issues** - Truncated content leading to errors

## Impact

- ❌ Search returns irrelevant results
- ❌ Entity cross-references link unrelated documents
- ❌ Topic clustering mixes unrelated content
- ❌ User trust in system degraded

## Next Steps

1. **Review enrichment prompts** in `src/services/enrichment_service.py`
2. **Add validation** - Cross-check extracted entities against source
3. **Test with known examples** - Regression test suite
4. **Consider** - Use entity extraction models instead of pure LLM
5. **Re-enrich affected documents** - Batch fix after solution

## Workaround

For now: Continue ingestion, fix enrichment logic, then re-process all documents.

## Files to Review

- `src/services/enrichment_service.py:105` - Entity extraction
- `src/services/vocabulary_service.py` - Topic classification
- `tests/unit/test_enrichment_service.py` - Add contamination tests
