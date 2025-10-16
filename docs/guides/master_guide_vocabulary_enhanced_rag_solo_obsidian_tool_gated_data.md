# The Complete Guide to Vocabulary‑Enhanced RAG (Solo Mode)

*A master document for strategy, implementation, Obsidian workflow, and safe personal data integration — including address book & calendar enrichment.*

---

## TL;DR

- **Vocabulary**: Model concepts in SKOS, govern with Git-like changes, validate with SHACL, and keep hierarchy 2–4 levels deep. Use `prefLabel`, `altLabel`, `hiddenLabel`, `broader/narrower`, `related`. Map to public vocabularies via `exactMatch/closeMatch`.
- **Pipelines**: Prepare data via **Preprocess → Enrich → Chunk → Embed**. Hybrid retrieval (BM25 + vectors + cross-encoder), then **boost concept overlap** and structure hits.
- **Capsules, not guesses**: Each item (email/chat/doc) carries a **Single‑Doc Context Capsule (SDCC)** with anchors (ids, dates, participants, heading path, concept ids) — small, extractive, and provenance‑aware.
- **Solo mode**: You’re the only user. Keep frontmatter minimal. Use **tool‑gated access** to finance/contacts/calendar; pass **redacted capsules** instead of raw data. Keep speculation in **/triage/** notes, never in YAML or embeddings.
- **Auto‑enrichment by‑product**: As you ingest items, generate **contact deltas** and **event deltas** for quick review in Obsidian; accept to patch `/profile/Contacts/*` and `/calendar/Events/*`.
- **Safety**: Never send secrets (SSN/IBAN full/keys). Redact by default; log tool calls; demote untrusted sources.

---

## Part 1 — The Strategic Framework (The RAG Playbook)

### 1.1 Concept Modeling (MV‑SKOS)
- **Concept = abstract idea** with a stable ID (`ex:C04217`); never reuse.
- **Core**: `prefLabel` (1), `altLabel` (synonyms/abbreviations), `hiddenLabel` (misspellings), `broader/narrower`, `related`, `scopeNote` (usage guidance).
- **Polyhierarchy** allowed; mark **stop concepts** (too broad) as *non‑indexable*.
- **Mappings**: `exactMatch / closeMatch / broadMatch / narrowMatch` to Wikidata/Schema.org/etc. Keep a **mapping confidence**.
- **Multilingual**: keep labels per language (SKOS‑XL if you want label metadata).

### 1.2 IDs, Versioning, Governance
- **Stable CURIEs** (e.g., `ex:C20251016143012`).
- Do **not** recycle IDs; deprecate with `status: deprecated` + `replacedBy`.
- Version the scheme (`v1.0.0`, `v1.1.0`). Maintain `CHANGELOG.md`.
- **Workflow (solo)**: Inbox → weekly review → release batch commit.

### 1.3 Validation as Code (CI)
- **SHACL** to prevent cycles, require `prefLabel`, disallow orphan `narrower`, forbid duplicate `altLabel`.
- Lint vocabulary with SKOSify/RDF toolchain.

### 1.4 Retrieval Architecture (Scoring)
- BM25 (field boosts: `title > headings > body > table > captions`).
- Vector ANN (domain‑tuned bi‑encoder) → **cross‑encoder re‑rank**.
- **Final score** ≈ α·BM25 + β·cosine + γ·concept‑overlap + δ·structure + ε·recency.
- **Abstain** if confidence below τ; ask clarifying question.

---

## Part 2 — The Data Processing Factory (Doctypes)

**Stages**: 1) Preprocess & normalize → 2) Structure & enrich → 3) Chunk → 4) Embed.

### 2.1 Scanned Documents (PDF/TIFF)
- OCR is foundational (layout‑aware). Capture headings/captions. Gate ingest on OCR quality score; queue low‑quality for re‑OCR.
- Keep **tables as whole chunks** and also store normalized CSV/JSON + units.

### 2.2 Emails
- Parse headers (From/To/Cc/Message‑ID/References). Thread as unit; store `thread_id`, `message_index`, `message_count`.
- Chunk: single message or a few back‑and‑forth messages; include sender/timestamp.

### 2.3 Chat Logs (WhatsApp/Signal/Slack/LLM)
- Structure: `timestamp, author, text`. Segment sessions by **time gap** (≥60–90m) and topic shift. Keep speaker tags in chunk text.
- For LLM chats: record **model/version**, **tool calls**, **system prompt hash**, **citations**.

### 2.4 Code / Office / Web
- Code chunks by block/function; keep language, path, commit hash.
- Office: slide titles, speaker notes, sheet cell values; preserve order.
- Web/HTML: strip boilerplate; use h1–h3 and definition lists as chunk boundaries.

**Chunk size heuristic**: 120–250 tokens, 1 idea per chunk, avoid crossing section boundaries; micro‑overlap ≤ 2 sentences when structure is weak.

---

## Part 3 — Single‑Doc Context Capsule (SDCC)

A small, extractive JSON header that anchors an item **without** importing outside knowledge. Include in prompts at ingestion.

```json
{
  "capsule_version": "1.0",
  "doc_id": "mail:2024-11-11T10:18Z:msgid=<abc@x>",
  "doctype": "Email|Chat|LLMChat|Doc|Code|Attachment",
  "source": {"path":"attachments/...","system":"Gmail|WhatsApp|Obsidian","thread_id":"t-79A12","message_index":5,"message_count":16},
  "heading_path": ["Project X","Onboarding","Access"],
  "participants": [{"name":"Alice Müller","role":"Legal","alias":["alice"],"id":"contact:alice"}],
  "timeline": {"start_ts":"2024-11-11T08:57:00Z","end_ts":"2024-11-11T12:05:00Z","gaps":[{"start":"2024-11-11T09:40:00Z","end":"2024-11-11T11:10:00Z","minutes":90}]},
  "topic": {"subject_normalized":"Linux on MacBook Air (2020)","session_labels":["Live USB","Dual-boot"],"lang":"en"},
  "concepts": {"ids":["ex:C200","ex:C210","ex:C230"],"labels":["Pop!_OS","Ubuntu","Live USB"]},
  "decisions": ["Try Live USB first; consider VM next"],
  "action_items": [{"owner":"person:daniel","action":"Create macOS recovery USB","due_date":null}],
  "entities": [{"text":"MacBook Air (2020)","norm":"device:macbook_air_2020","first_offset":128}],
  "attachments": [{"name":"install_guide.pdf","id":"file:abc","type":"pdf","ocr_quality":0.93}],
  "provenance": {"llm_prompt":"hash","tools_used":["web.search"],"embedder":{"name":"model-x","version":"1.3.2","hash":"…"}},
  "hints": {"related_docs_counts":[{"concept_id":"ex:C230","count":42}],"conflicts_known":[]}
}
```

**Guidelines**: Extractive only; absolute dates; stable IDs; hints are non‑assertive.

---

## Part 4 — Enrichment Prompts (JSON‑only)

### 4.1 Global System Prompt
```
You are an accurate, conservative annotator inside a data pipeline.
Use ONLY the provided capsule + content. Do not import outside knowledge.
Return EXACTLY valid JSON matching the requested schema. No prose, no code fences.
Prefer extractive evidence with offsets. If uncertain, use null/[] and add a brief internal_notes.
```

### 4.2 Concept Tagging (Vocabulary‑Aware)
```
TASK: Vocabulary tagging
INPUT: { text, lang, vocabulary[...], candidate_mentions? }
OUTPUT: { concepts_found[], unresolved_mentions[], internal_notes }
```

### 4.3 Faithful Summarization for Retrieval
```
TASK: Faithful summarization
INPUT: { text, lang, token_budget:120, must_include:{numbers:true,dates:true,entities:true}, forbid:["recommendations"] }
OUTPUT: { summary, salient_points[], references[] }
```

### 4.4 Keywords & Queries
```
TASK: Keyphrase extraction
INPUT: { text, lang, allow_numbers:true, max_keywords:12, prefer_titles_and_headings:true, vocabulary_context?:[ids] }
OUTPUT: { keywords[{phrase,weight,evidence_span}], query_suggestions[] }
```

### 4.5 Facet Classification
```
TASK: Facet classification
INPUT: { text, facets:{audience[],region[],doctype[]}, pick_top_k:1 }
OUTPUT: { audience{label,confidence}, region{...}, doctype{...}, internal_notes }
```

### 4.6 Email/Chat Specific
- **Email thread enrichment**: decisions, action items, participants, normalized subject, with extractive evidence.
- **Chat session**: topics, Q&A pairs (speaker aware), decisions, open questions, session summary.

### 4.7 Meta‑Prompt (One Call Per Chunk)
```
TASK: Chunk enrichment (multi‑task)
INPUT: { text, lang, heading_path[], vocabulary[], facets{}, generate:{summary:true,keywords:true,concepts:true,facets:true} }
OUTPUT: { summary, keywords[], concepts_found[], facets{...}, internal_notes }
```

---

## Part 5 — Assessment (Quality, Sensitivity, Questions)

Produce a separate **assessor JSON** for ranking, triage, and safety (not in frontmatter):

```json
{
  "assessment_version": "1.0",
  "source_type": "email|chat|llm_chat|web|doc",
  "recency_days": 2,
  "evidence_rich": true,
  "citation_present": false,
  "hallucination_risk": "low|medium|high",
  "sensitivity": ["pii_possible"],
  "disambiguations": [{"surface":"Anna","resolved_to":"contact:anna_smith","confidence":0.86}],
  "open_questions": [{"q":"Backup exists <7 days?","severity":"medium"}],
  "followups": [{"action":"Test advanced gestures (mtrack)","owner":"person:daniel"}],
  "trust_score": 0.62,
  "notes": "Advisory only; facts must be extractive."
}
```

Usage: demote low‑trust `llm_chat` vs. primary sources; open `/triage/{doc_id}.md` for questions.

---

## Part 6 — Tool‑Gated Private Data (Finance, Contacts, Calendar, Devices)

### 6.1 Principle
**Connect** sensitive sources; do **not** embed them. The model may fetch **minimal, redacted** slices via audited tools.

### 6.2 Example Tool Signatures (Read‑Only, Redacting)
```ts
finance.search_transactions({ from, to, account, merchant?, amount_range?, limit:50 })
  -> [{ tx_id, ts, merchant, amount, currency, category, account_last4 }]

finance.get_invoice({ invoice_id })
  -> { id, vendor, issue_date, due_date, amount, currency, vat, line_items[], file_ref }

finance.match_invoice({ invoice_id })
  -> { candidate_tx_ids:[...], rationale }

contacts.resolve_name({ surface:"Anna" })
  -> [{ contact_id, display, role, confidence }]

calendar.resolve_relative({ anchor_ts, phrase:"next sprint" })
  -> { start, end }

devices.resolve({ surface:"iPad" })
  -> { device_id, model }
```
**Rules**: mask identifiers (last4), cap results, block broad dumps, log every call.

### 6.3 Capsules, Not Raw Rows
```json
{
  "capsule":"finance.tx_summary.v1",
  "period":["2024-11-01","2024-11-30"],
  "totals":{ "count":92, "amount":3120.44, "currency":"EUR", "vat_est":497.23 },
  "top_merchants":["Deutsche Bahn","Amazon","Netto"],
  "anomalies":[{"tx_id":"tx_9ab","reason":"amount>>median"}],
  "masking":"iban_last4,email_local_hidden"
}
```

### 6.4 High‑Risk Echo Guard (Prompt Snippet)
```
Never echo more than 4 consecutive digits from private identifiers. Mask as **** and last4. If asked for full values, refuse and suggest safer alternatives.
```

---

## Part 7 — Solo‑Mode Policy (What the Model Sees)

### 7.1 Tiered Visibility
- **Tier 0 (always)**: SDCC anchors — doc/thread IDs, absolute dates, heading_path, display names (no emails/phones), concept_ids, timezone/cadence, a few stable preferences.
- **Tier 1 (on trigger)**: minimal, redacted slices via tools (contacts, calendar, finance, devices).
- **Tier 2 (explicit confirmation)**: reveal a specific masked channel or invoice field for reconciliation.
- **Tier 3 (never)**: SSNs, full IBAN/card numbers, seed phrases, license keys, full serials.

### 7.2 Solo Persona Capsule (Tiny, Non‑Sensitive)
```json
{
  "solo_persona_v1": {
    "tz": "Europe/Berlin",
    "cadence": "sprint:2w Monday",
    "prefs": { "linux": ["Ubuntu","Pop!_OS"], "editor": ["vscode","neovim"] },
    "top_contacts": [
      {"display":"Anna Smith","id":"contact:anna","role":"Legal","aliases":["Anna"]},
      {"display":"Bob","id":"contact:bob","role":"Dev","aliases":["Bob"]}
    ],
    "devices": ["MacBook Air (Intel, 2020)","iPad Pro 11"]
  }
}
```

---

## Part 8 — Auto‑Enrich Address Book & Calendar (Delta Workflow)

Let ingestion produce **deltas** you review; accepted deltas patch canonical notes. No secrets, masked channels only.

### 8.1 Contact Delta Schema
```json
{
  "delta_version":"1.0",
  "doc_id":"mail:2024-11-11:…",
  "target":"contact:anna_smith" ,
  "confidence":0.86,
  "proposed":{
    "names_add":["Anna S."],
    "aliases_add":["Anna"],
    "org_title_add":{ "org":"Acme GmbH","title":"Legal Counsel","from":"2024-01-01","to":null },
    "tags_add":["Legal"],
    "channels_add":[{ "type":"email","masked":"*@acme.com","last4":"acme" }],
    "links_add":["https://www.linkedin.com/in/…"]
  },
  "evidence":{ "span":[1482,1560], "quote":"Anna Smith — Legal Counsel, Acme GmbH" }
}
```

### 8.2 Event Delta Schema
```json
{
  "delta_version":"1.0",
  "doc_id":"chat:2025-02-03:…",
  "confidence":0.82,
  "event":{
    "title":"Linux live USB test",
    "start":"2025-02-05T15:00:00+01:00",
    "end":"2025-02-05T16:00:00+01:00",
    "participants":["person:daniel","contact:anna_smith"],
    "location":"Zoom",
    "recurrence":null,
    "notes":"Decide Pop!_OS vs Ubuntu; trackpad gestures check"
  },
  "evidence":{ "quote":"let's do Thu 15:00 CET", "anchor_ts":"2025-02-03T10:12:00+01:00" }
}
```

### 8.3 Obsidian Folders
```
/profile/Contacts/            # canonical contact notes
/profile/_Deltas/             # accepted deltas (JSON audit trail)
/calendar/Events/             # optional event notes (past outcomes)
/triage/                      # accept/reject human-in-the-loop
```

### 8.4 Contact Note (Canonical)
```markdown
---
id: contact:anna_smith
names: ["Anna Smith"]
aliases: ["Anna"]
org_history:
  - { org: "Acme GmbH", title: "Legal Counsel", from: "2024-01-01", to: null }
roles: ["Legal"]
channels:
  - { type: "email", masked: "*@acme.com", last4: "acme" }
links: []
do_not_share: true
updated: 2025-10-16
---
```

### 8.5 Triage Note Template
```markdown
---
doc_id: mail:2024-11-11:…
type: contact_delta
target: contact:anna_smith
confidence: 0.86
delta_ref: attachments/deltas/contact_delta_2024-11-11.json
---

# Contact update — Anna Smith

**Proposal**
- Add alias “Anna”
- Add org/title: Legal Counsel @ Acme (since 2024-01-01)

**Evidence**
> "Anna Smith — Legal Counsel, Acme GmbH"

**Action**
- [ ] Accept → patch contact
- [ ] Reject
```

### 8.6 Dashboards (Dataview)
```dataview
TABLE file.link, confidence
FROM "triage"
WHERE type = "contact_delta"
SORT confidence desc
```

### 8.7 Acceptance Rules
- **Auto‑accept**: confidence ≥ 0.9, non‑sensitive (alias/tag), target exists.
- **Manual**: first org/title; any channel addition; any new event.
- **Never auto‑accept** strings with >4 consecutive digits.

### 8.8 Recurrence Detector (Optional)
- Given N events with same participants/title, propose RFC5545 rule when ≥3 instances align within ±15m.

---

## Part 9 — Obsidian Setup (Templates & Structure)

### 9.1 Folders
```
/vocab/Concepts/
/vocab/Inbox/
/vocab/_Dashboards/
/vocab/Scheme.md
/vocab/CHANGELOG.md
/templates/
  Concept.md
  ConceptInbox.md
  VocabDashboard.md
  Contact.md
  Triage.md
```

### 9.2 Concept Template (`/templates/Concept.md`)
```markdown
---
id: ex:C<% tp.date.now("YYYYMMDDHHmmss") %>
prefLabel: "<%* tR = await tp.system.prompt('Preferred label'); tR %>"
altLabel: []
hiddenLabel: []
broader: []
narrower: []
related: []
status: active
replacedBy: null
scopeNote: ""
notes: ""
exactMatch: []
closeMatch: []
created: <% tp.date.now("YYYY-MM-DD") %>
version_added: v1.0.0
version_deprecated: null
---

# <% tp.frontmatter.prefLabel %>

**ID:** <% tp.frontmatter.id %>

## Usage
- Use for: …
- Avoid for: …

## Relations
- **Broader:** <% tp.frontmatter.broader?.join(", ") %>
- **Narrower:** <% tp.frontmatter.narrower?.join(", ") %>
- **Related:** <% tp.frontmatter.related?.join(", ") %>
```

### 9.3 Inbox Template (`/templates/ConceptInbox.md`)
```markdown
---
status: proposed
surface: "<%* s = await tp.system.prompt('Surface form'); s %>"
contexts: [""]
suggested_concepts: []
proposed_prefLabel: "<% tp.frontmatter.surface %>"
proposed_altLabel: []
proposed_broader: []
reason: ""
review:
  editor: "daniel"
  reviewer: null
  decision: pending
  decided_on: null
---

# Proposal: <% tp.frontmatter.surface %>
- Why: …
- Evidence: …
```

### 9.4 Vocabulary Dashboard (`/templates/VocabDashboard.md`)
```markdown
# Vocabulary Dashboard

## Inbox (needs decision)
```dataview
TABLE surface, reason
FROM "vocab/Inbox"
WHERE status = "proposed" AND review.decision = "pending"
SORT file.ctime asc
```

## Recently added (last 7 days)
```dataview
TABLE prefLabel, id, broader, altLabel
FROM "vocab/Concepts"
WHERE status = "active" AND file.ctime >= date(today) - dur(7 days)
SORT prefLabel asc
```

## Orphans (check top concepts)
```dataview
TABLE prefLabel, id
FROM "vocab/Concepts"
WHERE status = "active" AND length(broader) = 0
```

## Deprecated (ensure replacedBy)
```dataview
TABLE prefLabel, id, replacedBy
FROM "vocab/Concepts"
WHERE status = "deprecated"
```
```

---

## Part 10 — Index Schema & Rendering

### 10.1 Index Record (Minimal)
```json
{
  "doc_id": "mail:2024-11-11:...msgid...",
  "chunk_id": "C001",
  "doctype": "Email",
  "lang": "en",
  "heading_path": ["Project","Linux on MacBook Air"],
  "text": "…",
  "tokens": 182,
  "concept_ids": ["ex:C200","ex:C210","ex:C230"],
  "annotation_confidence": [0.94,0.91,0.88],
  "capsule_ref": "capsule:mail:2024-11-11:...",
  "prev_chunk_id": null,
  "next_chunk_id": "C002",
  "ts": "2024-11-11T10:18:00Z",
  "security": ["internal"],
  "embedder": {"name":"model-x","version":"1.3.2","hash":"…"}
}
```

### 10.2 Obsidian Frontmatter (Lean)
```yaml
doc_id: mail:2024-11-11:...msgid...
doctype: Email
concept_ids: ["ex:C200","ex:C210","ex:C230"]
participants: ["person:daniel","contact:anna_smith"]
dates: ["2024-11-11"]
thread_id: t-79A12
```

### 10.3 Rendering Note Body
- Sections: Summary → People → Decisions → Action Items → Important Dates → Source → Content Pointer.
- Keep JSON outputs in sidecars under `/attachments/{doc_id}.enrich.json` and `/attachments/{doc_id}.assess.json`.

---

## Part 11 — Safety, Privacy, and Policy

- **Do not embed** raw bank ledgers, full contact cards, or secrets.
- **Mask** identifiers (show last4) and block echoing >4 consecutive digits.
- **Tool‑gated access only**; all tools read‑only, redacting, rate‑limited, and logged.
- **Speculation isolation**: `/triage/` holds hypotheses/questions until confirmed.
- **Demote** untrusted sources (old LLM chats) via `trust_score` in assessor.

---

## Part 12 — Checklists & Quick Start

**Solo Quick Start**
- [ ] Create `/vocab/*` + templates and validation.
- [ ] Implement SDCC generation (tier 0).
- [ ] Add enrichment + assessor prompts with schema validation.
- [ ] Implement tools: contacts/calendar/finance/devices (masked, limited).
- [ ] Wire trigger rules (names/devices/relative dates/reconciliation cues).
- [ ] Enable contact_delta / event_delta extraction.
- [ ] Render `/triage/*` notes and Dataview dashboards.
- [ ] Keep frontmatter minimal; store JSON sidecars.

**Weekly**
- [ ] Review `vocab/_Dashboards/Vocab Review.md`.
- [ ] Triage deltas; accept/reject; commit via Obsidian Git.
- [ ] Bump `Scheme.md` if structure changed; update `CHANGELOG.md`.

---

## Part 13 — Snippets & Appendices

### 13.1 SHACL Validation Snippet
```turtle
ex:ConceptShape a sh:NodeShape ;
  sh:targetClass skos:Concept ;
  sh:property [ sh:path skos:prefLabel ; sh:minCount 1 ] ;
  sh:property [ sh:path skos:broader ; sh:nodeKind sh:IRI ; sh:severity sh:Violation ] ;
  sh:sparql [
    sh:message "No cycles in broader/narrower hierarchy" ;
    sh:select """
      SELECT ?c WHERE { ?c skos:broader+ ?c . }
    """
  ] .
```

### 13.2 Hybrid Scoring (Illustrative)
```text
score(d,q) =
  0.35 * bm25(d,q)
+ 0.35 * cosine(embed(d), embed(q))
+ 0.20 * jaccard(concepts(d), concepts(q))
+ 0.05 * structureBoost(d,q)
+ 0.05 * recency(d)
```

### 13.3 Policy Snippet (Echo Guard)
```yaml
private_identifier_echo_guard:
  max_unmasked_digits: 4
  mask: "*"
  fields: [iban, card, ssn, license, serial]
```

### 13.4 Persona Store Examples
```markdown
/profile/Me.md
---
id: person:daniel
names: ["Daniel","Dan"]
roles: ["Parent","Engineer","Homelab admin"]
timezone: Europe/Berlin
sprint_cadence: "2w starting Mondays"
preferred_linux: ["Ubuntu","Pop!_OS"]
do_not_share: true
---
```

### 13.5 Templater/QuickAdd Hints
- Generate `ex:C<timestamp>` IDs.
- Promote Inbox → Concepts.
- Create triage note from delta JSON.

---

## Part 14 — FAQ

- **Why capsules?** They anchor context without leaking cross‑doc facts; great for single‑pass LLMs.
- **Do I still need RAG?** Yes, for cross‑doc questions. Capsules make each item self‑describing; RAG stitches items together.
- **Where do speculative insights go?** `/triage/{doc_id}.md`, never in YAML or embeddings.
- **Can I preload more about myself?** Use the tiny **solo persona capsule**; everything else is fetched via tools on demand.

---

**End of Master Guide**

