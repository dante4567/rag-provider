# Future Improvements

**Last Updated:** October 16, 2025

## High Priority

### 1. Re-enrich Emails with Attachment Content

**Problem:**
- Currently, emails are enriched BEFORE attachments are processed
- Email summary doesn't mention attachment content
- RAG retrieval quality suffers: searching for "contract terms" won't surface email if terms are only in PDF attachment

**Current Workaround (Oct 16, 2025):**
- Attachments get WikiLinks in parent email after processing
- Each attachment has its own summary and is separately searchable
- Bidirectional links work (email → attachment, attachment → email)

**Proper Fix Needed:**
1. Process attachments first OR defer enrichment
2. Include attachment text in email enrichment context
3. Update email summary to mention: "This email includes attached documents containing [summary of attachment content]"
4. Better RAG context: one query can surface both email + relevant attachments

**Estimate:** 20-25 min implementation
**Impact:** Significantly improved RAG retrieval quality for emails with attachments
**Cost:** Negligible (same enrichment, just better context)

## Medium Priority

### 2. Relative Date Context Resolution

**Status:** Relative date parsing added (Oct 16, 2025) but uses "future from today"
**Issue:** "next Monday" parsed relative to ingestion date, not email send date
**Fix:** Use email sent date as reference for relative dates
**Estimate:** 10 min

### 3. Attachment Content Filtering

**Current:** Skips images <50KB (logos/icons)
**Could Add:**
- OCR for content-rich images (screenshots, diagrams)
- Skip signature images automatically
- Better content vs decoration detection

## Low Priority

### 4. Test Infrastructure

**Smoke Tests:** 4/11 passing (test infra issue, runtime works)
**Integration Tests:** Flaky due to LLM rate limits
**Action:** Fix test infra or accept current state

---

## Completed

- ✅ Dates extraction with absolute + relative dates (Oct 16, 2025)
- ✅ Entity type validation (people vs software) (Oct 15, 2025)
- ✅ LiteLLM unified interface for vision (Oct 16, 2025)
- ✅ Voyage cloud reranking (Oct 16, 2025)
- ✅ Attachment WikiLinks (basic version, Oct 16, 2025)
