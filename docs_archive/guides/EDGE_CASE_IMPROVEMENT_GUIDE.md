# Edge Case Improvement Guide - Make the RAG Better

## Overview

This guide shows you how to improve the RAG pipeline based on your own edge cases and feedback. You don't need to be a developer - just follow these patterns.

---

## 1. Improving Topic Classification

### When to Do This
- Document gets wrong topics
- Missing topics from your domain
- Over-classification (too many generic topics)

### How to Fix

**Step 1: Add Topics to Vocabulary**

Edit `vocabulary/topics.yaml`:

```yaml
# Add your new topics under the right category
school:
  - school/admin
  - school/curriculum
  - school/parent-communication  # ← NEW
  - school/medical-forms          # ← NEW

legal:
  - legal/custody
  - legal/contracts                # ← NEW
  - legal/immigration             # ← NEW
```

**Step 2: Test Your Topics**

```bash
# Copy updated vocabulary
docker cp vocabulary/topics.yaml rag_service:/app/vocabulary/topics.yaml

# Restart service
docker-compose restart rag-service

# Re-ingest a test document
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@test-doc.pdf" \
  -F "generate_obsidian=true" | jq '.metadata.keywords.primary'
```

**Step 3: Create Examples File**

Help the LLM classify better:

```yaml
# vocabulary/topic_examples.yaml
legal/contracts:
  - "This agreement is entered into..."
  - "WHEREAS the parties agree..."
  - "Terms and conditions..."

school/parent-communication:
  - "Dear parents,"
  - "Parent-teacher conference"
  - "Permission slip"
```

---

## 2. Handling Domain-Specific Entities

### Problem: Missing Entities

Example: Your documents mention "Sparkasse" (German bank) but it's not extracted as an organization.

### Solution: Add Entity Patterns

Create `vocabulary/entity_patterns.yaml`:

```yaml
organizations:
  banks:
    - Sparkasse
    - Volksbank
    - Commerzbank
    - Deutsche Bank

  schools:
    - Grundschule
    - Gymnasium
    - Realschule
    - ".*schule$"  # Regex: any word ending in "schule"

  government:
    - Jugendamt
    - Familiengericht
    - Finanzamt

people_roles:
  legal:
    - Richterin
    - Rechtsanwalt
    - Verfahrensbevollmächtigter

  education:
    - Lehrkraft
    - Schulleiter
    - Erzieherin
```

Then update enrichment service to use these patterns.

---

## 3. Improving Date/Number Extraction

### Problem: Dates Not Extracted

Examples that currently fail:
- "Anfang Oktober" (early October)
- "nächste Woche" (next week)
- "Q4 2025"

### Solution: Add Date Patterns

Edit `src/services/enrichment_service.py`:

```python
def extract_dates_from_content(self, content: str) -> List[str]:
    dates = set()

    # Existing patterns...

    # NEW: Quarter patterns
    quarter_pattern = r'Q([1-4])\s*(\d{4})'
    for match in re.finditer(quarter_pattern, content):
        quarter, year = match.groups()
        # Convert Q1 2025 → 2025-01-01
        month = (int(quarter) - 1) * 3 + 1
        dates.add(f"{year}-{str(month).zfill(2)}-01")

    # NEW: Relative dates
    if "nächste Woche" in content:
        next_week = datetime.now() + timedelta(days=7)
        dates.add(next_week.strftime('%Y-%m-%d'))

    return sorted(list(dates))
```

### Problem: Case Numbers Not Extracted

Example: "File #2025-ABC-123" not recognized.

### Solution: Add Custom Number Patterns

```python
def extract_numbers_from_content(self, content: str) -> List[str]:
    numbers = set()

    # Existing patterns...

    # NEW: File numbers
    file_pattern = r'File\s*#?\s*(\d{4}-[A-Z]+-\d+)'
    for match in re.finditer(file_pattern, content, re.IGNORECASE):
        numbers.add(match.group(1))

    # NEW: Reference numbers
    ref_pattern = r'Ref(?:erence)?[:\s]+([A-Z0-9-]+)'
    for match in re.finditer(ref_pattern, content, re.IGNORECASE):
        numbers.add(match.group(1))

    return sorted(list(numbers))
```

---

## 4. Creating Gold Query Sets

### Purpose
Track search quality over time with known good queries.

### Setup

Create `evaluation/my_queries.yaml`:

```yaml
version: 1.0
domain: personal-legal-education
created_at: 2025-10-08

queries:
  - query: "custody arrangements"
    expected_docs:
      - "2025-08-22-BschlussKur.pdf"
    expected_topics:
      - legal/custody
      - legal/court/decision

  - query: "school enrollment deadline"
    expected_docs:
      - "einschulung_2026_27_nrw_zeitstrahl_checkliste_obsidian.md"
    expected_entities:
      dates:
        - "2025-11-15"  # Critical deadline
    expected_topics:
      - education/school/enrollment

  - query: "case number 310 F 141/25"
    expected_docs:
      - "2025-08-22-BschlussKur.pdf"
    expected_exact_match: true  # Should return exact document
```

### Test Your Queries

```bash
# Run evaluation
curl -X POST http://localhost:8001/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "query_set": "my_queries",
    "run_name": "after-topic-fix"
  }' | jq
```

---

## 5. Improving Search Results

### Problem: Wrong Documents Returned

Example: Searching "court decision" returns meta-discussion instead of actual court PDF.

### Solutions

**A. Add Document Priorities**

```yaml
# vocabulary/document_priorities.yaml
high_priority:
  - doc_types: [pdf, docx]
    topics: [legal/court/*]
    boost: 2.0  # 2x relevance

  - filenames: [".*-BschlussKur.pdf"]
    boost: 1.5

low_priority:
  - topics: [communication/report]  # Meta-discussion
    penalty: 0.5  # 50% relevance
```

**B. Exclude Meta-Content from Embeddings**

```markdown
<!-- RAG:META-START -->
This document discusses the court decision of 2025-08-22...
<!-- RAG:META-END -->
```

Update chunking to exclude META blocks.

**C. Create Document Hierarchy**

```yaml
# vocabulary/document_hierarchy.yaml
primary_sources:
  - legal/court/decision
  - legal/contract
  - education/school/official-letter

secondary_sources:
  - communication/report
  - meeting/notes

# Boost primary sources by 1.5x in search
```

---

## 6. Handling Non-Standard Formats

### Problem: WhatsApp Exports Not Parsed Correctly

Example:
```
[2024-10-08, 14:32:15] John: Can you pick up the kids?
[2024-10-08, 14:35:20] Jane: Yes, at 15:00
```

### Solution: Add Custom Parser

Create `src/services/whatsapp_enhanced.py`:

```python
def parse_whatsapp_chat(content: str) -> Dict:
    messages = []

    pattern = r'\[(\d{4}-\d{2}-\d{2}), (\d{2}:\d{2}:\d{2})\] ([^:]+): (.+)'

    for match in re.finditer(pattern, content):
        date, time, sender, text = match.groups()

        messages.append({
            'date': date,
            'time': time,
            'sender': sender,
            'text': text
        })

    # Extract participants
    participants = list(set([m['sender'] for m in messages]))

    # Extract dates mentioned
    dates = extract_dates_from_messages(messages)

    return {
        'type': 'whatsapp_chat',
        'participants': participants,
        'messages': messages,
        'dates': dates,
        'summary': f"Chat between {', '.join(participants)}"
    }
```

---

## 7. Creating Feedback Loop

### Log Bad Results

```bash
# When you get a bad search result, log it
echo "2025-10-08,court decision,returned-wrong-doc,expected-BschlussKur.pdf" \
  >> logs/bad_searches.csv
```

### Review Logs Weekly

```bash
# Analyze patterns
cat logs/bad_searches.csv | cut -d',' -f3 | sort | uniq -c | sort -rn
# Shows: Which documents are frequently mis-ranked
```

### Create Improvement Tasks

```bash
# From logs, create tasks
echo "TODO: Boost legal PDFs over meta-discussion" >> TODO.md
echo "TODO: Add 'Gerichtsbeschluss' to German legal vocabulary" >> TODO.md
```

---

## 8. A/B Testing Improvements

### Before/After Comparison

```bash
# Test BEFORE change
curl -X POST http://localhost:8001/search \
  -d '{"text":"court decision","top_k":3}' \
  | jq '.results[] | {title, score}' \
  > results_before.json

# Make your change (e.g., add topics)

# Test AFTER change
curl -X POST http://localhost:8001/search \
  -d '{"text":"court decision","top_k":3}' \
  | jq '.results[] | {title, score}' \
  > results_after.json

# Compare
diff results_before.json results_after.json
```

---

## 9. Edge Case Examples & Solutions

### Edge Case 1: Multi-Language Documents

**Problem**: German legal PDF with English summary not extracted correctly.

**Solution**:

```python
# src/services/enrichment_service.py

def detect_language(self, content: str) -> str:
    """Detect primary language"""
    german_words = ['der', 'die', 'das', 'und', 'ist', 'von']
    english_words = ['the', 'and', 'is', 'of', 'to', 'in']

    german_count = sum(1 for word in german_words if word in content.lower())
    english_count = sum(1 for word in english_words if word in content.lower())

    return 'de' if german_count > english_count else 'en'

# Use different prompts for different languages
if lang == 'de':
    prompt = self._build_german_enrichment_prompt(...)
else:
    prompt = self._build_enrichment_prompt(...)
```

### Edge Case 2: Scanned Documents with Poor OCR

**Problem**: OCR extracts "R1chter1n" instead of "Richterin".

**Solution**:

```python
def clean_ocr_artifacts(self, text: str) -> str:
    """Clean common OCR mistakes"""
    replacements = {
        'R1chter1n': 'Richterin',
        '0CR': 'OCR',
        'l': 'I',  # Lowercase L → uppercase I in contexts
        '||': 'H'
    }

    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)

    return text
```

### Edge Case 3: Tables Not Extracted

**Problem**: Table with dates/numbers not extracted.

**Solution**:

```python
def extract_tables(self, content: str) -> List[Dict]:
    """Extract tables using markdown/HTML patterns"""
    tables = []

    # Markdown tables
    table_pattern = r'\|(.+?)\|'
    lines = content.split('\n')

    current_table = []
    for line in lines:
        if '|' in line:
            current_table.append(line)
        elif current_table:
            tables.append('\n'.join(current_table))
            current_table = []

    return tables
```

---

## 10. Contributing Improvements Back

### Share Your Edge Cases

Create an issue on GitHub:

```markdown
Title: Edge Case: German Date Format "Anfang Oktober" Not Extracted

**Problem**: Relative date expressions in German not recognized.

**Example Document**: School newsletter with "Anfang Oktober 2025"

**Expected**: Extract as "2025-10-01" (approx)

**Actual**: Not extracted

**Proposed Solution**:
[paste code or pattern]
```

### Submit Pull Requests

```bash
# 1. Create branch
git checkout -b feature/german-date-extraction

# 2. Make changes
vim src/services/enrichment_service.py

# 3. Test
pytest tests/unit/test_enrichment_service.py

# 4. Commit
git commit -m "Add German relative date extraction"

# 5. Push
git push origin feature/german-date-extraction

# 6. Create PR on GitHub
```

---

## Quick Reference: Improvement Workflow

```bash
# 1. Identify problem
"Document X not classified correctly"

# 2. Locate relevant file
vocabulary/topics.yaml  # For topics
src/services/enrichment_service.py  # For extraction

# 3. Make change
vim vocabulary/topics.yaml

# 4. Test locally
docker cp vocabulary/topics.yaml rag_service:/app/vocabulary/topics.yaml
docker-compose restart rag-service
curl -X POST http://localhost:8001/ingest/file -F "file=@test.pdf" -F "generate_obsidian=true"

# 5. Validate
jq '.metadata.keywords.primary' < result.json

# 6. Commit if good
git add vocabulary/topics.yaml
git commit -m "Add missing legal topics"
git push

# 7. Document edge case
echo "- 2025-10-08: Added legal/immigration topic for visa documents" >> CHANGELOG.md
```

---

## Next Steps

1. **Start small** - Fix one misclassified document
2. **Create feedback log** - Track bad results
3. **Weekly review** - Analyze patterns, make improvements
4. **Test everything** - Use gold query sets
5. **Share learnings** - Create issues, submit PRs

The system gets better with every edge case you handle!
